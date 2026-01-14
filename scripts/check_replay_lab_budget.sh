#!/bin/bash
# Check ReplayLabs JIT budget status

# Load environment
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

echo "=========================================="
echo "ReplayLabs Budget Check"
echo "=========================================="
echo ""
echo "API URL: $REPLAY_LAB_URL"
echo ""

# Try a small request
echo "Testing small request (no date range)..."
curl -s "${REPLAY_LAB_URL}/api/ohlcv/COINBASE_SPOT_BTC_USD?timeframe=15m&limit=10" \
    -H "x-api-key: ${REPLAY_LAB_API_KEY}" | python3 -m json.tool

echo ""
echo "=========================================="
echo ""

# Try a larger request
echo "Testing larger request (with date range)..."
curl -s "${REPLAY_LAB_URL}/api/ohlcv/COINBASE_SPOT_BTC_USD?timeframe=15m&limit=100&from=2024-01-01T00:00:00Z&to=2024-01-31T23:59:59Z" \
    -H "x-api-key: ${REPLAY_LAB_API_KEY}" | python3 -m json.tool

echo ""
echo "=========================================="
echo "Interpretation:"
echo "=========================================="
echo ""
echo "If you see:"
echo "  - 'JIT_BUDGET_EXCEEDED' → Your JIT budget is too low"
echo "  - 'candles' array → Data is available"
echo "  - Small number of candles → Limited cached data"
echo ""
echo "Solutions:"
echo "  1. Contact ReplayLabs to increase JIT budget"
echo "  2. Ask them to pre-cache your needed date ranges"
echo "  3. Use CSV files instead (set data_dir in config)"
echo ""
