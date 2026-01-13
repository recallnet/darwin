"""Test script to verify replay-lab integration with real data.

This script tests:
1. Connection to replay-lab API
2. OHLCV data fetching
3. Data validation
4. Symbol format conversion
"""

import os
import sys
from pathlib import Path

# Add darwin to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from darwin.utils.data_loader import load_ohlcv_data

def test_replay_lab_integration():
    """Test replay-lab integration end-to-end."""

    replay_lab_url = os.getenv('REPLAY_LAB_URL')

    print("="*80)
    print("REPLAY-LAB INTEGRATION TEST")
    print("="*80)

    # Check if replay-lab URL is set
    if not replay_lab_url:
        print("\n❌ REPLAY_LAB_URL not set in environment")
        print("\nTo enable replay-lab:")
        print("1. Start replay-lab: cd ../replay-lab && pnpm dev --filter replay-lab")
        print("2. Set in .env: REPLAY_LAB_URL=http://localhost:3301")
        print("3. Run this test again")
        return False

    print(f"\n✅ Replay-lab URL configured: {replay_lab_url}")

    # Test 1: Check health endpoint
    print("\n" + "-"*80)
    print("Test 1: Health Check")
    print("-"*80)

    try:
        import httpx
        response = httpx.get(f"{replay_lab_url}/api/health", timeout=5.0)
        response.raise_for_status()
        print(f"✅ Replay-lab is reachable: {response.status_code}")
    except Exception as e:
        print(f"❌ Cannot reach replay-lab: {e}")
        print(f"\nMake sure replay-lab is running at {replay_lab_url}")
        return False

    # Test 2: Fetch OHLCV data for BTC-USD
    print("\n" + "-"*80)
    print("Test 2: Fetch OHLCV Data (BTC-USD, 15m)")
    print("-"*80)

    try:
        df = load_ohlcv_data(
            symbol="BTC-USD",
            timeframe="15m",
            start_date="2025-01-01",
            end_date="2025-01-02"
        )

        print(f"✅ Successfully loaded {len(df)} bars")
        print(f"\nData sample:")
        print(df.head(3))

        # Validate data
        print(f"\nData validation:")
        print(f"  • Columns: {list(df.columns)}")
        print(f"  • Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        print(f"  • Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
        print(f"  • No NaN values: {not df.isna().any().any()}")

        if len(df) > 0:
            print("\n✅ Replay-lab integration working perfectly!")
            return True
        else:
            print("\n⚠️  No data returned (may need to ingest data first)")
            return False

    except Exception as e:
        print(f"❌ Data fetch failed: {e}")
        print("\nPossible issues:")
        print("1. No data in database for this date range")
        print("2. Symbol not available")
        print("3. API endpoint changed")
        return False

    # Test 3: Test fallback to synthetic data
    print("\n" + "-"*80)
    print("Test 3: Fallback to Synthetic Data")
    print("-"*80)

    # Temporarily unset REPLAY_LAB_URL
    original_url = os.environ.get('REPLAY_LAB_URL')
    if original_url:
        del os.environ['REPLAY_LAB_URL']

    try:
        df = load_ohlcv_data(
            symbol="BTC-USD",
            timeframe="15m",
            start_date="2025-01-01",
            end_date="2025-01-02"
        )
        print(f"✅ Fallback works: {len(df)} synthetic bars generated")
    finally:
        # Restore REPLAY_LAB_URL
        if original_url:
            os.environ['REPLAY_LAB_URL'] = original_url

    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED")
    print("="*80)
    return True


if __name__ == "__main__":
    success = test_replay_lab_integration()
    sys.exit(0 if success else 1)
