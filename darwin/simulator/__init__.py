"""
Darwin simulator module.

Provides position simulation with comprehensive exit logic including trailing stops.

Main components:
- Position: Tracks a single open position with all exit conditions
- PositionManager: Manages multiple positions with entry/exit simulation
- ExitResult: Exit event data structure
- ExitChecker: Utility class for exit condition checks

Usage:
    from darwin.simulator import Position, PositionManager, ExitResult
    from darwin.storage import PositionLedgerSQLite

    # Create ledger and manager
    ledger = PositionLedgerSQLite("artifacts/ledger/positions.sqlite")
    manager = PositionManager(ledger, run_id="test_run")

    # Open position
    position_id = manager.open_position(
        candidate_id="cand_123",
        symbol="BTC-USD",
        direction="long",
        signal_price=45000.0,
        next_open=45100.0,
        bar_index=0,
        timestamp=datetime.now(),
        size_usd=1000.0,
        atr_at_entry=500.0,
        exit_spec=exit_spec,
    )

    # Update positions each bar
    closed = manager.update_positions(
        high=46000.0,
        low=44500.0,
        close=45800.0,
        bar_index=1,
        timestamp=datetime.now(),
    )

    # Close all at end
    manager.close_all_positions(close=45000.0, bar_index=100, timestamp=datetime.now())
"""

from darwin.simulator.exits import ExitChecker, ExitResult
from darwin.simulator.position import Position
from darwin.simulator.position_manager import PositionManager

__all__ = [
    "Position",
    "PositionManager",
    "ExitResult",
    "ExitChecker",
]
