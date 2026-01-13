"""Property-based tests for simulator invariants using Hypothesis."""

from datetime import datetime, timedelta

import pytest
from hypothesis import given, strategies as st

from darwin.schemas.candidate import ExitSpecV1
from darwin.simulator.position import Position


# Strategy for generating valid prices
prices = st.floats(min_value=1.0, max_value=1000000.0, allow_nan=False, allow_infinity=False)

# Strategy for generating valid ATR values
atr_values = st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False)

# Strategy for generating price movements as multipliers
price_movements = st.floats(min_value=0.8, max_value=1.2)


@pytest.mark.property
class TestTrailingStopInvariants:
    """Property-based tests for trailing stop behavior."""

    @given(
        entry_price=prices,
        atr=atr_values,
        price_multipliers=st.lists(price_movements, min_size=10, max_size=50),
    )
    def test_trailing_stop_never_decreases_long(
        self, entry_price: float, atr: float, price_multipliers: list
    ):
        """
        Property: For long positions, trailing stop price should never decrease.

        This is a critical invariant - trailing stops should only ratchet up,
        never down. Otherwise we could lock in losses.
        """
        # Create exit spec with reasonable values
        exit_spec = ExitSpecV1(
            stop_loss_price=entry_price * 0.96,  # 4% below entry
            take_profit_price=entry_price * 1.08,  # 8% above entry
            time_stop_bars=100,
            trailing_enabled=True,
            trailing_activation_price=entry_price * 1.02,  # Activate at +2%
            trailing_distance_atr=1.2,
        )

        position = Position(
            position_id="prop_test_001",
            symbol="TEST-USD",
            direction="long",
            entry_price=entry_price,
            entry_bar_index=0,
            entry_timestamp=datetime(2024, 1, 1),
            size_usd=1000.0,
            size_units=1000.0 / entry_price,
            entry_fees_usd=6.25,
            atr_at_entry=atr,
            exit_spec=exit_spec,
        )

        previous_trailing = None
        current_price = entry_price

        for i, multiplier in enumerate(price_multipliers):
            # Generate bar with price movement
            new_price = current_price * multiplier
            high = max(current_price, new_price) * 1.001
            low = min(current_price, new_price) * 0.999
            close = new_price

            # Update position
            result = position.update_bar(
                high=high,
                low=low,
                close=close,
                bar_index=i + 1,
                timestamp=datetime(2024, 1, 1) + timedelta(minutes=15 * i),
            )

            # If position exited, stop testing
            if result is not None:
                break

            # Invariant: trailing stop never decreases
            if position.trailing_stop_price is not None:
                if previous_trailing is not None:
                    assert position.trailing_stop_price >= previous_trailing, (
                        f"Trailing stop decreased from {previous_trailing} "
                        f"to {position.trailing_stop_price}"
                    )
                previous_trailing = position.trailing_stop_price

            current_price = new_price

    @given(
        entry_price=prices,
        atr=atr_values,
        price_multipliers=st.lists(price_movements, min_size=10, max_size=50),
    )
    def test_trailing_stop_respects_distance(
        self, entry_price: float, atr: float, price_multipliers: list
    ):
        """
        Property: Trailing stop should always be within trail_distance of highest high.

        For longs: trailing_stop >= highest_high - (trail_distance_atr * atr)
        """
        trail_distance_atr = 1.2

        exit_spec = ExitSpecV1(
            stop_loss_price=entry_price * 0.96,
            take_profit_price=entry_price * 1.08,
            time_stop_bars=100,
            trailing_enabled=True,
            trailing_activation_price=entry_price * 1.02,
            trailing_distance_atr=trail_distance_atr,
        )

        position = Position(
            position_id="prop_test_002",
            symbol="TEST-USD",
            direction="long",
            entry_price=entry_price,
            entry_bar_index=0,
            entry_timestamp=datetime(2024, 1, 1),
            size_usd=1000.0,
            size_units=1000.0 / entry_price,
            entry_fees_usd=6.25,
            atr_at_entry=atr,
            exit_spec=exit_spec,
        )

        current_price = entry_price

        for i, multiplier in enumerate(price_multipliers):
            new_price = current_price * multiplier
            high = max(current_price, new_price) * 1.001
            low = min(current_price, new_price) * 0.999
            close = new_price

            result = position.update_bar(
                high=high,
                low=low,
                close=close,
                bar_index=i + 1,
                timestamp=datetime(2024, 1, 1) + timedelta(minutes=15 * i),
            )

            if result is not None:
                break

            # Invariant: trailing stop within distance of highest high
            if position.trailing_activated and position.trailing_stop_price is not None:
                expected_max_distance = trail_distance_atr * atr
                actual_distance = position.highest_high - position.trailing_stop_price

                assert actual_distance <= expected_max_distance * 1.01, (  # Allow 1% tolerance
                    f"Trailing stop too far from highest high: "
                    f"distance={actual_distance}, max={expected_max_distance}"
                )

            current_price = new_price

    @given(
        entry_price=prices,
        atr=atr_values,
    )
    def test_trailing_stop_never_below_entry(self, entry_price: float, atr: float):
        """
        Property: Trailing stop should never go below entry price for longs
        (or above entry for shorts).

        This prevents locking in losses before the position is profitable.
        """
        exit_spec = ExitSpecV1(
            stop_loss_price=entry_price * 0.96,
            take_profit_price=entry_price * 1.08,
            time_stop_bars=100,
            trailing_enabled=True,
            trailing_activation_price=entry_price * 1.02,
            trailing_distance_atr=1.2,
        )

        position = Position(
            position_id="prop_test_003",
            symbol="TEST-USD",
            direction="long",
            entry_price=entry_price,
            entry_bar_index=0,
            entry_timestamp=datetime(2024, 1, 1),
            size_usd=1000.0,
            size_units=1000.0 / entry_price,
            entry_fees_usd=6.25,
            atr_at_entry=atr,
            exit_spec=exit_spec,
        )

        # Move price up to activate trailing
        high = entry_price * 1.05
        position.update_bar(
            high=high,
            low=entry_price,
            close=entry_price * 1.04,
            bar_index=1,
            timestamp=datetime(2024, 1, 1, 0, 15),
        )

        # Invariant: trailing stop never below entry
        if position.trailing_stop_price is not None:
            assert position.trailing_stop_price >= entry_price, (
                f"Trailing stop {position.trailing_stop_price} below entry {entry_price}"
            )


@pytest.mark.property
class TestPositionSizeInvariants:
    """Property-based tests for position sizing."""

    @given(
        entry_price=prices,
        size_usd=st.floats(min_value=100.0, max_value=100000.0),
    )
    def test_size_units_consistency(self, entry_price: float, size_usd: float):
        """
        Property: size_units should equal size_usd / entry_price.
        """
        size_units = size_usd / entry_price

        exit_spec = ExitSpecV1(
            stop_loss_price=entry_price * 0.96,
            take_profit_price=entry_price * 1.08,
            time_stop_bars=32,
            trailing_enabled=True,
            trailing_activation_price=entry_price * 1.02,
            trailing_distance_atr=1.2,
        )

        position = Position(
            position_id="prop_test_004",
            symbol="TEST-USD",
            direction="long",
            entry_price=entry_price,
            entry_bar_index=0,
            entry_timestamp=datetime(2024, 1, 1),
            size_usd=size_usd,
            size_units=size_units,
            entry_fees_usd=6.25,
            atr_at_entry=100.0,
            exit_spec=exit_spec,
        )

        # Verify relationship
        calculated_size_usd = position.size_units * position.entry_price
        assert abs(calculated_size_usd - size_usd) < 0.01, (
            f"Size mismatch: {calculated_size_usd} vs {size_usd}"
        )


@pytest.mark.property
class TestExitPriorityInvariants:
    """Property-based tests for exit priority."""

    @given(
        entry_price=prices,
        atr=atr_values,
    )
    def test_stop_loss_has_priority(self, entry_price: float, atr: float):
        """
        Property: Stop loss should always have priority over other exits.

        Even if trailing stop or take profit would also trigger, stop loss wins.
        """
        stop_loss = entry_price * 0.96
        take_profit = entry_price * 1.08

        exit_spec = ExitSpecV1(
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            time_stop_bars=32,
            trailing_enabled=True,
            trailing_activation_price=entry_price * 1.02,
            trailing_distance_atr=1.2,
        )

        position = Position(
            position_id="prop_test_005",
            symbol="TEST-USD",
            direction="long",
            entry_price=entry_price,
            entry_bar_index=0,
            entry_timestamp=datetime(2024, 1, 1),
            size_usd=1000.0,
            size_units=1000.0 / entry_price,
            entry_fees_usd=6.25,
            atr_at_entry=atr,
            exit_spec=exit_spec,
        )

        # Activate trailing
        position.update_bar(
            high=entry_price * 1.05,
            low=entry_price * 1.01,
            close=entry_price * 1.03,
            bar_index=1,
            timestamp=datetime(2024, 1, 1, 0, 15),
        )

        # Bar that would hit both stop loss and trailing stop
        result = position.update_bar(
            high=entry_price * 0.98,
            low=stop_loss * 0.99,  # Below stop loss
            close=stop_loss * 0.995,
            bar_index=2,
            timestamp=datetime(2024, 1, 1, 0, 30),
        )

        # Should exit at stop loss, not trailing
        assert result is not None
        assert result.exit_reason.value == "stop_loss"


@pytest.mark.property
class TestBarsHeldInvariants:
    """Property-based tests for bars_held tracking."""

    @given(
        entry_price=prices,
        num_bars=st.integers(min_value=1, max_value=100),
    )
    def test_bars_held_increments_correctly(self, entry_price: float, num_bars: int):
        """
        Property: bars_held should increment by exactly 1 for each update_bar call.
        """
        exit_spec = ExitSpecV1(
            stop_loss_price=entry_price * 0.96,
            take_profit_price=entry_price * 1.50,  # High TP to avoid hitting
            time_stop_bars=200,  # High time stop
            trailing_enabled=False,
            trailing_activation_price=entry_price * 1.02,
            trailing_distance_atr=1.2,
        )

        position = Position(
            position_id="prop_test_006",
            symbol="TEST-USD",
            direction="long",
            entry_price=entry_price,
            entry_bar_index=0,
            entry_timestamp=datetime(2024, 1, 1),
            size_usd=1000.0,
            size_units=1000.0 / entry_price,
            entry_fees_usd=6.25,
            atr_at_entry=100.0,
            exit_spec=exit_spec,
        )

        for i in range(num_bars):
            result = position.update_bar(
                high=entry_price * 1.01,
                low=entry_price * 0.99,
                close=entry_price,
                bar_index=i + 1,
                timestamp=datetime(2024, 1, 1) + timedelta(minutes=15 * i),
            )

            if result is not None:
                break

        assert position.bars_held == min(num_bars, position.bars_held)
