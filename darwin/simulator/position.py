"""Position class for tracking open positions with all exit logic."""

from datetime import datetime
from typing import Optional

from darwin.schemas.candidate import ExitSpecV1
from darwin.schemas.position import ExitReason
from darwin.simulator.exits import ExitChecker, ExitResult


class Position:
    """
    Tracks a single open position with all exit conditions.

    This class maintains the state of an open position and checks exit conditions
    on each bar update. It implements comprehensive trailing stop logic with proper
    ratcheting behavior.

    Key invariants:
    - Trailing stop never decreases (for longs) / never increases (for shorts)
    - Trailing stop never crosses entry price (no profit lock-in before activation)
    - Trailing stop always stays within trail_distance of highest_high/lowest_low
    """

    def __init__(
        self,
        position_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        entry_bar_index: int,
        entry_timestamp: datetime,
        size_usd: float,
        size_units: float,
        entry_fees_usd: float,
        atr_at_entry: float,
        exit_spec: ExitSpecV1,
    ):
        """
        Initialize a new position.

        Args:
            position_id: Unique position identifier
            symbol: Trading symbol
            direction: Position direction ('long' or 'short')
            entry_price: Entry price (with slippage)
            entry_bar_index: Bar index at entry
            entry_timestamp: Entry timestamp
            size_usd: Position size in USD
            size_units: Position size in units
            entry_fees_usd: Entry fees in USD
            atr_at_entry: ATR(14) value at entry
            exit_spec: Exit specification from playbook
        """
        # Identity
        self.position_id = position_id
        self.symbol = symbol
        self.direction = direction

        # Entry details
        self.entry_price = entry_price
        self.entry_bar_index = entry_bar_index
        self.entry_timestamp = entry_timestamp
        self.size_usd = size_usd
        self.size_units = size_units
        self.entry_fees_usd = entry_fees_usd
        self.atr_at_entry = atr_at_entry

        # Exit specification
        self.exit_spec = exit_spec
        self.stop_loss_price = exit_spec.stop_loss_price
        self.take_profit_price = exit_spec.take_profit_price
        self.time_stop_bars = exit_spec.time_stop_bars

        # Trailing stop state
        self.trailing_enabled = exit_spec.trailing_enabled
        self.trailing_activated = False
        self.trailing_stop_price: Optional[float] = None

        # Price tracking (for trailing stops)
        if direction == "long":
            self.highest_high = entry_price
            self.lowest_low: Optional[float] = None
        else:
            self.highest_high: Optional[float] = None
            self.lowest_low = entry_price

        # Position state
        self.bars_held = 0
        self.is_open = True

    def update_bar(
        self, high: float, low: float, close: float, bar_index: int, timestamp: datetime
    ) -> Optional[ExitResult]:
        """
        Update position state with new bar data and check for exits.

        This method checks exits in priority order:
        1. Stop loss
        2. Trailing stop (if activated)
        3. Take profit
        4. Time stop

        Args:
            high: Bar high price
            low: Bar low price
            close: Bar close price
            bar_index: Current bar index
            timestamp: Current bar timestamp

        Returns:
            ExitResult if position should close, None if still open.

        Notes:
            - Increments bars_held counter
            - Updates highest_high/lowest_low for trailing stops
            - Checks trailing activation and updates trailing stop price
            - Returns first exit condition that is met
        """
        # Increment bars held
        self.bars_held += 1

        # Update price extremes for trailing stops
        if self.direction == "long":
            self.highest_high = ExitChecker.update_highest_high(self.highest_high, high)
        else:
            self.lowest_low = ExitChecker.update_lowest_low(self.lowest_low, low)

        # Check trailing stop activation and update trailing stop price
        if self.trailing_enabled and not self.trailing_activated:
            self._check_trailing_activation()

        if self.trailing_activated:
            self._update_trailing_stop()

        # Check exits in priority order

        # 1. Stop loss (highest priority)
        if ExitChecker.check_stop_loss(close, self.stop_loss_price, self.direction):
            return self._create_exit_result(
                exit_reason=ExitReason.STOP_LOSS,
                exit_price=self.stop_loss_price,
                bar_index=bar_index,
                timestamp=timestamp,
            )

        # 2. Trailing stop (if activated)
        if self.trailing_activated and self.trailing_stop_price is not None:
            if ExitChecker.check_stop_loss(
                close, self.trailing_stop_price, self.direction
            ):
                return self._create_exit_result(
                    exit_reason=ExitReason.TRAILING_STOP,
                    exit_price=self.trailing_stop_price,
                    bar_index=bar_index,
                    timestamp=timestamp,
                )

        # 3. Take profit
        if ExitChecker.check_take_profit(
            close, self.take_profit_price, self.direction
        ):
            return self._create_exit_result(
                exit_reason=ExitReason.TAKE_PROFIT,
                exit_price=self.take_profit_price,
                bar_index=bar_index,
                timestamp=timestamp,
            )

        # 4. Time stop
        if ExitChecker.check_time_stop(self.bars_held, self.time_stop_bars):
            return self._create_exit_result(
                exit_reason=ExitReason.TIME_STOP,
                exit_price=close,  # Exit at close for time stop
                bar_index=bar_index,
                timestamp=timestamp,
            )

        # No exit condition met
        return None

    def force_close(
        self, close: float, bar_index: int, timestamp: datetime, reason: ExitReason
    ) -> ExitResult:
        """
        Force close the position (e.g., end of run, manual close).

        Args:
            close: Current bar close price
            bar_index: Current bar index
            timestamp: Current bar timestamp
            reason: Exit reason (e.g., END_OF_RUN, MANUAL)

        Returns:
            ExitResult with the forced close details.
        """
        return self._create_exit_result(
            exit_reason=reason,
            exit_price=close,
            bar_index=bar_index,
            timestamp=timestamp,
        )

    def _check_trailing_activation(self) -> None:
        """
        Check if trailing stop should be activated.

        For longs: activates when highest_high >= activation_price
        For shorts: activates when lowest_low <= activation_price

        Updates self.trailing_activated flag.
        """
        if self.exit_spec.trailing_activation_price is None:
            return

        if self.direction == "long":
            self.trailing_activated = ExitChecker.check_trailing_activation_long(
                self.highest_high, self.exit_spec.trailing_activation_price
            )
        else:
            self.trailing_activated = ExitChecker.check_trailing_activation_short(
                self.lowest_low, self.exit_spec.trailing_activation_price
            )

    def _update_trailing_stop(self) -> None:
        """
        Update trailing stop price.

        For longs: trailing_stop = highest_high - trail_distance_atr * ATR
        For shorts: trailing_stop = lowest_low + trail_distance_atr * ATR

        Key invariants:
        - Trailing stop never decreases (for longs) / never increases (for shorts)
        - Trailing stop never crosses entry price
        - Trailing stop always stays within trail_distance of highest_high/lowest_low
        """
        if self.exit_spec.trailing_distance_atr is None:
            return

        if self.direction == "long":
            new_trailing_stop = ExitChecker.calculate_trailing_stop_long(
                self.highest_high,
                self.atr_at_entry,
                self.exit_spec.trailing_distance_atr,
                self.entry_price,
            )

            # Ratchet up: trailing stop never decreases for longs
            if self.trailing_stop_price is None:
                self.trailing_stop_price = new_trailing_stop
            else:
                self.trailing_stop_price = max(self.trailing_stop_price, new_trailing_stop)

        else:  # short
            new_trailing_stop = ExitChecker.calculate_trailing_stop_short(
                self.lowest_low,
                self.atr_at_entry,
                self.exit_spec.trailing_distance_atr,
                self.entry_price,
            )

            # Ratchet down: trailing stop never increases for shorts
            if self.trailing_stop_price is None:
                self.trailing_stop_price = new_trailing_stop
            else:
                self.trailing_stop_price = min(self.trailing_stop_price, new_trailing_stop)

    def _create_exit_result(
        self,
        exit_reason: ExitReason,
        exit_price: float,
        bar_index: int,
        timestamp: datetime,
    ) -> ExitResult:
        """
        Create an ExitResult for this position.

        Args:
            exit_reason: Reason for exit
            exit_price: Exit price
            bar_index: Current bar index
            timestamp: Current bar timestamp

        Returns:
            ExitResult with all relevant information.
        """
        return ExitResult(
            exit_reason=exit_reason,
            exit_price=exit_price,
            bars_held=self.bars_held,
            bar_index=bar_index,
            timestamp=timestamp.isoformat(),
            highest_high=self.highest_high,
            lowest_low=self.lowest_low,
            trailing_was_active=self.trailing_activated,
            trailing_stop_price=self.trailing_stop_price,
        )

    def get_unrealized_pnl(self, current_price: float) -> float:
        """
        Calculate unrealized PnL at current price.

        Args:
            current_price: Current market price

        Returns:
            Unrealized PnL in USD (positive for profit, negative for loss).
        """
        if self.direction == "long":
            pnl_per_unit = current_price - self.entry_price
        else:
            pnl_per_unit = self.entry_price - current_price

        return pnl_per_unit * self.size_units

    def get_unrealized_pnl_pct(self, current_price: float) -> float:
        """
        Calculate unrealized PnL as percentage of entry notional.

        Args:
            current_price: Current market price

        Returns:
            Unrealized PnL as percentage (e.g., 0.05 = 5%).
        """
        unrealized_pnl = self.get_unrealized_pnl(current_price)
        return unrealized_pnl / self.size_usd if self.size_usd > 0 else 0.0

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"Position(id={self.position_id}, symbol={self.symbol}, "
            f"direction={self.direction}, entry={self.entry_price:.2f}, "
            f"bars_held={self.bars_held}, trailing_activated={self.trailing_activated})"
        )
