"""Data loader utilities for integration with replay-lab.

This module provides functions to load OHLCV data from replay-lab.
For now, it contains stub implementations that can be replaced when
replay-lab is available.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

import httpx
import pandas as pd

logger = logging.getLogger(__name__)


class DataLoadError(Exception):
    """Raised when data loading fails."""

    pass


def load_ohlcv_data(
    symbol: str,
    timeframe: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    data_dir: Optional[Path] = None,
    allow_synthetic: bool = True,
) -> pd.DataFrame:
    """
    Load OHLCV data for a symbol and timeframe.

    Attempts to load data from multiple sources in priority order:
    1. replay-lab (if available)
    2. CSV files in data_dir (if specified)
    3. Synthetic data (only if allow_synthetic=True)

    Args:
        symbol: Trading symbol (e.g., "BTC-USD")
        timeframe: Timeframe (e.g., "15m", "1h", "4h")
        start_date: Start date (YYYY-MM-DD) or None for all available
        end_date: End date (YYYY-MM-DD) or None for latest
        data_dir: Directory containing OHLCV data (optional)
        allow_synthetic: Allow fallback to synthetic data (default: True)

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume

    Raises:
        DataLoadError: If data cannot be loaded

    Example:
        >>> df = load_ohlcv_data("BTC-USD", "15m", start_date="2024-01-01")
        >>> df.head()
                   timestamp     open     high      low    close      volume
        0 2024-01-01 00:00:00  42000.0  42100.0  41900.0  42050.0  1234.567
    """
    logger.info(
        f"Loading OHLCV data: symbol={symbol}, timeframe={timeframe}, "
        f"start={start_date}, end={end_date}"
    )

    errors = []

    # Try 1: replay-lab API (if configured)
    replay_lab_url = os.getenv("REPLAY_LAB_URL")
    if replay_lab_url:
        try:
            df = _load_from_replay_lab(
                replay_lab_url, symbol, timeframe, start_date, end_date
            )
            validate_ohlcv_data(df)
            logger.info(f"Loaded {len(df)} bars from replay-lab API")
            return df
        except Exception as e:
            error_msg = f"replay-lab API failed: {e}"
            logger.warning(error_msg)
            errors.append(error_msg)

    # Try 2: CSV files in data_dir
    if data_dir is not None:
        csv_path = Path(data_dir) / f"{symbol}_{timeframe}.csv"
        if csv_path.exists():
            try:
                logger.info(f"Loading data from CSV: {csv_path}")
                df = pd.read_csv(csv_path)
                df['timestamp'] = pd.to_datetime(df['timestamp'])

                # Filter by date range if specified
                if start_date:
                    df = df[df['timestamp'] >= pd.to_datetime(start_date)]
                if end_date:
                    df = df[df['timestamp'] <= pd.to_datetime(end_date)]

                validate_ohlcv_data(df)
                logger.info(f"Loaded {len(df)} bars from CSV")
                return df
            except Exception as e:
                error_msg = f"CSV loading failed: {e}"
                logger.warning(error_msg)
                errors.append(error_msg)

    # Try 3: Synthetic data (only if allowed)
    if allow_synthetic:
        logger.warning(
            "No real data source available. Generating synthetic data for testing. "
            "This should only be used for development/testing, not production."
        )
        df = _generate_synthetic_ohlcv(symbol, timeframe, start_date, end_date)
        validate_ohlcv_data(df)
        logger.info(f"Generated {len(df)} synthetic bars")
        return df
    else:
        # Fail with all accumulated errors
        error_summary = "\n".join([f"  - {err}" for err in errors])
        raise DataLoadError(
            f"Failed to load real data for {symbol} {timeframe} (synthetic data disabled).\n"
            f"Errors encountered:\n{error_summary}\n\n"
            f"To allow synthetic data fallback for testing, set allow_synthetic=True or use mock mode."
        )


def _load_from_replay_lab(
    base_url: str,
    symbol: str,
    timeframe: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load OHLCV data from replay-lab REST API with pagination.

    The function attempts to fetch all available data by making multiple paginated requests.
    If pagination fails or returns limited data, it will log warnings to help diagnose issues.

    Args:
        base_url: Base URL of replay-lab API (e.g., "http://localhost:3301")
        symbol: Trading symbol (e.g., "BTC-USD")
        timeframe: Timeframe (e.g., "15m", "1h", "4h")
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        DataFrame with OHLCV data

    Raises:
        DataLoadError: If API request fails

    Environment Variables:
        REPLAY_LAB_PAGINATION_LIMIT: Override default pagination limit (default: 1000)
        REPLAY_LAB_MAX_ITERATIONS: Override max pagination iterations (default: 50)

    Example:
        >>> df = _load_from_replay_lab("http://localhost:3301", "BTC-USD", "15m")
    """
    # Convert Darwin symbol format (BTC-USD) to replay-lab format (COINBASE_SPOT_BTC_USD)
    symbol_parts = symbol.split("-")
    if len(symbol_parts) != 2:
        raise DataLoadError(f"Invalid symbol format: {symbol}. Expected format: BASE-QUOTE")

    base, quote = symbol_parts
    replay_lab_symbol = f"COINBASE_SPOT_{base}_{quote}"

    # Get API key if configured
    api_key = os.getenv("REPLAY_LAB_API_KEY")
    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    # Build request URL
    url = f"{base_url}/api/ohlcv/{replay_lab_symbol}"

    # Fetch data in chunks (configurable via env vars)
    all_candles = []
    max_limit = int(os.getenv("REPLAY_LAB_PAGINATION_LIMIT", "1000"))
    max_iterations = int(os.getenv("REPLAY_LAB_MAX_ITERATIONS", "50"))

    current_from = f"{start_date}T00:00:00Z" if start_date else None
    target_to = f"{end_date}T23:59:59Z" if end_date else None

    logger.info(f"Fetching data from replay-lab: {url}")
    logger.info(f"  Symbol: {replay_lab_symbol}")
    logger.info(f"  Timeframe: {timeframe}")
    logger.info(f"  Date range: {current_from} to {target_to}")
    logger.info(f"  Pagination: limit={max_limit}, max_iterations={max_iterations}")

    iteration = 0
    seen_timestamps = set()  # Track to avoid duplicates

    while iteration < max_iterations:
        iteration += 1
        params = {"timeframe": timeframe, "limit": max_limit}

        if current_from:
            params["from"] = current_from
        if target_to:
            params["to"] = target_to

        logger.info(f"  Pagination iteration {iteration}: from={current_from}, limit={max_limit}")

        try:
            response = httpx.get(url, params=params, headers=headers, timeout=30.0)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise DataLoadError(f"replay-lab API request failed: {e}")

        try:
            data = response.json()
        except ValueError as e:
            raise DataLoadError(f"Invalid JSON response from replay-lab: {e}")

        # Parse response
        if "candles" not in data:
            raise DataLoadError(f"Unexpected response format: {data}")

        candles = data["candles"]
        if not candles:
            # No more data
            logger.info(f"  No more candles returned. Pagination complete.")
            break

        # Filter out duplicates (can happen at pagination boundaries)
        new_candles = []
        duplicate_count = 0
        for candle in candles:
            ts = candle.get("timestamp") or candle.get("period_start")
            if ts not in seen_timestamps:
                seen_timestamps.add(ts)
                new_candles.append(candle)
            else:
                duplicate_count += 1

        if duplicate_count > 0:
            logger.debug(f"  Filtered {duplicate_count} duplicate candles")

        if not new_candles:
            logger.info(f"  All candles were duplicates. Pagination complete.")
            break

        all_candles.extend(new_candles)
        logger.info(f"  Fetched {len(new_candles)} new candles (total: {len(all_candles)})")

        # Check if we got less than max_limit (meaning we've reached the end)
        if len(candles) < max_limit:
            logger.info(f"  Received {len(candles)} < {max_limit} candles. Reached end of data.")
            break

        # Update current_from to AFTER the last (oldest) candle we received
        # replay-lab returns candles in descending order (newest first)
        # So candles[-1] is the oldest, and we want to fetch data OLDER than that
        last_candle = candles[-1]
        last_timestamp_str = last_candle.get("timestamp") or last_candle.get("period_start")

        # Parse the timestamp and advance it by 1 second to avoid fetching the same candle
        try:
            last_timestamp = pd.to_datetime(last_timestamp_str)
            # Move 1 second earlier (since we're going backwards in time)
            next_timestamp = last_timestamp - pd.Timedelta(seconds=1)
            current_from = next_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
            logger.debug(f"  Advanced from {last_timestamp_str} to {current_from}")
        except Exception as e:
            logger.warning(f"  Failed to parse timestamp for pagination: {e}")
            # Fallback: use the string as-is (might cause duplicates)
            current_from = last_timestamp_str

    if iteration >= max_iterations:
        logger.warning(f"Reached maximum pagination iterations ({max_iterations}). There may be more data available.")
        logger.warning(f"Consider increasing REPLAY_LAB_MAX_ITERATIONS environment variable.")

    if not all_candles:
        raise DataLoadError("No candles returned from replay-lab")

    # Log final summary
    logger.info(f"✅ Pagination complete: fetched {len(all_candles)} total candles in {iteration} iteration(s)")

    # Warn if we got suspiciously few candles (possible API issue)
    if start_date and end_date:
        # Calculate expected minimum candles based on timeframe
        try:
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            days = (end_dt - start_dt).days

            # Rough estimate: 15m = 96/day, 1h = 24/day, 4h = 6/day
            timeframe_minutes = _parse_timeframe_to_minutes(timeframe)
            candles_per_day = 1440 / timeframe_minutes
            expected_min = int(days * candles_per_day * 0.5)  # At least 50% of expected

            if len(all_candles) < expected_min:
                logger.warning(f"⚠️  Received fewer candles than expected:")
                logger.warning(f"   Got: {len(all_candles)} candles")
                logger.warning(f"   Expected (min): ~{expected_min} candles for {days} days at {timeframe}")
                logger.warning(f"   This may indicate:")
                logger.warning(f"   1. ReplayLabs server has limited historical data")
                logger.warning(f"   2. API pagination is not working correctly")
                logger.warning(f"   3. Date range includes gaps (weekends/holidays)")
                logger.warning(f"   Run 'python scripts/test_replay_lab_pagination.py' to diagnose")
        except Exception:
            pass  # Skip warning if we can't calculate

    # Convert to DataFrame
    # replay-lab returns candles in descending order (newest first)
    # We need to reverse to get ascending order (oldest first)
    rows = []
    for candle in reversed(all_candles):
        # Handle both timestamp formats
        ts = candle.get("timestamp") or candle.get("period_start")
        rows.append({
            "timestamp": pd.to_datetime(ts),
            "open": float(candle["open"]),
            "high": float(candle["high"]),
            "low": float(candle["low"]),
            "close": float(candle["close"]),
            "volume": float(candle["volume"]),
        })

    return pd.DataFrame(rows)


def _generate_synthetic_ohlcv(
    symbol: str,
    timeframe: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data for testing.

    Args:
        symbol: Trading symbol
        timeframe: Timeframe
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        DataFrame with synthetic OHLCV data
    """
    import numpy as np

    # Parse timeframe to minutes
    timeframe_minutes = _parse_timeframe_to_minutes(timeframe)

    # Default date range: 30 days
    if start_date is None:
        start_date = "2024-01-01"
    if end_date is None:
        # 30 days of data
        end = pd.to_datetime(start_date) + pd.Timedelta(days=30)
        end_date = end.strftime("%Y-%m-%d")

    # Generate timestamps
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    timestamps = pd.date_range(start, end, freq=f"{timeframe_minutes}min")

    # Base price by symbol
    base_prices = {
        "BTC-USD": 45000.0,
        "ETH-USD": 2500.0,
        "SOL-USD": 100.0,
    }
    base_price = base_prices.get(symbol, 45000.0)

    # Generate price series using geometric Brownian motion
    n_bars = len(timestamps)
    returns = np.random.normal(0.0001, 0.02 / np.sqrt(96), n_bars)  # ~2% daily vol
    log_prices = np.log(base_price) + np.cumsum(returns)
    close_prices = np.exp(log_prices)

    # Generate OHLC from close
    data = []
    for i, (ts, close) in enumerate(zip(timestamps, close_prices)):
        # Intrabar volatility (smaller range to avoid negative prices)
        intrabar_range = abs(np.random.normal(0, 0.002)) * close
        high = close + intrabar_range
        low = close - intrabar_range
        open_price = close_prices[i-1] if i > 0 else base_price

        # Ensure no negative prices
        low = max(low, close * 0.98)  # At most 2% drop intrabar
        high = max(high, close * 1.01)  # At least 1% higher than close

        # Volume (random around 1M with some correlation to price moves)
        base_volume = 1_000_000
        volume_mult = 1 + abs(returns[i]) * 10
        volume = base_volume * volume_mult * abs(1 + np.random.normal(0, 0.2))

        data.append({
            'timestamp': ts,
            'open': max(open_price, 0.01),  # Ensure positive
            'high': max(high, open_price, close),
            'low': max(min(low, open_price, close), 0.01),  # Ensure positive
            'close': max(close, 0.01),  # Ensure positive
            'volume': max(volume, 0)
        })

    return pd.DataFrame(data)


def _parse_timeframe_to_minutes(timeframe: str) -> int:
    """
    Parse timeframe string to minutes.

    Args:
        timeframe: Timeframe string (e.g., "15m", "1h", "4h", "1d")

    Returns:
        Number of minutes

    Example:
        >>> _parse_timeframe_to_minutes("15m")
        15
        >>> _parse_timeframe_to_minutes("1h")
        60
        >>> _parse_timeframe_to_minutes("4h")
        240
    """
    timeframe = timeframe.lower()
    if timeframe.endswith('m'):
        return int(timeframe[:-1])
    elif timeframe.endswith('h'):
        return int(timeframe[:-1]) * 60
    elif timeframe.endswith('d'):
        return int(timeframe[:-1]) * 1440
    else:
        raise ValueError(f"Unsupported timeframe format: {timeframe}")


def load_multiple_timeframes(
    symbol: str,
    timeframes: List[str],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    data_dir: Optional[Path] = None,
) -> dict[str, pd.DataFrame]:
    """
    Load OHLCV data for multiple timeframes.

    Args:
        symbol: Trading symbol (e.g., "BTC-USD")
        timeframes: List of timeframes (e.g., ["15m", "1h", "4h"])
        start_date: Start date (YYYY-MM-DD) or None for all available
        end_date: End date (YYYY-MM-DD) or None for latest
        data_dir: Directory containing OHLCV data (optional)

    Returns:
        Dictionary mapping timeframe to DataFrame

    Raises:
        DataLoadError: If data cannot be loaded

    Example:
        >>> data = load_multiple_timeframes("BTC-USD", ["15m", "1h"])
        >>> data["15m"].head()
        >>> data["1h"].head()
    """
    result = {}
    for tf in timeframes:
        try:
            result[tf] = load_ohlcv_data(symbol, tf, start_date, end_date, data_dir)
        except Exception as e:
            raise DataLoadError(f"Failed to load {symbol} {tf}: {e}")
    return result


def validate_ohlcv_data(df: pd.DataFrame) -> None:
    """
    Validate OHLCV data format.

    Args:
        df: DataFrame to validate

    Raises:
        DataLoadError: If data format is invalid
    """
    required_columns = ["timestamp", "open", "high", "low", "close", "volume"]
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise DataLoadError(f"Missing required columns: {missing}")

    if len(df) == 0:
        raise DataLoadError("DataFrame is empty")

    # Check for NaN values
    if df[required_columns].isna().any().any():
        raise DataLoadError("Data contains NaN values")

    # Check for negative prices
    price_cols = ["open", "high", "low", "close"]
    if (df[price_cols] <= 0).any().any():
        raise DataLoadError("Data contains non-positive prices")

    # Check that high >= low
    if (df["high"] < df["low"]).any():
        raise DataLoadError("Data contains bars where high < low")

    logger.debug(f"Data validation passed: {len(df)} bars")
