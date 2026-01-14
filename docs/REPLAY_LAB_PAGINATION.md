# ReplayLabs Pagination Troubleshooting Guide

## Problem: Only Getting ~67 Candles

If you're only receiving about 67 candles from ReplayLabs instead of the full date range, this guide will help diagnose and fix the issue.

## Quick Diagnosis

Run the test script to see what's happening:

```bash
export REPLAY_LAB_URL="http://localhost:3301"
export REPLAY_LAB_API_KEY="your-key"  # if needed
python scripts/test_replay_lab_pagination.py
```

This will test pagination and show you exactly how many candles are being returned.

## Common Causes & Solutions

### 1. ReplayLabs Default Limit

**Symptom**: Always getting the same number of candles (e.g., 67, 100, 200)

**Cause**: ReplayLabs API may have a default limit that's not being overridden by our `limit` parameter.

**Solution A**: Check ReplayLabs documentation for correct parameter name

The API might use different parameter names:
- `limit` (what we're using)
- `max`
- `count`
- `pageSize`
- `perPage`

**Solution B**: Override the limit via environment variable

```bash
export REPLAY_LAB_PAGINATION_LIMIT=5000
darwin run config.yaml
```

**Solution C**: Check ReplayLabs server configuration

Look for these settings in ReplayLabs server config:
- `MAX_PAGE_SIZE`
- `DEFAULT_PAGE_SIZE`
- `API_RESPONSE_LIMIT`

### 2. Pagination Not Working

**Symptom**: Getting exactly the limit (e.g., 1000 candles) but no more

**Cause**: Pagination logic may not be advancing correctly

**What We Fixed**:
- ✅ Added duplicate detection to avoid re-fetching same candles
- ✅ Properly advance timestamps (subtract 1 second to move backwards)
- ✅ Added safety max iterations counter
- ✅ Better logging to see pagination progress

**Check Logs**:
Look for these log messages to see if pagination is working:
```
Pagination iteration 1: from=2024-01-01T00:00:00Z, limit=1000
  Fetched 1000 new candles (total: 1000)
Pagination iteration 2: from=2023-12-31T23:59:59Z, limit=1000
  Fetched 1000 new candles (total: 2000)
...
```

### 3. API Parameter Format Issues

**Symptom**: First request works, but pagination fails

**Cause**: ReplayLabs might not accept the timestamp format we're using

**Current Format**: `2024-01-01T00:00:00Z` (ISO 8601 with Z)

**Alternative Formats to Try**:
```python
# Unix timestamp (milliseconds)
current_from = int(last_timestamp.timestamp() * 1000)

# Unix timestamp (seconds)
current_from = int(last_timestamp.timestamp())

# ISO without Z
current_from = last_timestamp.strftime("%Y-%m-%dT%H:%M:%S")

# Different format
current_from = last_timestamp.strftime("%Y-%m-%d %H:%M:%S")
```

To test, temporarily modify `darwin/utils/data_loader.py` line ~250.

### 4. ReplayLabs Historical Data Limit

**Symptom**: Always getting same amount of data regardless of date range

**Cause**: ReplayLabs server may only have limited historical data

**Check**:
1. What date range does ReplayLabs actually have?
2. Check ReplayLabs server logs/UI to see available data range
3. Verify the symbol has data for your requested period

**Example**:
```bash
# Request data for 2023-01-01 to 2024-12-31 (2 years)
# But ReplayLabs only has data from 2024-06-01 onward

# You'll get ~7 months instead of 2 years
```

### 5. Cursor-Based Pagination

**Symptom**: API returns a `cursor` or `nextPage` field

**Cause**: ReplayLabs might use cursor-based pagination instead of timestamp-based

**What to Look For** in API responses:
```json
{
  "candles": [...],
  "cursor": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "hasMore": true
}
```

**Solution**: Update `data_loader.py` to use cursor if available:

```python
cursor = None
while True:
    params = {"timeframe": timeframe, "limit": max_limit}
    if cursor:
        params["cursor"] = cursor

    # ... make request ...

    data = response.json()
    candles = data["candles"]
    cursor = data.get("cursor") or data.get("nextPage")

    if not cursor or not candles:
        break
```

## Environment Variables

Configure pagination behavior:

```bash
# Maximum candles per request (default: 1000)
export REPLAY_LAB_PAGINATION_LIMIT=5000

# Maximum pagination iterations (default: 50, allowing 50k candles)
export REPLAY_LAB_MAX_ITERATIONS=100

# ReplayLabs API URL
export REPLAY_LAB_URL="http://localhost:3301"

# ReplayLabs API key (if required)
export REPLAY_LAB_API_KEY="your-api-key"
```

## Debugging Steps

### Step 1: Enable Debug Logging

Set log level to DEBUG to see all requests:

```python
# In your config
"logging": {
    "level": "DEBUG"
}
```

Or via environment:
```bash
export DARWIN_LOG_LEVEL=DEBUG
```

### Step 2: Check Actual API Requests

Look for log messages like:
```
Pagination iteration 1: from=2024-01-01T00:00:00Z, limit=1000
```

This shows the exact parameters being sent.

### Step 3: Inspect ReplayLabs Response

Add temporary logging to see raw response:

```python
# In data_loader.py, after line ~200
data = response.json()
logger.debug(f"Raw API response: {data}")  # Add this line
```

Look for:
- Actual number of candles returned
- Any pagination fields (cursor, nextPage, hasMore)
- Any error or warning messages

### Step 4: Test with ReplayLabs Directly

Use curl to test the API directly:

```bash
# First request
curl "http://localhost:3301/api/ohlcv/COINBASE_SPOT_BTC_USD?timeframe=15m&limit=1000&from=2024-01-01T00:00:00Z&to=2024-01-31T23:59:59Z"

# Check response count
curl "..." | jq '.candles | length'

# Check for pagination fields
curl "..." | jq 'keys'
```

### Step 5: Check ReplayLabs Server

If you have access to the ReplayLabs server:

1. **Check logs** for incoming requests
2. **Check configuration** for limits
3. **Check database** for available data range
4. **Check version** - older versions might not support pagination

## Expected Candle Counts

For reference, here's how many candles to expect:

| Timeframe | Per Day | 1 Month | 3 Months | 1 Year |
|-----------|---------|---------|----------|--------|
| 1m        | 1,440   | 43,200  | 129,600  | 525,600|
| 5m        | 288     | 8,640   | 25,920   | 105,120|
| 15m       | 96      | 2,880   | 8,640    | 35,040 |
| 1h        | 24      | 720     | 2,160    | 8,760  |
| 4h        | 6       | 180     | 540      | 2,190  |
| 1d        | 1       | 30      | 90       | 365    |

**Note**: Crypto markets trade 24/7, so these are actual counts (not adjusted for market hours).

## Still Having Issues?

If pagination still isn't working after trying these steps:

1. **Share logs** with the Darwin team (with DEBUG level enabled)
2. **Check ReplayLabs documentation** for their specific API
3. **Contact ReplayLabs support** about pagination limits
4. **Consider alternatives**:
   - Use CSV files instead: Set `data_dir` in your config
   - Download data in chunks manually
   - Use ReplayLabs export feature (if available)

## Workaround: Manual Data Export

If pagination can't be fixed immediately:

```bash
# Export data from ReplayLabs to CSV
replay-lab export --symbol BTC-USD --timeframe 15m \
    --from 2023-01-01 --to 2024-12-31 --output btc_15m.csv

# Use CSV in Darwin
# In your config.yaml:
data_dir: "/path/to/csv/files"
```

Then Darwin will load from CSV instead of hitting the API.

## Success Indicators

You'll know pagination is working when:

✅ Log shows multiple pagination iterations:
```
Pagination iteration 1: ... (total: 1000)
Pagination iteration 2: ... (total: 2000)
Pagination iteration 3: ... (total: 3000)
...
```

✅ Candle count matches expected for your date range

✅ No warnings about "fewer candles than expected"

✅ Different date ranges return proportionally different candle counts

## Report Issues

If you discover a specific ReplayLabs API issue, please document:

1. ReplayLabs version
2. Exact API endpoint and parameters used
3. Expected vs actual candle count
4. Sample API response (anonymized)
5. Any error messages from ReplayLabs server logs

This helps us improve pagination for everyone!
