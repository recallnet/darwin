"""Exit-related classes and data structures for position simulation."""

from dataclasses import dataclass
from typing import Optional

from darwin.schemas.position import ExitReason


@dataclass
class ExitResult:
    """
    Result of an exit check.

    Returned when a position should be closed due to an exit condition being met.
    Contains all information needed to close the position and calculate PnL.
    """

    # Exit details
    exit_reason: ExitReason
    exit_price: float
    bars_held: int

    # Context
    bar_index: int
    timestamp: str  # ISO format

    # Price tracking (for trailing stops)
    highest_high: Optional[float] = None
    lowest_low: Optional[float] = None

    # Optional: trailing stop state at exit
    trailing_was_active: bool = False
    trailing_stop_price: Optional[float] = None

    def __str__(self) -> str:
        """Human-readable string representation."""
        return (
            f"ExitResult(reason={self.exit_reason.value}, "
            f"price={self.exit_price:.2f}, "
            f"bars_held={self.bars_held})"
        )


class ExitChecker:
    """
    Utility class for checking exit conditions.

    Provides helper methods for common exit logic checks.
    This is a stateless utility class.
    """

    @staticmethod
    def check_stop_loss(
        close: float, stop_loss_price: float, direction: str = "long"
    ) -> bool:
        """
        Check if stop loss is hit.

        Args:
            close: Current bar close price
            stop_loss_price: Stop loss price level
            direction: Position direction ('long' or 'short')

        Returns:
            True if stop loss is hit, False otherwise.
        """
        if direction == "long":
            return close <= stop_loss_price
        else:
            return close >= stop_loss_price

    @staticmethod
    def check_take_profit(
        close: float, take_profit_price: float, direction: str = "long"
    ) -> bool:
        """
        Check if take profit is hit.

        Args:
            close: Current bar close price
            take_profit_price: Take profit price level
            direction: Position direction ('long' or 'short')

        Returns:
            True if take profit is hit, False otherwise.
        """
        if direction == "long":
            return close >= take_profit_price
        else:
            return close <= take_profit_price

    @staticmethod
    def check_time_stop(bars_held: int, time_stop_bars: int) -> bool:
        """
        Check if time stop is reached.

        Args:
            bars_held: Number of bars position has been held
            time_stop_bars: Maximum bars to hold position

        Returns:
            True if time stop is reached, False otherwise.
        """
        return bars_held >= time_stop_bars

    @staticmethod
    def update_highest_high(current_highest: float, bar_high: float) -> float:
        """
        Update highest high since entry (for long positions).

        Args:
            current_highest: Current highest high
            bar_high: High of current bar

        Returns:
            Updated highest high.
        """
        return max(current_highest, bar_high)

    @staticmethod
    def update_lowest_low(current_lowest: float, bar_low: float) -> float:
        """
        Update lowest low since entry (for short positions).

        Args:
            current_lowest: Current lowest low
            bar_low: Low of current bar

        Returns:
            Updated lowest low.
        """
        return min(current_lowest, bar_low)

    @staticmethod
    def calculate_trailing_stop_long(
        highest_high: float, atr: float, trail_distance_atr: float, entry_price: float
    ) -> float:
        """
        Calculate trailing stop price for long position.

        Args:
            highest_high: Highest high since entry
            atr: ATR value at entry
            trail_distance_atr: Trail distance in ATR units
            entry_price: Entry price (used as floor)

        Returns:
            Trailing stop price (never below entry price).
        """
        trailing_stop = highest_high - (trail_distance_atr * atr)
        # Ensure trailing stop never goes below entry price
        return max(trailing_stop, entry_price)

    @staticmethod
    def calculate_trailing_stop_short(
        lowest_low: float, atr: float, trail_distance_atr: float, entry_price: float
    ) -> float:
        """
        Calculate trailing stop price for short position.

        Args:
            lowest_low: Lowest low since entry
            atr: ATR value at entry
            trail_distance_atr: Trail distance in ATR units
            entry_price: Entry price (used as ceiling)

        Returns:
            Trailing stop price (never above entry price).
        """
        trailing_stop = lowest_low + (trail_distance_atr * atr)
        # Ensure trailing stop never goes above entry price
        return min(trailing_stop, entry_price)

    @staticmethod
    def check_trailing_activation_long(
        highest_high: float, activation_price: float
    ) -> bool:
        """
        Check if trailing stop should be activated for long position.

        Args:
            highest_high: Highest high since entry
            activation_price: Price level to activate trailing

        Returns:
            True if trailing should be activated, False otherwise.
        """
        return highest_high >= activation_price

    @staticmethod
    def check_trailing_activation_short(
        lowest_low: float, activation_price: float
    ) -> bool:
        """
        Check if trailing stop should be activated for short position.

        Args:
            lowest_low: Lowest low since entry
            activation_price: Price level to activate trailing

        Returns:
            True if trailing should be activated, False otherwise.
        """
        return lowest_low <= activation_price
