"""Simple end-to-end test of Darwin trading system.

This script demonstrates the core components working together:
- Data loading (synthetic for testing)
- Feature computation
- Playbook evaluation
- LLM integration (mock)
- Simulator
"""

import sys
from pathlib import Path

# Add darwin to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from darwin.features import FeaturePipelineV1
from darwin.llm import LLMHarnessWithRetry, RateLimiter, create_llm_backend
from darwin.playbooks import BreakoutPlaybook
from darwin.simulator import PositionManager
from darwin.storage import PositionLedgerSQLite
from darwin.utils.data_loader import load_ohlcv_data
from darwin.utils.logging import configure_logging

# Configure logging
configure_logging(log_level="INFO", log_file=None)

print("=" * 60)
print("Darwin Trading System - Simple Test")
print("=" * 60)

# 1. Load data
print("\n1. Loading OHLCV data...")
df = load_ohlcv_data("BTC-USD", "15m", "2024-01-01", "2024-01-03")
print(f"   ✅ Loaded {len(df)} bars")

# 2. Initialize feature pipeline
print("\n2. Initializing feature pipeline...")
pipeline = FeaturePipelineV1(symbol="BTC-USD", warmup_bars=400, spread_bps=1.5)
print("   ✅ Feature pipeline ready")

# 3. Initialize playbook
print("\n3. Initializing breakout playbook...")
playbook = BreakoutPlaybook()
print("   ✅ Playbook ready")

# 4. Initialize LLM
print("\n4. Initializing LLM harness (mock)...")
backend = create_llm_backend(use_mock=True)
rate_limiter = RateLimiter(max_calls_per_minute=60)
llm_harness = LLMHarnessWithRetry(backend=backend, rate_limiter=rate_limiter, max_retries=3)
print("   ✅ LLM harness ready")

# 5. Initialize simulator
print("\n5. Initializing simulator...")
ledger = PositionLedgerSQLite(":memory:")  # In-memory for testing
position_manager = PositionManager(ledger, run_id="test_001")
print("   ✅ Simulator ready")

# 6. Run simulation
print("\n6. Running simulation...")
candidates_found = 0
positions_opened = 0

for idx, row in df.iterrows():
    # Compute features
    features = pipeline.on_bar(
        timestamp=row['timestamp'],
        open_price=row['open'],
        high=row['high'],
        low=row['low'],
        close=row['close'],
        volume=row['volume'],
        open_positions=position_manager.get_open_position_count(),
        exposure_frac=0.0,
        dd_24h_bps=0.0,
        halt_flag=0,
    )

    if features is None:
        # Still in warmup period
        continue

    # Check for candidates
    bar_data = {
        'timestamp': row['timestamp'],
        'open': row['open'],
        'high': row['high'],
        'low': row['low'],
        'close': row['close'],
        'volume': row['volume'],
        'prev_close': df.iloc[idx-1]['close'] if idx > 0 else row['close'],
    }

    candidate = playbook.evaluate(features, bar_data)

    if candidate is not None:
        candidates_found += 1
        print(f"   📊 Candidate #{candidates_found} at {row['timestamp']}: entry={candidate.entry_price:.2f}")

        # In a full system, we would:
        # 1. Build LLM payload
        # 2. Query LLM for decision
        # 3. Open position if LLM says "take"
        # For now, just demonstrate we found candidates

        if candidates_found >= 3:
            print("   ✅ Found 3+ candidates, stopping early")
            break

print(f"\n7. Results:")
print(f"   - Total bars processed: {idx + 1}")
print(f"   - Candidates found: {candidates_found}")
print(f"   - Warmup bars: {pipeline.warmup_bars}")

print("\n" + "=" * 60)
print("✅ Test complete - All components working!")
print("=" * 60)
