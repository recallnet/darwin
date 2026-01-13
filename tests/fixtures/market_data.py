"""Synthetic market data generators for testing.

These generators create realistic OHLCV data for various market scenarios
without requiring actual market data. This enables fast, reproducible tests.
"""

from datetime import datetime, timedelta
from typing import List, Literal, Optional

import numpy as np
import pandas as pd


def generate_synthetic_ohlcv(
    bars: int = 1000,
    base_price: float = 100.0,
    volatility: float = 0.02,
    trend: float = 0.0001,
    seed: int = 42,
    start_time: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data using geometric Brownian motion.

    Args:
        bars: Number of bars to generate
        base_price: Starting price
        volatility: Daily volatility (e.g., 0.02 = 2%)
        trend: Drift per bar (e.g., 0.0001 = 0.01% per bar)
        seed: Random seed for reproducibility
        start_time: Starting timestamp (defaults to 2024-01-01)

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    if start_time is None:
        start_time = datetime(2024, 1, 1)

    np.random.seed(seed)

    # Generate log returns using geometric Brownian motion
    returns = np.random.normal(trend, volatility / np.sqrt(96), bars)

    # Cumulative price path
    log_prices = np.log(base_price) + np.cumsum(returns)
    close_prices = np.exp(log_prices)

    ohlcv_data = []
    for i, close in enumerate(close_prices):
        timestamp = start_time + timedelta(minutes=15 * i)

        # Generate realistic intrabar high/low
        intrabar_range = abs(np.random.normal(0, volatility / 4))
        high = close * (1 + intrabar_range)
        low = close * (1 - intrabar_range)

        # Open is previous close (or base_price for first bar)
        open_price = close_prices[i - 1] if i > 0 else base_price

        # Ensure OHLC relationships are valid
        high = max(high, open_price, close)
        low = min(low, open_price, close)

        # Generate realistic volume
        volume = abs(np.random.normal(1e6, 2e5))

        ohlcv_data.append(
            {
                "timestamp": timestamp,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )

    return pd.DataFrame(ohlcv_data)


def generate_trending_market(
    bars: int = 500,
    base_price: float = 50000.0,
    trend_strength: Literal["weak", "moderate", "strong"] = "moderate",
    direction: Literal["up", "down"] = "up",
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate a trending market scenario.

    Args:
        bars: Number of bars
        base_price: Starting price
        trend_strength: Strength of trend (weak/moderate/strong)
        direction: Direction of trend (up/down)
        seed: Random seed

    Returns:
        DataFrame with OHLCV data showing consistent trend
    """
    trend_multipliers = {"weak": 0.0002, "moderate": 0.0005, "strong": 0.001}
    trend = trend_multipliers[trend_strength]

    if direction == "down":
        trend = -trend

    return generate_synthetic_ohlcv(
        bars=bars, base_price=base_price, volatility=0.015, trend=trend, seed=seed
    )


def generate_ranging_market(
    bars: int = 500, base_price: float = 50000.0, range_pct: float = 0.05, seed: int = 42
) -> pd.DataFrame:
    """
    Generate a ranging (sideways) market scenario.

    Args:
        bars: Number of bars
        base_price: Center price of range
        range_pct: Range width as percentage (e.g., 0.05 = 5%)
        seed: Random seed

    Returns:
        DataFrame with OHLCV data showing range-bound price action
    """
    np.random.seed(seed)

    range_high = base_price * (1 + range_pct / 2)
    range_low = base_price * (1 - range_pct / 2)

    ohlcv_data = []
    current_price = base_price

    for i in range(bars):
        timestamp = datetime(2024, 1, 1) + timedelta(minutes=15 * i)

        # Mean reversion: pull price back toward center
        distance_from_center = (current_price - base_price) / base_price
        mean_reversion = -distance_from_center * 0.1

        # Add noise
        noise = np.random.randn() * 0.002

        # Calculate close
        price_change = mean_reversion + noise
        close = current_price * (1 + price_change)

        # Ensure price stays within range
        close = np.clip(close, range_low, range_high)

        # Generate OHLC
        open_price = current_price
        intrabar_range = abs(np.random.normal(0, 0.003))
        high = min(close * (1 + intrabar_range), range_high)
        low = max(close * (1 - intrabar_range), range_low)

        high = max(high, open_price, close)
        low = min(low, open_price, close)

        volume = abs(np.random.normal(8e5, 1e5))  # Lower volume in ranging markets

        ohlcv_data.append(
            {
                "timestamp": timestamp,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )

        current_price = close

    return pd.DataFrame(ohlcv_data)


def generate_breakout_scenario(
    warmup_bars: int = 200,
    breakout_bar: int = 200,
    post_breakout_bars: int = 100,
    base_price: float = 50000.0,
    breakout_magnitude: float = 0.10,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate a breakout scenario for testing breakout playbook.

    Scenario:
    1. Compression phase (low volatility ranging)
    2. Breakout with volume spike
    3. Continuation after breakout

    Args:
        warmup_bars: Number of bars before breakout
        breakout_bar: Bar index where breakout occurs
        post_breakout_bars: Number of bars after breakout
        base_price: Price before breakout
        breakout_magnitude: Size of breakout move (e.g., 0.10 = 10%)
        seed: Random seed

    Returns:
        DataFrame with OHLCV data showing breakout pattern
    """
    np.random.seed(seed)

    total_bars = warmup_bars + post_breakout_bars
    ohlcv_data = []

    # Phase 1: Compression (low volatility range)
    range_data = generate_ranging_market(
        bars=warmup_bars, base_price=base_price, range_pct=0.03, seed=seed
    )

    # Phase 2: Breakout
    breakout_price = base_price * (1 + breakout_magnitude)

    # Phase 3: Post-breakout continuation
    post_breakout_data = generate_trending_market(
        bars=post_breakout_bars,
        base_price=breakout_price,
        trend_strength="moderate",
        direction="up",
        seed=seed + 1,
    )

    # Combine phases
    df = pd.concat([range_data, post_breakout_data], ignore_index=True)

    # Inject volume spike at breakout
    if breakout_bar < len(df):
        df.loc[breakout_bar, "volume"] *= 3.0
        df.loc[breakout_bar : breakout_bar + 2, "volume"] *= 2.0

    # Fix timestamps
    start_time = datetime(2024, 1, 1)
    df["timestamp"] = [start_time + timedelta(minutes=15 * i) for i in range(len(df))]

    return df


def generate_pullback_scenario(
    trend_bars: int = 200,
    pullback_start: int = 200,
    pullback_bars: int = 50,
    continuation_bars: int = 100,
    base_price: float = 50000.0,
    pullback_depth: float = 0.382,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate a pullback scenario for testing pullback playbook.

    Scenario:
    1. Strong uptrend
    2. Pullback to key level
    3. Continuation of trend

    Args:
        trend_bars: Number of bars in initial trend
        pullback_start: Bar index where pullback starts
        pullback_bars: Number of bars in pullback
        continuation_bars: Number of bars in continuation
        base_price: Starting price
        pullback_depth: Depth of pullback (Fibonacci ratio, e.g., 0.382)
        seed: Random seed

    Returns:
        DataFrame with OHLCV data showing pullback pattern
    """
    np.random.seed(seed)

    # Phase 1: Initial uptrend
    trend_data = generate_trending_market(
        bars=trend_bars,
        base_price=base_price,
        trend_strength="strong",
        direction="up",
        seed=seed,
    )

    trend_high = trend_data["close"].iloc[-1]
    trend_low = base_price
    trend_range = trend_high - trend_low

    # Phase 2: Pullback
    pullback_target = trend_high - (trend_range * pullback_depth)
    pullback_data = generate_trending_market(
        bars=pullback_bars,
        base_price=trend_high,
        trend_strength="moderate",
        direction="down",
        seed=seed + 1,
    )

    # Adjust pullback to hit target
    pullback_data["close"] = np.linspace(trend_high, pullback_target, len(pullback_data))
    pullback_data["open"] = pullback_data["close"].shift(1).fillna(trend_high)
    pullback_data["high"] = pullback_data[["open", "close"]].max(axis=1) * 1.005
    pullback_data["low"] = pullback_data[["open", "close"]].min(axis=1) * 0.995

    # Phase 3: Continuation
    continuation_data = generate_trending_market(
        bars=continuation_bars,
        base_price=pullback_target,
        trend_strength="moderate",
        direction="up",
        seed=seed + 2,
    )

    # Combine phases
    df = pd.concat([trend_data, pullback_data, continuation_data], ignore_index=True)

    # Fix timestamps
    start_time = datetime(2024, 1, 1)
    df["timestamp"] = [start_time + timedelta(minutes=15 * i) for i in range(len(df))]

    return df


def generate_choppy_market(
    bars: int = 500, base_price: float = 50000.0, seed: int = 42
) -> pd.DataFrame:
    """
    Generate a choppy (whipsaw) market scenario.

    This is a difficult environment with frequent false signals.

    Args:
        bars: Number of bars
        base_price: Base price
        seed: Random seed

    Returns:
        DataFrame with OHLCV data showing choppy price action
    """
    np.random.seed(seed)

    ohlcv_data = []
    current_price = base_price

    # Generate alternating short trends
    for i in range(bars):
        timestamp = datetime(2024, 1, 1) + timedelta(minutes=15 * i)

        # Switch direction frequently
        if i % 20 < 10:
            trend = 0.001  # Up
        else:
            trend = -0.001  # Down

        # High noise
        noise = np.random.randn() * 0.01

        close = current_price * (1 + trend + noise)

        open_price = current_price
        intrabar_range = abs(np.random.normal(0, 0.008))
        high = close * (1 + intrabar_range)
        low = close * (1 - intrabar_range)

        high = max(high, open_price, close)
        low = min(low, open_price, close)

        volume = abs(np.random.normal(1e6, 3e5))  # High volume variance

        ohlcv_data.append(
            {
                "timestamp": timestamp,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )

        current_price = close

    return pd.DataFrame(ohlcv_data)


def generate_gap_scenario(
    bars: int = 500, base_price: float = 50000.0, gap_pct: float = 0.05, gap_bar: int = 250, seed: int = 42
) -> pd.DataFrame:
    """
    Generate a scenario with a price gap (simulating news event).

    Args:
        bars: Total number of bars
        base_price: Base price
        gap_pct: Size of gap as percentage (e.g., 0.05 = 5%)
        gap_bar: Bar index where gap occurs
        seed: Random seed

    Returns:
        DataFrame with OHLCV data including a gap
    """
    df = generate_synthetic_ohlcv(bars=bars, base_price=base_price, seed=seed)

    # Insert gap
    gap_size = base_price * gap_pct
    df.loc[gap_bar:, "open"] += gap_size
    df.loc[gap_bar:, "high"] += gap_size
    df.loc[gap_bar:, "low"] += gap_size
    df.loc[gap_bar:, "close"] += gap_size

    # Spike volume at gap
    df.loc[gap_bar, "volume"] *= 5.0

    return df


def generate_multi_symbol_data(
    symbols: List[str],
    bars: int = 1000,
    correlation: float = 0.7,
    seed: int = 42,
) -> dict:
    """
    Generate correlated OHLCV data for multiple symbols.

    Args:
        symbols: List of symbol names
        bars: Number of bars per symbol
        correlation: Correlation between symbols (0 to 1)
        seed: Random seed

    Returns:
        Dictionary mapping symbol names to DataFrames
    """
    np.random.seed(seed)

    # Generate correlated returns
    n_symbols = len(symbols)
    cov_matrix = np.full((n_symbols, n_symbols), correlation)
    np.fill_diagonal(cov_matrix, 1.0)

    # Generate returns for all symbols at once
    mean_returns = np.full(n_symbols, 0.0001)
    std_returns = np.full(n_symbols, 0.02 / np.sqrt(96))

    returns = np.random.multivariate_normal(
        mean=mean_returns,
        cov=np.outer(std_returns, std_returns) * cov_matrix,
        size=bars,
    )

    # Convert to price data for each symbol
    base_prices = [50000.0, 3000.0, 100.0]  # BTC, ETH, SOL-like prices
    data = {}

    for i, symbol in enumerate(symbols):
        base_price = base_prices[i] if i < len(base_prices) else 1000.0

        # Cumulative prices from returns
        log_prices = np.log(base_price) + np.cumsum(returns[:, i])
        close_prices = np.exp(log_prices)

        ohlcv_data = []
        for j, close in enumerate(close_prices):
            timestamp = datetime(2024, 1, 1) + timedelta(minutes=15 * j)

            open_price = close_prices[j - 1] if j > 0 else base_price
            intrabar_range = abs(np.random.normal(0, 0.005))
            high = max(close * (1 + intrabar_range), open_price, close)
            low = min(close * (1 - intrabar_range), open_price, close)
            volume = abs(np.random.normal(1e6, 2e5))

            ohlcv_data.append(
                {
                    "timestamp": timestamp,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )

        data[symbol] = pd.DataFrame(ohlcv_data)

    return data
