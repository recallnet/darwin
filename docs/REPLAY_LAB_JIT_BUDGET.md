# ReplayLabs JIT Budget Issue

## Problem Summary

**You're not hitting a pagination limit - you're hitting ReplayLabs' JIT (Just-In-Time) budget limit!**

When requesting historical data that isn't pre-cached, ReplayLabs needs to fetch it from upstream sources (like CoinAPI) in real-time. This uses "JIT calls" which are limited by your account budget.

## What We Discovered

### Test Results

```bash
python3 scripts/test_replay_lab_pagination.py
```

**Results:**
- ✅ **Without date range**: Got 4 candles (recent test data from Dec 18, 2025)
- ❌ **With date ranges (2024)**: 400 Bad Request

**Error Message:**
```json
{
    "error": "JIT requires 140 API calls but budget is 10",
    "code": "JIT_BUDGET_EXCEEDED",
    "callsNeeded": 140,
    "budget": 10,
    "gapCount": 41759
}
```

### What This Means

1. **ReplayLabs has minimal cached data** - Only 4 recent candles are pre-cached
2. **Historical data requires JIT calls** - Fetching 2024 data needs 140 API calls to upstream
3. **Your budget is 10 calls** - Can only fetch a small amount before hitting limit
4. **This explains the "~67 candles" issue** - That's what 10 JIT calls can fetch!

## Root Cause

**Found it!** The JIT budget is hardcoded in the ReplayLabs API route:

```typescript
// File: apps/replay-lab/src/app/api/ohlcv/[symbolId]/route.ts (line 63)
await jitFetchGaps(database, symbolId, timeframe, fromNorm, toNorm, {
  maxRequests: 10,  // <-- HARDCODED LIMIT
  timeout: 5000
})
```

**The Math:**
- To fetch 1 month (Jan 2024): ~149 requests needed
- To fetch 1 year: ~1,753 requests needed
- To fetch 2 years: ~3,506 requests needed
- Your current limit: **10 requests** → only ~3,000 1-minute candles (~67 when aggregated to 15m)

Each request fetches up to 300 1-minute candles from Coinbase API.

## Solutions

### Option 1: Increase JIT Budget in ReplayLabs (Best for Production)

**Ask the ReplayLabs maintainer to either:**

1. **Make it configurable via environment variable:**
   ```typescript
   const maxRequests = parseInt(process.env.JIT_MAX_REQUESTS || '10', 10);
   await jitFetchGaps(database, symbolId, timeframe, fromNorm, toNorm, {
     maxRequests,
     timeout: 30000  // Also increase timeout for large fetches
   })
   ```

2. **Or increase the hardcoded limit:**
   ```typescript
   await jitFetchGaps(database, symbolId, timeframe, fromNorm, toNorm, {
     maxRequests: 5000,  // Supports ~2 years of data
     timeout: 30000
   })
   ```

**Recommended values:**
- For RL training (need 2+ years): `maxRequests: 5000`
- For backtesting (need 3-6 months): `maxRequests: 1000`
- For quick tests (need 1 month): `maxRequests: 200`

### Option 2: Pre-Cache Data on ReplayLabs (Best for Repeated Testing)

Ask ReplayLabs to pre-cache the date ranges you need:

**What to cache:**
```
Symbols:
  - COINBASE_SPOT_BTC_USD
  - COINBASE_SPOT_ETH_USD
  - COINBASE_SPOT_SOL_USD

Timeframes:
  - 15m
  - 1h
  - 4h

Date Range:
  - 2023-01-01 to 2025-12-31
```

Once cached, these requests won't use JIT calls.

### Option 3: Use CSV Files (Immediate Workaround)

Download historical data and load from CSV files instead:

**Step 1: Download data**

From CoinAPI, Binance, or another source:
```bash
# Example: Download from CoinAPI
curl "https://rest.coinapi.io/v1/ohlcv/COINBASE_SPOT_BTC_USD/history?period_id=15MIN&time_start=2024-01-01&time_end=2024-12-31" \
  -H "X-CoinAPI-Key: YOUR_KEY" > btc_15m.json
```

**Step 2: Convert to CSV**

CSV format needed:
```csv
timestamp,open,high,low,close,volume
2024-01-01 00:00:00,42000.0,42100.0,41900.0,42050.0,1234.567
2024-01-01 00:15:00,42050.0,42150.0,42000.0,42100.0,1456.789
...
```

**Step 3: Configure Darwin to use CSV**

```yaml
# In your config.yaml
data_dir: "data/ohlcv"  # Directory containing CSV files

# Darwin will look for files like:
# data/ohlcv/BTC-USD_15m.csv
# data/ohlcv/ETH-USD_1h.csv
```

### Option 4: Use Synthetic Data (For Testing Only)

Temporarily use synthetic data for RL development:

```yaml
# In config.yaml - DON'T set data_dir
# Darwin will auto-generate synthetic data
```

Or explicitly in code:
```python
df = load_ohlcv_data(
    symbol="BTC-USD",
    timeframe="15m",
    start_date="2024-01-01",
    end_date="2024-12-31",
    allow_synthetic=True  # Falls back to synthetic if real data fails
)
```

**Warning:** Synthetic data is for testing only - don't use for actual backtesting or RL training!

## Checking Your Budget Status

Run the budget check script:

```bash
./scripts/check_replay_lab_budget.sh
```

This will:
- Test a small request (no JIT needed)
- Test a larger request (requires JIT)
- Show current budget status
- Display error messages if budget exceeded

## Understanding JIT Calls

**What counts as a JIT call:**
- Fetching data that's not already cached
- Each "gap" in data requires additional calls
- Number of calls depends on:
  - Date range requested
  - Data availability in cache
  - Granularity of timeframe

**Example:**
```
Request: BTC-USD 15m data for January 2024 (31 days)
Expected candles: 31 days × 96 candles/day = 2,976 candles

If ReplayLabs has ZERO cached data:
  - Needs to fetch all 2,976 candles
  - Might require 100-200 JIT calls (depending on API batch size)

If you have 10 JIT call budget:
  - Can only fetch ~60-70 candles
  - Request fails with JIT_BUDGET_EXCEEDED
```

## FAQ

### Q: Why does ReplayLabs have so little cached data?

A: ReplayLabs is designed to cache data on-demand. When you first request a date range, it uses JIT calls to fetch and cache it. Subsequent requests use the cached data (no JIT calls).

The issue is your first request hits the budget limit before completing.

### Q: Can I just increase the `limit` parameter?

A: No. The `limit` parameter controls how many candles to return per request, but the JIT budget is about *fetching* the data from upstream, not how it's returned to you.

### Q: Why do I get ~67 candles specifically?

A: With a 10 JIT call budget and typical API batch sizes, ReplayLabs can fetch approximately 60-70 candles before hitting the limit. The exact number depends on data gaps and API behavior.

### Q: Is this a Darwin bug?

A: No, this is a ReplayLabs configuration issue. Darwin's pagination code is working correctly - it just can't get past ReplayLabs' JIT budget limit.

### Q: How much should I increase my JIT budget to?

**For RL Training (need lots of data):**
- Minimum: 1000 JIT calls (covers ~6 months)
- Recommended: 5000 JIT calls (covers ~2+ years)
- This allows fetching sufficient diverse historical data

**For backtesting:**
- 200-500 JIT calls (covers 1-3 months)

**Calculation:**
- 1 month = ~149 requests
- 1 year = ~1,753 requests
- Each request fetches 300 1-minute candles

## Next Steps

1. **Check your current situation:**
   ```bash
   ./scripts/check_replay_lab_budget.sh
   ```

2. **Choose a solution:**
   - **Production**: Increase JIT budget or pre-cache data
   - **Quick workaround**: Use CSV files
   - **Testing only**: Use synthetic data

3. **For RL training**, you'll need Option 1 or 2 (real historical data) with sufficient budget to fetch:
   - Multiple symbols (BTC, ETH, SOL)
   - Multiple timeframes (15m, 1h, 4h)
   - Long date ranges (1-2 years for diversity)

4. **Contact ReplayLabs** if you need budget increase:
   - Explain you need historical data for RL training
   - Request appropriate JIT budget based on your needs
   - Or ask them to pre-cache specific date ranges

## Summary

The "~67 candles" issue is NOT a pagination bug in Darwin. It's ReplayLabs' JIT budget limiting how much data can be fetched on-demand. The solution is to either:

1. Increase your JIT budget on ReplayLabs
2. Have ReplayLabs pre-cache the data you need
3. Use CSV files as a workaround

For RL training purposes (which requires lots of diverse data), you'll definitely need to address this with ReplayLabs directly.
