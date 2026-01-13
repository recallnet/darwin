# Feature Pipeline Documentation

## Overview

The feature pipeline computes 80+ technical indicators from OHLCV data. Features are designed to be:

1. **Incremental**: Updated per-bar instead of recomputed
2. **Efficient**: O(1) updates using rolling state
3. **Bucketed**: Converted to LLM-friendly categorical values

## Feature Categories

### 1. Price & Trend (20 features)

#### Moving Averages
- `ema20`, `ema50`, `ema200`: Exponential moving averages
- `sma20`, `sma50`, `sma200`: Simple moving averages
- `ema_20_50_cross`: EMA crossover signal

#### Price Location
- `close`: Current price
- `price_vs_ema20`: Deviation from EMA20 (%)
- `price_location_1h`: Position in 1h range (bucketed)

#### Trend Indicators
- `adx`: Average Directional Index
- `plus_di`, `minus_di`: Directional indicators
- `trend_strength`: ADX-based strength score
- `trend_direction`: Up/Down/Sideways

### 2. Momentum (15 features)

- `rsi`: Relative Strength Index
- `rsi_regime`: Overbought/Neutral/Oversold
- `macd`, `macd_signal`, `macd_histogram`: MACD components
- `momentum_1h`, `momentum_4h`: Multi-timeframe momentum
- `stoch_k`, `stoch_d`: Stochastic oscillator

### 3. Volatility (12 features)

- `atr`: Average True Range
- `atr_pct`: ATR as % of price
- `atr_regime`: Low/Normal/High
- `bollinger_upper`, `bollinger_lower`, `bollinger_mid`: Bollinger Bands
- `bollinger_width`: Band width (volatility measure)
- `keltner_upper`, `keltner_lower`: Keltner Channels

### 4. Volume (10 features)

- `volume`: Current volume
- `volume_sma20`: 20-period volume average
- `volume_ratio`: Current / average
- `volume_regime`: Low/Normal/High
- `volume_zscore`: Z-score vs 96-bar lookback
- `obv`: On-Balance Volume
- `vwap`: Volume-Weighted Average Price

### 5. Market Structure (15 features)

- `swing_high`, `swing_low`: Recent swing points
- `support`, `resistance`: Key levels
- `distance_to_support`, `distance_to_resistance`: Distance in ATR
- `range_state`: Compression/Expansion
- `chop_index`: Choppiness index
- `fib_382`, `fib_500`, `fib_618`: Fibonacci levels

### 6. Multi-Timeframe (8 features)

- `trend_1h`, `trend_4h`: Trend on higher timeframes
- `volatility_1h`, `volatility_4h`: Volatility regimes
- `momentum_1h`, `momentum_4h`: Momentum indicators
- `alignment_score`: Cross-timeframe alignment

### 7. Derivatives (Optional, 5 features)

- `funding_rate`: Perpetual swap funding
- `open_interest_usd`: Total open interest
- `oi_change_24h`: OI change over 24 hours
- `premium_index`: Spot vs futures premium
- `volume_spot_futures_ratio`: Volume split

### 8. Global Regime (5 features)

Based on BTC 4h chart:
- `risk_mode`: Risk-on/Risk-off/Neutral
- `trend_mode`: Uptrend/Downtrend/Ranging
- `vol_mode`: Low/Normal/High/Extreme
- `drawdown_pct`: Current drawdown from ATH
- `drawdown_bucket`: None/Shallow/Moderate/Deep

## Feature Bucketing

Features are converted to LLM-friendly buckets for prompts.

### Price Location Buckets

```python
def bucket_price_location(price, ema20, ema50):
    if price > ema20 * 1.02:
        return "well_above_ema20"
    elif price > ema20:
        return "above_ema20"
    elif price > ema20 * 0.98:
        return "at_ema20"
    elif price > ema50:
        return "between_ema20_ema50"
    else:
        return "below_ema50"
```

### Momentum Buckets

```python
def bucket_momentum(rsi):
    if rsi > 70:
        return "overbought"
    elif rsi > 60:
        return "strong"
    elif rsi > 50:
        return "bullish"
    elif rsi > 40:
        return "neutral"
    elif rsi > 30:
        return "bearish"
    else:
        return "oversold"
```

### Volatility Buckets

```python
def bucket_volatility(atr_pct):
    if atr_pct > 3.0:
        return "extreme"
    elif atr_pct > 2.0:
        return "high"
    elif atr_pct > 1.0:
        return "normal"
    else:
        return "low"
```

## Incremental Updates

### EMA State

```python
class EMAState:
    def __init__(self, period: int):
        self.period = period
        self.alpha = 2.0 / (period + 1)
        self.value = None

    def update(self, price: float):
        if self.value is None:
            self.value = price
        else:
            self.value = (price * self.alpha) + (self.value * (1 - self.alpha))
```

### ATR State (Wilder's EMA)

```python
class ATRState:
    def __init__(self, period: int = 14):
        self.period = period
        self.alpha = 1.0 / period
        self.value = None

    def update(self, true_range: float):
        if self.value is None:
            self.value = true_range
        else:
            self.value = (true_range * self.alpha) + (self.value * (1 - self.alpha))
```

## Usage Example

```python
from darwin.features.pipeline import FeaturePipelineV1

# Initialize pipeline
pipeline = FeaturePipelineV1(
    symbol="BTC-USD",
    warmup_bars=400,
    feature_mode="full"
)

# Process bars
for bar in bars:
    features = pipeline.on_bar(bar)

    if features is not None:
        # Features ready after warmup
        print(f"Close: {features['close']}")
        print(f"RSI: {features['rsi']}")
        print(f"ATR: {features['atr']}")
```

## Performance Optimization

### Before (Naive)
```python
# Recompute from scratch each bar
def compute_ema(prices, period):
    return pandas.ewm(prices, span=period).mean()[-1]

# O(N) per bar × M features × K bars = O(NMK)
```

### After (Incremental)
```python
# Update state
ema_state.update(new_price)
value = ema_state.value

# O(1) per bar × M features × K bars = O(MK)
# 10-100x speedup
```

## Testing Features

### Unit Tests

```python
def test_ema_calculation():
    ema = EMAState(period=3)
    prices = [100.0, 102.0, 101.0, 103.0, 105.0]

    for price in prices:
        ema.update(price)

    assert ema.value is not None
    assert 100 < ema.value < 106
```

### Property-Based Tests

```python
@given(
    prices=st.lists(st.floats(min_value=1, max_value=100000), min_size=50)
)
def test_ema_stays_in_range(prices):
    ema = EMAState(period=20)

    for price in prices:
        ema.update(price)

    # EMA should stay within price range
    assert min(prices) <= ema.value <= max(prices)
```

## References

- [Architecture Overview](./architecture.md)
- [Playbook Specifications](./playbooks.md)
- [Technical Analysis Library](https://technical-analysis-library-in-python.readthedocs.io/)
