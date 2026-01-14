#!/usr/bin/env python3
"""Test script to diagnose ReplayLabs pagination issues.

This script tests the ReplayLabs API directly to understand how pagination works
and diagnose why we're only getting ~67 candles.

Usage:
    export REPLAY_LAB_URL="http://localhost:3301"
    export REPLAY_LAB_API_KEY="your-api-key"  # if needed
    python scripts/test_replay_lab_pagination.py
"""

import os
import sys
import logging
from pathlib import Path

# Add darwin to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file if it exists
from dotenv import load_dotenv
load_dotenv()

from darwin.utils.data_loader import load_ohlcv_data, _load_from_replay_lab
from darwin.utils.logging import configure_logging

def test_pagination():
    """Test ReplayLabs pagination to see how many candles we can get."""

    # Configure logging to see all details
    configure_logging(log_level="DEBUG", console_level="DEBUG")
    logger = logging.getLogger(__name__)

    # Check environment variables
    replay_lab_url = os.getenv("REPLAY_LAB_URL")
    if not replay_lab_url:
        logger.error("REPLAY_LAB_URL not set. Please set it to your ReplayLabs server URL.")
        logger.error("Example: export REPLAY_LAB_URL='http://localhost:3301'")
        return

    logger.info(f"Testing ReplayLabs API at: {replay_lab_url}")

    # Test parameters
    symbol = "BTC-USD"
    timeframe = "15m"

    # Test 1: Load without date range (get all available)
    logger.info("\n" + "="*80)
    logger.info("TEST 1: Load all available data (no date range)")
    logger.info("="*80)

    try:
        df1 = load_ohlcv_data(
            symbol=symbol,
            timeframe=timeframe,
            start_date=None,
            end_date=None,
            allow_synthetic=False
        )
        logger.info(f"✅ SUCCESS: Loaded {len(df1)} candles")
        logger.info(f"   Date range: {df1['timestamp'].min()} to {df1['timestamp'].max()}")
        logger.info(f"   First 3 timestamps: {df1['timestamp'].head(3).tolist()}")
        logger.info(f"   Last 3 timestamps: {df1['timestamp'].tail(3).tolist()}")
    except Exception as e:
        logger.error(f"❌ FAILED: {e}")
        df1 = None

    # Test 2: Load with specific date range
    logger.info("\n" + "="*80)
    logger.info("TEST 2: Load with date range (2024-01-01 to 2024-01-31)")
    logger.info("="*80)

    try:
        df2 = load_ohlcv_data(
            symbol=symbol,
            timeframe=timeframe,
            start_date="2024-01-01",
            end_date="2024-01-31",
            allow_synthetic=False
        )
        logger.info(f"✅ SUCCESS: Loaded {len(df2)} candles")
        logger.info(f"   Date range: {df2['timestamp'].min()} to {df2['timestamp'].max()}")

        # Calculate expected candles for 15m timeframe over 31 days
        # 15m = 96 candles per day * 31 days = 2976 candles
        expected = 96 * 31
        logger.info(f"   Expected ~{expected} candles for 31 days at 15m timeframe")
        if len(df2) < expected * 0.9:
            logger.warning(f"   ⚠️  Got significantly less than expected ({len(df2)} vs ~{expected})")
    except Exception as e:
        logger.error(f"❌ FAILED: {e}")
        df2 = None

    # Test 3: Load longer date range
    logger.info("\n" + "="*80)
    logger.info("TEST 3: Load longer date range (2023-01-01 to 2024-12-31)")
    logger.info("="*80)

    try:
        df3 = load_ohlcv_data(
            symbol=symbol,
            timeframe=timeframe,
            start_date="2023-01-01",
            end_date="2024-12-31",
            allow_synthetic=False
        )
        logger.info(f"✅ SUCCESS: Loaded {len(df3)} candles")
        logger.info(f"   Date range: {df3['timestamp'].min()} to {df3['timestamp'].max()}")

        # Calculate expected for 2 years
        expected = 96 * 365 * 2
        logger.info(f"   Expected ~{expected} candles for 2 years at 15m timeframe")
        if len(df3) < expected * 0.5:
            logger.warning(f"   ⚠️  Got significantly less than expected ({len(df3)} vs ~{expected})")
    except Exception as e:
        logger.error(f"❌ FAILED: {e}")
        df3 = None

    # Test 4: Different timeframe
    logger.info("\n" + "="*80)
    logger.info("TEST 4: Different timeframe (1h instead of 15m)")
    logger.info("="*80)

    try:
        df4 = load_ohlcv_data(
            symbol=symbol,
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-01-31",
            allow_synthetic=False
        )
        logger.info(f"✅ SUCCESS: Loaded {len(df4)} candles")
        logger.info(f"   Date range: {df4['timestamp'].min()} to {df4['timestamp'].max()}")

        # 1h = 24 candles per day * 31 days = 744 candles
        expected = 24 * 31
        logger.info(f"   Expected ~{expected} candles for 31 days at 1h timeframe")
    except Exception as e:
        logger.error(f"❌ FAILED: {e}")
        df4 = None

    # Summary
    logger.info("\n" + "="*80)
    logger.info("SUMMARY")
    logger.info("="*80)

    results = [
        ("No date range", df1),
        ("Jan 2024 (15m)", df2),
        ("2 years (15m)", df3),
        ("Jan 2024 (1h)", df4),
    ]

    for test_name, df in results:
        if df is not None:
            logger.info(f"✅ {test_name:<20} {len(df):>6} candles")
        else:
            logger.info(f"❌ {test_name:<20} FAILED")

    logger.info("="*80)

    # Check if the "67 candle" issue appears
    if any(df is not None and 50 < len(df) < 100 for _, df in results):
        logger.warning("\n⚠️  DETECTED: One or more tests returned 50-100 candles")
        logger.warning("This matches the reported '67 candle' issue.")
        logger.warning("\nPossible causes:")
        logger.warning("1. ReplayLabs API has a default limit that's not being overridden")
        logger.warning("2. The 'limit' parameter is not being recognized")
        logger.warning("3. Pagination logic is not working correctly")
        logger.warning("4. ReplayLabs server configuration limits response size")
        logger.warning("\nRecommendations:")
        logger.warning("- Check ReplayLabs API documentation for correct parameter names")
        logger.warning("- Check ReplayLabs server logs to see what parameters it's receiving")
        logger.warning("- Try different parameter names (e.g., 'max', 'count', 'pageSize')")
        logger.warning("- Verify ReplayLabs server version supports pagination")

if __name__ == "__main__":
    test_pagination()
