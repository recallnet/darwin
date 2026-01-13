"""
Incremental indicator implementations for feature pipeline.

All indicators maintain internal state and update incrementally (O(1) operations).
Designed for online processing of OHLCV bars.
"""

from collections import deque
from typing import Optional
import math


class RollingWindow:
    """
    Efficient fixed-size buffer for rolling window calculations.

    Maintains a circular buffer and computes sum, mean, std efficiently.
    """

    def __init__(self, size: int):
        """
        Initialize rolling window.

        Args:
            size: Window size (number of values to keep)
        """
        if size <= 0:
            raise ValueError("Window size must be positive")

        self.size = size
        self.buffer: deque[float] = deque(maxlen=size)
        self._sum = 0.0
        self._sum_sq = 0.0

    def update(self, value: float) -> None:
        """Add new value to window, removing oldest if full."""
        if len(self.buffer) == self.size:
            # Remove oldest value from sums
            oldest = self.buffer[0]
            self._sum -= oldest
            self._sum_sq -= oldest * oldest

        # Add new value
        self.buffer.append(value)
        self._sum += value
        self._sum_sq += value * value

    def mean(self) -> float:
        """Get mean of values in window."""
        if not self.buffer:
            return 0.0
        return self._sum / len(self.buffer)

    def std(self) -> float:
        """Get standard deviation of values in window."""
        if len(self.buffer) < 2:
            return 0.0

        n = len(self.buffer)
        variance = (self._sum_sq / n) - (self._sum / n) ** 2

        # Handle numerical precision issues
        if variance < 0:
            variance = 0.0

        return math.sqrt(variance)

    def sum(self) -> float:
        """Get sum of values in window."""
        return self._sum

    def max(self) -> float:
        """Get maximum value in window."""
        if not self.buffer:
            return 0.0
        return max(self.buffer)

    def min(self) -> float:
        """Get minimum value in window."""
        if not self.buffer:
            return 0.0
        return min(self.buffer)

    def is_full(self) -> bool:
        """Check if window has reached full size."""
        return len(self.buffer) == self.size

    def __len__(self) -> int:
        """Get current number of values in window."""
        return len(self.buffer)

    def get_buffer(self) -> list[float]:
        """Get copy of buffer as list."""
        return list(self.buffer)


class EMAState:
    """
    Exponential Moving Average with incremental updates.

    Uses standard EMA formula: EMA[t] = α * price + (1-α) * EMA[t-1]
    where α = 2 / (period + 1)
    """

    def __init__(self, period: int):
        """
        Initialize EMA state.

        Args:
            period: EMA period (e.g., 20 for EMA20)
        """
        if period <= 0:
            raise ValueError("Period must be positive")

        self.period = period
        self.alpha = 2.0 / (period + 1)
        self.value: Optional[float] = None
        self.initialized = False

    def update(self, price: float) -> float:
        """
        Update EMA with new price.

        Args:
            price: New price value

        Returns:
            Current EMA value
        """
        if not self.initialized:
            self.value = price
            self.initialized = True
        else:
            self.value = self.alpha * price + (1 - self.alpha) * self.value

        return self.value

    def get(self) -> float:
        """Get current EMA value."""
        return self.value if self.value is not None else 0.0


class WilderEMAState:
    """
    Wilder's smoothing (modified EMA used in RSI, ATR, ADX).

    Formula: Wilder[t] = (Wilder[t-1] * (period-1) + value) / period
    Equivalent to EMA with α = 1/period
    """

    def __init__(self, period: int):
        """
        Initialize Wilder EMA state.

        Args:
            period: Smoothing period (e.g., 14 for RSI14)
        """
        if period <= 0:
            raise ValueError("Period must be positive")

        self.period = period
        self.alpha = 1.0 / period
        self.value: Optional[float] = None
        self.initialized = False

    def update(self, value: float) -> float:
        """
        Update Wilder EMA with new value.

        Args:
            value: New value

        Returns:
            Current smoothed value
        """
        if not self.initialized:
            self.value = value
            self.initialized = True
        else:
            # Wilder formula: (prev * (n-1) + value) / n
            # Equivalent to: prev + α * (value - prev) where α = 1/n
            self.value = self.value + self.alpha * (value - self.value)

        return self.value

    def get(self) -> float:
        """Get current smoothed value."""
        return self.value if self.value is not None else 0.0


class ATRState:
    """
    Average True Range (ATR) with incremental updates.

    Uses Wilder's smoothing over True Range values.
    """

    def __init__(self, period: int = 14):
        """
        Initialize ATR state.

        Args:
            period: ATR period (default 14)
        """
        self.period = period
        self.wilder = WilderEMAState(period)
        self.prev_close: Optional[float] = None

    def update(self, high: float, low: float, close: float) -> float:
        """
        Update ATR with new bar.

        Args:
            high: Bar high
            low: Bar low
            close: Bar close

        Returns:
            Current ATR value
        """
        # Calculate True Range
        if self.prev_close is None:
            # First bar: TR = high - low
            tr = high - low
        else:
            # TR = max(high-low, |high-prev_close|, |low-prev_close|)
            tr = max(
                high - low,
                abs(high - self.prev_close),
                abs(low - self.prev_close)
            )

        self.prev_close = close

        # Update Wilder EMA of TR
        return self.wilder.update(tr)

    def get(self) -> float:
        """Get current ATR value."""
        return self.wilder.get()


class ADXState:
    """
    Average Directional Index (ADX) with +DI and -DI.

    Uses Wilder's smoothing throughout.
    """

    def __init__(self, period: int = 14):
        """
        Initialize ADX state.

        Args:
            period: ADX period (default 14)
        """
        self.period = period

        # Wilder smoothing for TR, +DM, -DM
        self.tr_smooth = WilderEMAState(period)
        self.plus_dm_smooth = WilderEMAState(period)
        self.minus_dm_smooth = WilderEMAState(period)

        # Wilder smoothing for DX -> ADX
        self.adx_smooth = WilderEMAState(period)

        self.prev_high: Optional[float] = None
        self.prev_low: Optional[float] = None
        self.prev_close: Optional[float] = None

        self.adx = 0.0
        self.di_plus = 0.0
        self.di_minus = 0.0

    def update(self, high: float, low: float, close: float) -> tuple[float, float, float]:
        """
        Update ADX with new bar.

        Args:
            high: Bar high
            low: Bar low
            close: Bar close

        Returns:
            Tuple of (adx, +DI, -DI)
        """
        if self.prev_high is None:
            # First bar: initialize but don't compute
            self.prev_high = high
            self.prev_low = low
            self.prev_close = close

            # Initialize with simple range
            tr = high - low
            self.tr_smooth.update(tr)
            self.plus_dm_smooth.update(0.0)
            self.minus_dm_smooth.update(0.0)

            return 0.0, 0.0, 0.0

        # Calculate True Range
        tr = max(
            high - low,
            abs(high - self.prev_close),
            abs(low - self.prev_close)
        )

        # Calculate Directional Movement
        up_move = high - self.prev_high
        down_move = self.prev_low - low

        plus_dm = 0.0
        minus_dm = 0.0

        if up_move > down_move and up_move > 0:
            plus_dm = up_move

        if down_move > up_move and down_move > 0:
            minus_dm = down_move

        # Update smoothed values
        tr_smoothed = self.tr_smooth.update(tr)
        plus_dm_smoothed = self.plus_dm_smooth.update(plus_dm)
        minus_dm_smoothed = self.minus_dm_smooth.update(minus_dm)

        # Calculate Directional Indicators
        if tr_smoothed > 1e-12:
            self.di_plus = 100.0 * plus_dm_smoothed / tr_smoothed
            self.di_minus = 100.0 * minus_dm_smoothed / tr_smoothed
        else:
            self.di_plus = 0.0
            self.di_minus = 0.0

        # Calculate DX
        di_sum = self.di_plus + self.di_minus
        if di_sum > 1e-12:
            dx = 100.0 * abs(self.di_plus - self.di_minus) / di_sum
        else:
            dx = 0.0

        # Smooth DX to get ADX
        self.adx = self.adx_smooth.update(dx)

        # Update previous values
        self.prev_high = high
        self.prev_low = low
        self.prev_close = close

        return self.adx, self.di_plus, self.di_minus

    def get(self) -> tuple[float, float, float]:
        """Get current (ADX, +DI, -DI) values."""
        return self.adx, self.di_plus, self.di_minus


class RSIState:
    """
    Relative Strength Index (RSI) with Wilder's smoothing.

    Uses separate Wilder EMAs for gains and losses.
    """

    def __init__(self, period: int = 14):
        """
        Initialize RSI state.

        Args:
            period: RSI period (default 14)
        """
        self.period = period
        self.gain_smooth = WilderEMAState(period)
        self.loss_smooth = WilderEMAState(period)
        self.prev_close: Optional[float] = None
        self.rsi = 50.0

    def update(self, close: float) -> float:
        """
        Update RSI with new close price.

        Args:
            close: Bar close price

        Returns:
            Current RSI value (0-100)
        """
        if self.prev_close is None:
            self.prev_close = close
            # Initialize with zero gain/loss
            self.gain_smooth.update(0.0)
            self.loss_smooth.update(0.0)
            return 50.0

        # Calculate price change
        change = close - self.prev_close

        # Separate into gain and loss
        gain = max(change, 0.0)
        loss = max(-change, 0.0)

        # Update smoothed gain and loss
        avg_gain = self.gain_smooth.update(gain)
        avg_loss = self.loss_smooth.update(loss)

        # Calculate RSI
        if avg_loss < 1e-12:
            self.rsi = 100.0 if avg_gain > 1e-12 else 50.0
        else:
            rs = avg_gain / avg_loss
            self.rsi = 100.0 - (100.0 / (1.0 + rs))

        self.prev_close = close

        return self.rsi

    def get(self) -> float:
        """Get current RSI value."""
        return self.rsi


class MACDState:
    """
    MACD (Moving Average Convergence Divergence).

    MACD line = EMA12 - EMA26
    Signal line = EMA9 of MACD line
    Histogram = MACD line - Signal line
    """

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        """
        Initialize MACD state.

        Args:
            fast: Fast EMA period (default 12)
            slow: Slow EMA period (default 26)
            signal: Signal line period (default 9)
        """
        self.ema_fast = EMAState(fast)
        self.ema_slow = EMAState(slow)
        self.ema_signal = EMAState(signal)

        self.macd = 0.0
        self.signal_line = 0.0
        self.histogram = 0.0

    def update(self, close: float) -> tuple[float, float, float]:
        """
        Update MACD with new close price.

        Args:
            close: Bar close price

        Returns:
            Tuple of (macd_line, signal_line, histogram)
        """
        # Update EMAs
        fast = self.ema_fast.update(close)
        slow = self.ema_slow.update(close)

        # Calculate MACD line
        self.macd = fast - slow

        # Update signal line (EMA of MACD)
        self.signal_line = self.ema_signal.update(self.macd)

        # Calculate histogram
        self.histogram = self.macd - self.signal_line

        return self.macd, self.signal_line, self.histogram

    def get(self) -> tuple[float, float, float]:
        """Get current (MACD, signal, histogram) values."""
        return self.macd, self.signal_line, self.histogram


class BollingerBandsState:
    """
    Bollinger Bands with mid (SMA), upper, lower bands.

    Also computes width and position metrics.
    """

    def __init__(self, period: int = 20, num_std: float = 2.0):
        """
        Initialize Bollinger Bands state.

        Args:
            period: SMA period (default 20)
            num_std: Number of standard deviations for bands (default 2.0)
        """
        self.period = period
        self.num_std = num_std
        self.window = RollingWindow(period)

        self.mid = 0.0
        self.upper = 0.0
        self.lower = 0.0
        self.width = 0.0
        self.position = 0.5  # Position within bands (0=lower, 1=upper)

    def update(self, close: float) -> tuple[float, float, float]:
        """
        Update Bollinger Bands with new close price.

        Args:
            close: Bar close price

        Returns:
            Tuple of (upper, mid, lower)
        """
        self.window.update(close)

        if not self.window.is_full():
            # Not enough data yet
            self.mid = close
            self.upper = close
            self.lower = close
            self.width = 0.0
            self.position = 0.5
            return self.upper, self.mid, self.lower

        # Calculate bands
        self.mid = self.window.mean()
        std = self.window.std()

        self.upper = self.mid + self.num_std * std
        self.lower = self.mid - self.num_std * std

        # Calculate width (as fraction of price)
        if abs(close) > 1e-12:
            self.width = (self.upper - self.lower) / close
        else:
            self.width = 0.0

        # Calculate position within bands
        band_range = self.upper - self.lower
        if band_range > 1e-12:
            self.position = (close - self.lower) / band_range
        else:
            self.position = 0.5

        return self.upper, self.mid, self.lower

    def get(self) -> tuple[float, float, float]:
        """Get current (upper, mid, lower) band values."""
        return self.upper, self.mid, self.lower

    def get_width(self) -> float:
        """Get current band width as fraction of price."""
        return self.width

    def get_position(self) -> float:
        """Get current position within bands (0=lower, 1=upper)."""
        return self.position


class DonchianState:
    """
    Donchian Channels (highest high and lowest low over period).

    Excludes current bar from calculation.
    """

    def __init__(self, period: int = 32):
        """
        Initialize Donchian channels state.

        Args:
            period: Lookback period (default 32)
        """
        self.period = period
        self.highs = RollingWindow(period)
        self.lows = RollingWindow(period)

        self.upper = 0.0
        self.lower = 0.0

        # Need to track previous bar's values since we exclude current bar
        self.prev_high: Optional[float] = None
        self.prev_low: Optional[float] = None

    def update(self, high: float, low: float) -> tuple[float, float]:
        """
        Update Donchian channels with new bar.

        Args:
            high: Bar high
            low: Bar low

        Returns:
            Tuple of (upper_channel, lower_channel)
        """
        # Add previous bar's values to window (exclude current bar)
        if self.prev_high is not None:
            self.highs.update(self.prev_high)
            self.lows.update(self.prev_low)

        # Calculate channels from window
        if len(self.highs) > 0:
            self.upper = self.highs.max()
            self.lower = self.lows.min()
        else:
            self.upper = high
            self.lower = low

        # Store current bar for next update
        self.prev_high = high
        self.prev_low = low

        return self.upper, self.lower

    def get(self) -> tuple[float, float]:
        """Get current (upper, lower) channel values."""
        return self.upper, self.lower
