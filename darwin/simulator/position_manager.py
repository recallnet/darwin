"""Position manager for simulating multiple open positions."""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from darwin.schemas.candidate import ExitSpecV1
from darwin.schemas.position import ExitReason, PositionRowV1
from darwin.simulator.position import Position
from darwin.storage.interface import PositionLedgerInterface


class PositionManager:
    """
    Manages multiple open positions with entry/exit simulation.

    Responsibilities:
    - Opens new positions with entry fills and fees
    - Updates all open positions each bar
    - Closes positions when exit conditions are met
    - Handles fill simulation (slippage, fees)
    - Calculates PnL and R-multiples
    - Writes to position ledger

    Fill Simulation Semantics:
    - Decision made at bar close
    - Entry filled at next bar open (taker order with slippage)
    - Exit filled at trigger price (maker order)
    """

    def __init__(
        self,
        ledger: PositionLedgerInterface,
        run_id: str,
        fee_maker_bps: float = 6.0,
        fee_taker_bps: float = 12.5,
        spread_bps_map: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize position manager.

        Args:
            ledger: Position ledger interface for persistence
            run_id: Run ID for this simulation
            fee_maker_bps: Maker fee in basis points (default: 6.0)
            fee_taker_bps: Taker fee in basis points (default: 12.5)
            spread_bps_map: Spread in bps per symbol (default: BTC=1.5, ETH=2.0, SOL=3.0)
        """
        self.ledger = ledger
        self.run_id = run_id
        self.fee_maker_bps = fee_maker_bps
        self.fee_taker_bps = fee_taker_bps

        # Default spread map
        if spread_bps_map is None:
            self.spread_bps_map = {
                "BTC-USD": 1.5,
                "ETH-USD": 2.0,
                "SOL-USD": 3.0,
            }
        else:
            self.spread_bps_map = spread_bps_map

        # Active positions
        self.positions: Dict[str, Position] = {}

    def open_position(
        self,
        candidate_id: str,
        symbol: str,
        direction: str,
        signal_price: float,
        next_open: float,
        bar_index: int,
        timestamp: datetime,
        size_usd: float,
        atr_at_entry: float,
        exit_spec: ExitSpecV1,
    ) -> str:
        """
        Open a new position with entry fill simulation.

        Entry Fill Logic:
        - Decision made at bar close (signal_price)
        - Order filled at next bar open (next_open)
        - Slippage applied: spread_bps for the symbol
        - Fees applied: taker fee (12.5 bps by default)

        Args:
            candidate_id: Candidate ID that triggered this position
            symbol: Trading symbol
            direction: Position direction ('long' or 'short')
            signal_price: Price at bar close when decision was made
            next_open: Open price of next bar (actual fill reference)
            bar_index: Bar index at entry
            timestamp: Entry timestamp
            size_usd: Position size in USD (notional)
            atr_at_entry: ATR(14) value at entry
            exit_spec: Exit specification from playbook

        Returns:
            Position ID of the newly opened position.
        """
        # Calculate fill price with slippage
        spread_bps = self.spread_bps_map.get(symbol, 2.0)  # Default 2 bps
        entry_price = self._calculate_entry_fill(next_open, direction, spread_bps)

        # Calculate entry fees (taker)
        entry_fees_usd = (self.fee_taker_bps / 10000.0) * size_usd

        # Calculate position size in units
        size_units = size_usd / entry_price

        # Generate position ID
        position_id = f"{self.run_id}_{symbol}_{bar_index}_{uuid.uuid4().hex[:8]}"

        # Create Position object
        position = Position(
            position_id=position_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            entry_bar_index=bar_index,
            entry_timestamp=timestamp,
            size_usd=size_usd,
            size_units=size_units,
            entry_fees_usd=entry_fees_usd,
            atr_at_entry=atr_at_entry,
            exit_spec=exit_spec,
        )

        # Add to active positions
        self.positions[position_id] = position

        # Create position record for ledger
        position_record = PositionRowV1(
            position_id=position_id,
            run_id=self.run_id,
            candidate_id=candidate_id,
            symbol=symbol,
            direction=direction,
            entry_timestamp=timestamp,
            entry_bar_index=bar_index,
            entry_price=entry_price,
            entry_fees_usd=entry_fees_usd,
            size_usd=size_usd,
            size_units=size_units,
            stop_loss_price=exit_spec.stop_loss_price,
            take_profit_price=exit_spec.take_profit_price,
            time_stop_bars=exit_spec.time_stop_bars,
            trailing_enabled=exit_spec.trailing_enabled,
            trailing_activated=False,
            highest_price=position.highest_high,
            lowest_price=position.lowest_low,
            is_open=True,
        )

        # Write to ledger
        self.ledger.open_position(position_record)

        return position_id

    def update_positions(
        self, high: float, low: float, close: float, bar_index: int, timestamp: datetime
    ) -> List[str]:
        """
        Update all open positions with new bar data.

        Checks exit conditions for all positions and closes any that should exit.

        Args:
            high: Current bar high
            low: Current bar low
            close: Current bar close
            bar_index: Current bar index
            timestamp: Current bar timestamp

        Returns:
            List of position IDs that were closed.
        """
        closed_positions = []

        for position_id, position in list(self.positions.items()):
            # Update position state and check exits
            exit_result = position.update_bar(high, low, close, bar_index, timestamp)

            # Update trailing state in ledger if activated
            if position.trailing_activated and exit_result is None:
                self.ledger.update_position_trailing(
                    position_id=position_id,
                    trailing_activated=True,
                    highest_price=position.highest_high,
                    lowest_price=position.lowest_low,
                )

            # Close position if exit condition met
            if exit_result is not None:
                self._close_position(position, exit_result)
                closed_positions.append(position_id)
                del self.positions[position_id]

        return closed_positions

    def close_all_positions(
        self, close: float, bar_index: int, timestamp: datetime
    ) -> List[str]:
        """
        Close all open positions at end of run.

        Args:
            close: Current bar close price
            bar_index: Current bar index
            timestamp: Current bar timestamp

        Returns:
            List of position IDs that were closed.
        """
        closed_positions = []

        for position_id, position in list(self.positions.items()):
            exit_result = position.force_close(
                close=close,
                bar_index=bar_index,
                timestamp=timestamp,
                reason=ExitReason.END_OF_RUN,
            )
            self._close_position(position, exit_result)
            closed_positions.append(position_id)
            del self.positions[position_id]

        return closed_positions

    def get_open_position_count(self) -> int:
        """Get count of currently open positions."""
        return len(self.positions)

    def get_open_positions(self) -> List[Position]:
        """Get list of all open positions."""
        return list(self.positions.values())

    def get_position(self, position_id: str) -> Optional[Position]:
        """Get a specific position by ID."""
        return self.positions.get(position_id)

    def _calculate_entry_fill(
        self, next_open: float, direction: str, spread_bps: float
    ) -> float:
        """
        Calculate entry fill price with slippage.

        Entry simulation:
        - For longs: pay the spread (buy at ask)
        - For shorts: pay the spread (sell at bid)

        Args:
            next_open: Next bar open price
            direction: Position direction ('long' or 'short')
            spread_bps: Spread in basis points

        Returns:
            Entry fill price with slippage applied.
        """
        slippage_factor = spread_bps / 10000.0

        if direction == "long":
            # Long: pay the spread (worse fill)
            return next_open * (1.0 + slippage_factor)
        else:
            # Short: pay the spread (worse fill)
            return next_open * (1.0 - slippage_factor)

    def _calculate_exit_fill(
        self, exit_price: float, direction: str, spread_bps: float
    ) -> float:
        """
        Calculate exit fill price with slippage.

        Exit simulation:
        - Assume maker order at limit price (exit_price)
        - Apply spread slippage (more conservative than zero slippage)

        Args:
            exit_price: Exit trigger price
            direction: Position direction ('long' or 'short')
            spread_bps: Spread in basis points

        Returns:
            Exit fill price with slippage applied.
        """
        slippage_factor = spread_bps / 10000.0

        if direction == "long":
            # Long exit: sell at bid (worse fill)
            return exit_price * (1.0 - slippage_factor)
        else:
            # Short exit: buy at ask (worse fill)
            return exit_price * (1.0 + slippage_factor)

    def _close_position(self, position: Position, exit_result) -> None:
        """
        Close a position and write to ledger.

        Args:
            position: Position object to close
            exit_result: ExitResult with exit details
        """
        # Get spread for this symbol
        spread_bps = self.spread_bps_map.get(position.symbol, 2.0)

        # Calculate exit fill price with slippage
        exit_price = self._calculate_exit_fill(
            exit_result.exit_price, position.direction, spread_bps
        )

        # Calculate exit notional
        exit_notional_usd = exit_price * position.size_units

        # Calculate exit fees (maker for limit orders)
        exit_fees_usd = (self.fee_maker_bps / 10000.0) * exit_notional_usd

        # Calculate gross PnL
        if position.direction == "long":
            gross_pnl = exit_notional_usd - position.size_usd
        else:
            gross_pnl = position.size_usd - exit_notional_usd

        # Calculate net PnL (after fees)
        net_pnl_usd = gross_pnl - position.entry_fees_usd - exit_fees_usd

        # Calculate PnL percentage
        pnl_pct = net_pnl_usd / position.size_usd if position.size_usd > 0 else 0.0

        # Calculate R-multiple
        risk_amount = abs(position.entry_price - position.stop_loss_price) * position.size_units
        r_multiple = net_pnl_usd / risk_amount if risk_amount > 0 else 0.0

        # Write close to ledger
        self.ledger.close_position(
            position_id=position.position_id,
            exit_timestamp=exit_result.timestamp,
            exit_bar_index=exit_result.bar_index,
            exit_price=exit_price,
            exit_fees_usd=exit_fees_usd,
            exit_reason=exit_result.exit_reason.value,
            pnl_usd=net_pnl_usd,
            pnl_pct=pnl_pct,
            r_multiple=r_multiple,
        )

    def _calculate_position_size(
        self,
        equity: float,
        risk_per_trade_pct: float,
        entry_price: float,
        stop_loss_price: float,
    ) -> float:
        """
        Calculate position size based on risk management rules.

        Uses fixed fractional position sizing based on equity and risk per trade.

        Args:
            equity: Current account equity in USD
            risk_per_trade_pct: Risk per trade as percentage (e.g., 0.01 = 1%)
            entry_price: Entry price
            stop_loss_price: Stop loss price

        Returns:
            Position size in USD (notional value).
        """
        # Risk amount in USD
        risk_amount_usd = equity * risk_per_trade_pct

        # Distance to stop loss as fraction
        stop_distance_pct = abs(entry_price - stop_loss_price) / entry_price

        # Position size to risk the target amount
        if stop_distance_pct > 0:
            size_usd = risk_amount_usd / stop_distance_pct
        else:
            size_usd = 0.0

        return size_usd
