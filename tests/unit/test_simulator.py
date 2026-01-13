"""Unit tests for position simulator and exit logic."""

from datetime import datetime, timedelta

import pytest

from darwin.schemas.candidate import ExitSpecV1
from darwin.schemas.position import ExitReason
from darwin.simulator.exits import ExitChecker, ExitResult
from darwin.simulator.position import Position


class TestPosition:
    """Test Position class."""

    def test_position_initialization(self, sample_exit_spec):
        """Test position initialization."""
        position = Position(
            position_id="pos_001",
            symbol="BTC-USD",
            direction="long",
            entry_price=50000.0,
            entry_bar_index=100,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            size_usd=1000.0,
            size_units=0.02,
            entry_fees_usd=6.25,
            atr_at_entry=500.0,
            exit_spec=sample_exit_spec,
        )

        assert position.position_id == "pos_001"
        assert position.entry_price == 50000.0
        assert position.is_open is True
        assert position.bars_held == 0

    def test_stop_loss_hit_long(self, sample_exit_spec):
        """Test stop loss exit for long position."""
        position = Position(
            position_id="pos_001",
            symbol="BTC-USD",
            direction="long",
            entry_price=50000.0,
            entry_bar_index=100,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            size_usd=1000.0,
            size_units=0.02,
            entry_fees_usd=6.25,
            atr_at_entry=500.0,
            exit_spec=sample_exit_spec,
        )

        # Bar that hits stop loss
        exit_result = position.update_bar(
            high=49500.0,
            low=48500.0,  # Below stop loss at 49000
            close=48800.0,
            bar_index=101,
            timestamp=datetime(2024, 1, 1, 12, 15),
        )

        assert exit_result is not None
        assert exit_result.reason == ExitReason.STOP_LOSS
        assert exit_result.exit_price == position.stop_loss_price
        assert not position.is_open

    def test_take_profit_hit_long(self, sample_exit_spec):
        """Test take profit exit for long position."""
        position = Position(
            position_id="pos_001",
            symbol="BTC-USD",
            direction="long",
            entry_price=50000.0,
            entry_bar_index=100,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            size_usd=1000.0,
            size_units=0.02,
            entry_fees_usd=6.25,
            atr_at_entry=500.0,
            exit_spec=sample_exit_spec,
        )

        # Bar that hits take profit
        exit_result = position.update_bar(
            high=52500.0,  # Above take profit at 52000
            low=51500.0,
            close=52200.0,
            bar_index=105,
            timestamp=datetime(2024, 1, 1, 13, 0),
        )

        assert exit_result is not None
        assert exit_result.reason == ExitReason.TAKE_PROFIT
        assert exit_result.exit_price == position.take_profit_price

    def test_time_stop_exit(self, sample_exit_spec):
        """Test time stop exit."""
        position = Position(
            position_id="pos_001",
            symbol="BTC-USD",
            direction="long",
            entry_price=50000.0,
            entry_bar_index=100,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            size_usd=1000.0,
            size_units=0.02,
            entry_fees_usd=6.25,
            atr_at_entry=500.0,
            exit_spec=sample_exit_spec,
        )

        # Update position for 31 bars (no exit)
        for i in range(31):
            exit_result = position.update_bar(
                high=50500.0,
                low=49500.0,
                close=50000.0,
                bar_index=101 + i,
                timestamp=datetime(2024, 1, 1, 12, 15) + timedelta(minutes=15 * i),
            )
            assert exit_result is None

        # 32nd bar: time stop triggers
        exit_result = position.update_bar(
            high=50500.0,
            low=49500.0,
            close=50000.0,
            bar_index=132,
            timestamp=datetime(2024, 1, 1, 20, 0),
        )

        assert exit_result is not None
        assert exit_result.reason == ExitReason.TIME_STOP
        assert exit_result.exit_price == 50000.0  # Close price

    def test_trailing_stop_activation_long(self, sample_exit_spec):
        """Test trailing stop activation for long position."""
        position = Position(
            position_id="pos_001",
            symbol="BTC-USD",
            direction="long",
            entry_price=50000.0,
            entry_bar_index=100,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            size_usd=1000.0,
            size_units=0.02,
            entry_fees_usd=6.25,
            atr_at_entry=500.0,
            exit_spec=sample_exit_spec,
        )

        # Move price up to activation level (51000 from exit_spec)
        position.update_bar(
            high=51500.0,
            low=51000.0,
            close=51200.0,
            bar_index=101,
            timestamp=datetime(2024, 1, 1, 12, 15),
        )

        assert position.trailing_activated is True
        assert position.trailing_stop_price is not None
        assert position.trailing_stop_price < position.highest_high

    def test_trailing_stop_never_decreases(self, sample_exit_spec):
        """Test that trailing stop only ratchets up, never down."""
        position = Position(
            position_id="pos_001",
            symbol="BTC-USD",
            direction="long",
            entry_price=50000.0,
            entry_bar_index=100,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            size_usd=1000.0,
            size_units=0.02,
            entry_fees_usd=6.25,
            atr_at_entry=500.0,
            exit_spec=sample_exit_spec,
        )

        # Activate trailing at high price
        position.update_bar(
            high=52000.0,
            low=51500.0,
            close=51800.0,
            bar_index=101,
            timestamp=datetime(2024, 1, 1, 12, 15),
        )
        initial_trailing = position.trailing_stop_price

        # Price pulls back - trailing should NOT decrease
        position.update_bar(
            high=51000.0,
            low=50500.0,
            close=50800.0,
            bar_index=102,
            timestamp=datetime(2024, 1, 1, 12, 30),
        )

        assert position.trailing_stop_price == initial_trailing
        assert position.is_open

    def test_trailing_stop_triggered(self, sample_exit_spec):
        """Test trailing stop triggering exit."""
        position = Position(
            position_id="pos_001",
            symbol="BTC-USD",
            direction="long",
            entry_price=50000.0,
            entry_bar_index=100,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            size_usd=1000.0,
            size_units=0.02,
            entry_fees_usd=6.25,
            atr_at_entry=500.0,
            exit_spec=sample_exit_spec,
        )

        # Activate trailing
        position.update_bar(
            high=52000.0,
            low=51500.0,
            close=51800.0,
            bar_index=101,
            timestamp=datetime(2024, 1, 1, 12, 15),
        )

        trailing_stop = position.trailing_stop_price

        # Price drops below trailing stop
        exit_result = position.update_bar(
            high=51000.0,
            low=trailing_stop - 100,  # Below trailing stop
            close=trailing_stop - 50,
            bar_index=102,
            timestamp=datetime(2024, 1, 1, 12, 30),
        )

        assert exit_result is not None
        assert exit_result.reason == ExitReason.TRAILING_STOP
        assert exit_result.exit_price == trailing_stop

    def test_exit_priority_stop_loss_before_trailing(self, sample_exit_spec):
        """Test that stop loss has priority over trailing stop."""
        position = Position(
            position_id="pos_001",
            symbol="BTC-USD",
            direction="long",
            entry_price=50000.0,
            entry_bar_index=100,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            size_usd=1000.0,
            size_units=0.02,
            entry_fees_usd=6.25,
            atr_at_entry=500.0,
            exit_spec=sample_exit_spec,
        )

        # Activate trailing
        position.update_bar(
            high=52000.0,
            low=51500.0,
            close=51800.0,
            bar_index=101,
            timestamp=datetime(2024, 1, 1, 12, 15),
        )

        # Bar hits both stop loss and trailing - should exit at stop loss
        exit_result = position.update_bar(
            high=49500.0,
            low=48000.0,  # Below stop loss
            close=48500.0,
            bar_index=102,
            timestamp=datetime(2024, 1, 1, 12, 30),
        )

        assert exit_result is not None
        assert exit_result.reason == ExitReason.STOP_LOSS


class TestPositionShort:
    """Test short position logic."""

    def test_short_stop_loss(self, sample_exit_spec):
        """Test stop loss for short position."""
        # For short, stop loss should be above entry
        exit_spec = ExitSpecV1(
            stop_loss_price=51000.0,  # Above entry
            take_profit_price=48000.0,  # Below entry
            time_stop_bars=32,
            trailing_enabled=True,
            trailing_activation_price=49000.0,
            trailing_distance_atr=1.2,
        )

        position = Position(
            position_id="pos_001",
            symbol="BTC-USD",
            direction="short",
            entry_price=50000.0,
            entry_bar_index=100,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            size_usd=1000.0,
            size_units=0.02,
            entry_fees_usd=6.25,
            atr_at_entry=500.0,
            exit_spec=exit_spec,
        )

        # Bar that hits stop loss
        exit_result = position.update_bar(
            high=51500.0,  # Above stop loss
            low=50500.0,
            close=51200.0,
            bar_index=101,
            timestamp=datetime(2024, 1, 1, 12, 15),
        )

        assert exit_result is not None
        assert exit_result.reason == ExitReason.STOP_LOSS

    def test_short_take_profit(self, sample_exit_spec):
        """Test take profit for short position."""
        exit_spec = ExitSpecV1(
            stop_loss_price=51000.0,
            take_profit_price=48000.0,
            time_stop_bars=32,
            trailing_enabled=True,
            trailing_activation_price=49000.0,
            trailing_distance_atr=1.2,
        )

        position = Position(
            position_id="pos_001",
            symbol="BTC-USD",
            direction="short",
            entry_price=50000.0,
            entry_bar_index=100,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            size_usd=1000.0,
            size_units=0.02,
            entry_fees_usd=6.25,
            atr_at_entry=500.0,
            exit_spec=exit_spec,
        )

        # Bar that hits take profit
        exit_result = position.update_bar(
            high=48500.0,
            low=47500.0,  # Below take profit
            close=48200.0,
            bar_index=105,
            timestamp=datetime(2024, 1, 1, 13, 0),
        )

        assert exit_result is not None
        assert exit_result.reason == ExitReason.TAKE_PROFIT


class TestExitChecker:
    """Test ExitChecker utility."""

    def test_check_stop_loss_long(self):
        """Test stop loss check for long."""
        result = ExitChecker.check_stop_loss(
            direction="long",
            low=48500.0,
            stop_loss_price=49000.0,
        )
        assert result is not None
        assert result.reason == ExitReason.STOP_LOSS

    def test_check_stop_loss_not_hit(self):
        """Test stop loss not hit."""
        result = ExitChecker.check_stop_loss(
            direction="long",
            low=49500.0,
            stop_loss_price=49000.0,
        )
        assert result is None

    def test_check_take_profit_long(self):
        """Test take profit check for long."""
        result = ExitChecker.check_take_profit(
            direction="long",
            high=52500.0,
            take_profit_price=52000.0,
        )
        assert result is not None
        assert result.reason == ExitReason.TAKE_PROFIT

    def test_check_time_stop(self):
        """Test time stop check."""
        result = ExitChecker.check_time_stop(
            bars_held=32,
            time_stop_bars=32,
            current_close=50000.0,
        )
        assert result is not None
        assert result.reason == ExitReason.TIME_STOP


class TestPositionTracking:
    """Test position tracking fields."""

    def test_bars_held_increments(self, sample_exit_spec):
        """Test that bars_held increments correctly."""
        position = Position(
            position_id="pos_001",
            symbol="BTC-USD",
            direction="long",
            entry_price=50000.0,
            entry_bar_index=100,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            size_usd=1000.0,
            size_units=0.02,
            entry_fees_usd=6.25,
            atr_at_entry=500.0,
            exit_spec=sample_exit_spec,
        )

        for i in range(5):
            position.update_bar(
                high=50500.0,
                low=49500.0,
                close=50000.0,
                bar_index=101 + i,
                timestamp=datetime(2024, 1, 1, 12, 15) + timedelta(minutes=15 * i),
            )

        assert position.bars_held == 5

    def test_highest_high_tracking(self, sample_exit_spec):
        """Test highest high tracking for long position."""
        position = Position(
            position_id="pos_001",
            symbol="BTC-USD",
            direction="long",
            entry_price=50000.0,
            entry_bar_index=100,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            size_usd=1000.0,
            size_units=0.02,
            entry_fees_usd=6.25,
            atr_at_entry=500.0,
            exit_spec=sample_exit_spec,
        )

        # Update with increasing highs
        highs = [50500.0, 51000.0, 52000.0, 51500.0, 53000.0]
        for i, high in enumerate(highs):
            position.update_bar(
                high=high,
                low=high - 500,
                close=high - 250,
                bar_index=101 + i,
                timestamp=datetime(2024, 1, 1, 12, 15) + timedelta(minutes=15 * i),
            )

        assert position.highest_high == 53000.0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exit_at_exact_stop_loss(self, sample_exit_spec):
        """Test exit when low exactly equals stop loss."""
        position = Position(
            position_id="pos_001",
            symbol="BTC-USD",
            direction="long",
            entry_price=50000.0,
            entry_bar_index=100,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            size_usd=1000.0,
            size_units=0.02,
            entry_fees_usd=6.25,
            atr_at_entry=500.0,
            exit_spec=sample_exit_spec,
        )

        exit_result = position.update_bar(
            high=49500.0,
            low=49000.0,  # Exactly at stop loss
            close=49200.0,
            bar_index=101,
            timestamp=datetime(2024, 1, 1, 12, 15),
        )

        assert exit_result is not None
        assert exit_result.reason == ExitReason.STOP_LOSS

    def test_no_exit_when_disabled(self):
        """Test that disabled exits don't trigger."""
        exit_spec = ExitSpecV1(
            stop_loss_price=49000.0,
            take_profit_price=52000.0,
            time_stop_bars=32,
            trailing_enabled=False,  # Trailing disabled
            trailing_activation_price=51000.0,
            trailing_distance_atr=1.2,
        )

        position = Position(
            position_id="pos_001",
            symbol="BTC-USD",
            direction="long",
            entry_price=50000.0,
            entry_bar_index=100,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            size_usd=1000.0,
            size_units=0.02,
            entry_fees_usd=6.25,
            atr_at_entry=500.0,
            exit_spec=exit_spec,
        )

        # Move to trailing activation price - should NOT activate
        position.update_bar(
            high=52000.0,
            low=51500.0,
            close=51800.0,
            bar_index=101,
            timestamp=datetime(2024, 1, 1, 12, 15),
        )

        assert position.trailing_activated is False
        assert position.trailing_stop_price is None
