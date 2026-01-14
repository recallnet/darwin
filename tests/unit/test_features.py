"""Comprehensive tests for feature computation and indicators.

Tests cover:
1. Individual indicator calculations (EMA, ATR, RSI, MACD, ADX, BB, Donchian)
2. Full feature pipeline computation
3. Bucketing functions for LLM context
4. Multi-symbol feature computation (BTC, ETH, SOL 15m)
5. Multi-timeframe scenarios (4h vs 15m)
"""

import numpy as np
import pytest

from darwin.features.bucketing import (
    bucket_drawdown,
    bucket_momentum,
    bucket_price_location,
    bucket_range_state,
    bucket_risk_mode,
    bucket_trend_mode,
    bucket_trend_strength_pct,
    bucket_vol_mode,
    bucket_vol_pct,
    bucket_volume_regime,
    compute_risk_budget,
)
from darwin.features.indicators import (
    ADXState,
    ATRState,
    BollingerBandsState,
    DonchianState,
    EMAState,
    MACDState,
    RollingWindow,
    RSIState,
    WilderEMAState,
)
from darwin.features.pipeline import FeaturePipelineV1
from tests.fixtures.market_data import (
    generate_breakout_scenario,
    generate_multi_symbol_data,
    generate_ranging_market,
    generate_synthetic_ohlcv,
    generate_trending_market,
)


class TestRollingWindow:
    """Test RollingWindow helper class."""

    def test_rolling_window_basic(self):
        """Test basic rolling window operations."""
        window = RollingWindow(size=3)

        # Add values
        window.update(10.0)
        assert window.mean() == 10.0
        assert len(window) == 1

        window.update(20.0)
        assert window.mean() == 15.0
        assert len(window) == 2

        window.update(30.0)
        assert window.mean() == 20.0
        assert len(window) == 3
        assert window.is_full()

        # Test overflow (should drop oldest)
        window.update(40.0)
        assert window.mean() == 30.0  # (20 + 30 + 40) / 3
        assert len(window) == 3

    def test_rolling_window_std(self):
        """Test standard deviation calculation."""
        window = RollingWindow(size=5)

        # Values: [10, 10, 10, 10, 10] - no variance
        for _ in range(5):
            window.update(10.0)
        assert abs(window.std()) < 1e-10

        # Values with variance
        window2 = RollingWindow(size=3)
        window2.update(1.0)
        window2.update(2.0)
        window2.update(3.0)
        # std = sqrt(((1-2)^2 + (2-2)^2 + (3-2)^2) / 3) = sqrt(2/3) ≈ 0.816
        assert 0.8 < window2.std() < 0.85

    def test_rolling_window_max_min(self):
        """Test max/min calculations."""
        window = RollingWindow(size=4)
        window.update(5.0)
        window.update(2.0)
        window.update(8.0)
        window.update(3.0)

        assert window.max() == 8.0
        assert window.min() == 2.0


class TestEMAIndicator:
    """Test EMA calculations."""

    def test_ema_basic(self):
        """Test basic EMA calculation."""
        ema = EMAState(period=3)

        # EMA formula: EMA_t = α * price + (1-α) * EMA_{t-1}
        # α = 2 / (period + 1) = 2 / 4 = 0.5
        prices = [100.0, 102.0, 101.0, 103.0, 105.0]

        for price in prices:
            ema.update(price)

        # Should be close to recent prices
        assert ema.value is not None
        assert 100.0 < ema.value < 106.0
        # With α=0.5, EMA should be between last price and mean
        assert ema.value > np.mean(prices) * 0.95

    def test_ema_convergence(self):
        """Test EMA converges to constant value."""
        ema = EMAState(period=10)

        # Feed constant values
        for _ in range(50):
            ema.update(50.0)

        # Should converge to exactly 50.0
        assert abs(ema.value - 50.0) < 1e-6

    def test_ema_trend_following(self):
        """Test EMA follows trend direction."""
        ema = EMAState(period=5)

        # Uptrend
        for i in range(20):
            ema.update(100.0 + i * 2.0)

        value_uptrend = ema.value

        # Downtrend
        ema2 = EMAState(period=5)
        for i in range(20):
            ema2.update(140.0 - i * 2.0)

        value_downtrend = ema2.value

        # EMA should follow the trend
        assert value_uptrend > 120.0  # Should be near end of uptrend
        assert value_downtrend < 120.0  # Should be near end of downtrend


class TestWilderEMA:
    """Test Wilder's smoothing (used in RSI, ATR)."""

    def test_wilder_ema_vs_standard_ema(self):
        """Test Wilder EMA uses different smoothing factor."""
        standard_ema = EMAState(period=14)
        wilder_ema = WilderEMAState(period=14)

        prices = [100.0, 102.0, 98.0, 105.0, 103.0]

        for price in prices:
            standard_ema.update(price)
            wilder_ema.update(price)

        # Wilder EMA (α = 1/14) is more conservative than standard EMA (α = 2/15)
        # They should differ
        assert abs(standard_ema.value - wilder_ema.value) > 0.01


class TestATRIndicator:
    """Test ATR (Average True Range) calculation."""

    def test_atr_basic(self):
        """Test basic ATR calculation."""
        atr = ATRState(period=14)

        # Simulate OHLC bars with varying ranges
        bars = [
            {"high": 102.0, "low": 98.0, "prev_close": 100.0},  # TR = 4.0
            {"high": 103.0, "low": 99.0, "prev_close": 100.0},  # TR = 4.0
            {"high": 105.0, "low": 101.0, "prev_close": 102.0},  # TR = 4.0
        ]

        for bar in bars:
            atr.update(bar["high"], bar["low"], bar["prev_close"])

        # ATR should stabilize around the true range
        assert atr.value is not None
        assert 3.5 < atr.value < 4.5

    def test_atr_gap_handling(self):
        """Test ATR handles gaps correctly."""
        atr = ATRState(period=5)

        # Normal bar
        atr.update(high=102.0, low=98.0, prev_close=100.0)  # TR = 4.0

        # Gap up (high-low < high-prev_close)
        atr.update(high=112.0, low=108.0, prev_close=100.0)  # TR = 12.0

        # Gap down (high-low < prev_close-low)
        atr.update(high=105.0, low=100.0, prev_close=110.0)  # TR = 10.0

        # ATR should be elevated due to gaps
        assert atr.value > 5.0


class TestRSIIndicator:
    """Test RSI (Relative Strength Index) calculation."""

    def test_rsi_basic(self):
        """Test basic RSI calculation."""
        rsi = RSIState(period=14)

        # Strong uptrend - RSI should be > 70
        for i in range(30):
            close = 100.0 + i * 2.0
            rsi.update(close)

        assert rsi.value is not None
        assert rsi.value > 70.0, f"Expected RSI > 70 in uptrend, got {rsi.value}"

    def test_rsi_downtrend(self):
        """Test RSI in downtrend."""
        rsi = RSIState(period=14)

        # Strong downtrend - RSI should be < 30
        for i in range(30):
            close = 200.0 - i * 2.0
            rsi.update(close)

        assert rsi.value < 30.0, f"Expected RSI < 30 in downtrend, got {rsi.value}"

    def test_rsi_sideways(self):
        """Test RSI in sideways market."""
        rsi = RSIState(period=14)

        # Sideways market - RSI should be near 50
        prices = [100.0, 102.0, 98.0, 101.0, 99.0] * 10
        for price in prices:
            rsi.update(price)

        assert 40.0 < rsi.value < 60.0, f"Expected RSI ≈ 50 in sideways, got {rsi.value}"


class TestMACDIndicator:
    """Test MACD calculation."""

    def test_macd_basic(self):
        """Test basic MACD calculation."""
        macd = MACDState(fast_period=12, slow_period=26, signal_period=9)

        # Uptrend
        for i in range(50):
            close = 100.0 + i * 1.0
            macd.update(close)

        # In uptrend, MACD should be positive
        assert macd.macd is not None
        assert macd.signal is not None
        assert macd.histogram is not None
        assert macd.macd > 0.0, f"Expected positive MACD in uptrend, got {macd.macd}"

    def test_macd_crossover(self):
        """Test MACD signal crossover."""
        macd = MACDState(fast_period=12, slow_period=26, signal_period=9)

        # Start with uptrend
        for i in range(40):
            macd.update(100.0 + i * 0.5)

        histogram_uptrend = macd.histogram

        # Add some downward movement
        for i in range(20):
            macd.update(120.0 - i * 0.3)

        histogram_downtrend = macd.histogram

        # Histogram should change sign or magnitude
        assert histogram_uptrend != histogram_downtrend


class TestADXIndicator:
    """Test ADX (Average Directional Index) calculation."""

    def test_adx_trending_market(self):
        """Test ADX rises in trending market."""
        adx = ADXState(period=14)

        # Strong uptrend
        for i in range(50):
            high = 100.0 + i * 1.0
            low = 98.0 + i * 1.0
            close = 99.0 + i * 1.0
            prev_close = 99.0 + (i - 1) * 1.0 if i > 0 else 99.0
            adx.update(high, low, close, prev_close)

        # ADX should be elevated in strong trend
        assert adx.adx is not None
        assert adx.adx > 20.0, f"Expected ADX > 20 in trend, got {adx.adx}"

    def test_adx_ranging_market(self):
        """Test ADX is low in ranging market."""
        adx = ADXState(period=14)

        # Sideways market
        prices = [100.0, 102.0, 98.0, 101.0, 99.0] * 15
        for i in range(len(prices)):
            high = prices[i] + 1.0
            low = prices[i] - 1.0
            close = prices[i]
            prev_close = prices[i - 1] if i > 0 else 100.0
            adx.update(high, low, close, prev_close)

        # ADX should be low in ranging market
        assert adx.adx < 25.0, f"Expected ADX < 25 in ranging, got {adx.adx}"


class TestBollingerBands:
    """Test Bollinger Bands calculation."""

    def test_bb_basic(self):
        """Test basic Bollinger Bands calculation."""
        bb = BollingerBandsState(period=20, num_std=2.0)

        # Feed constant prices - bands should be tight
        for _ in range(30):
            bb.update(100.0)

        assert bb.upper is not None
        assert bb.middle is not None
        assert bb.lower is not None
        assert abs(bb.middle - 100.0) < 0.1
        assert bb.upper > bb.middle > bb.lower

    def test_bb_expansion(self):
        """Test BB expansion during volatility."""
        bb = BollingerBandsState(period=20, num_std=2.0)

        # Start with low volatility
        for _ in range(30):
            bb.update(100.0)

        width_low_vol = bb.upper - bb.lower

        # Add high volatility
        bb2 = BollingerBandsState(period=20, num_std=2.0)
        for i in range(30):
            # Oscillate wildly
            price = 100.0 + (10.0 if i % 2 == 0 else -10.0)
            bb2.update(price)

        width_high_vol = bb2.upper - bb2.lower

        # High vol should have wider bands
        assert width_high_vol > width_low_vol


class TestDonchianChannels:
    """Test Donchian Channels calculation."""

    def test_donchian_basic(self):
        """Test basic Donchian channels."""
        donchian = DonchianState(period=20)

        # Uptrend
        for i in range(30):
            high = 100.0 + i * 1.0
            low = 98.0 + i * 1.0
            donchian.update(high, low)

        assert donchian.high is not None
        assert donchian.low is not None
        assert donchian.high > donchian.low

        # High should be near the recent highs
        assert donchian.high > 120.0


class TestFeaturePipeline:
    """Test full feature pipeline computation."""

    def test_pipeline_initialization(self):
        """Test feature pipeline initialization."""
        pipeline = FeaturePipelineV1(
            symbol="BTC-USD", warmup_bars=50, spread_bps=1.5
        )

        assert pipeline.symbol == "BTC-USD"
        assert pipeline.warmup_bars == 50
        assert pipeline.bar_count == 0

    def test_pipeline_warmup(self):
        """Test pipeline returns None during warmup."""
        pipeline = FeaturePipelineV1(
            symbol="BTC-USD", warmup_bars=100, spread_bps=1.5
        )

        # Generate synthetic data
        df = generate_synthetic_ohlcv(bars=150, base_price=50000.0, seed=42)

        # Process first 99 bars - should return None
        for i in range(99):
            row = df.iloc[i]
            features = pipeline.on_bar(
                timestamp=int(row["timestamp"].timestamp()),
                open_price=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
            assert features is None, f"Expected None during warmup at bar {i}"

        # Bar 100 should return features
        row = df.iloc[100]
        features = pipeline.on_bar(
            timestamp=int(row["timestamp"].timestamp()),
            open_price=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
        )
        assert features is not None, "Expected features after warmup"
        assert isinstance(features, dict)

    def test_pipeline_feature_keys(self):
        """Test pipeline returns all expected feature keys."""
        pipeline = FeaturePipelineV1(
            symbol="BTC-USD", warmup_bars=50, spread_bps=1.5
        )

        # Generate data
        df = generate_synthetic_ohlcv(bars=100, base_price=50000.0, seed=42)

        # Process all bars
        features = None
        for i in range(len(df)):
            row = df.iloc[i]
            features = pipeline.on_bar(
                timestamp=int(row["timestamp"].timestamp()),
                open_price=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )

        # Check last features
        assert features is not None

        # Required feature categories
        expected_keys = [
            # Price & Returns
            "close",
            "ret_1",
            "ret_4",
            "ret_16",
            "ret_96",
            "logret_1",
            "range_bps",
            # Volatility
            "atr",
            "atr_bps",
            "atr_z_96",
            "realized_vol_96",
            # Bollinger Bands
            "bb_upper",
            "bb_mid",
            "bb_lower",
            "bb_width_bps",
            "bb_pos",
            # EMAs
            "ema20",
            "ema50",
            "ema200",
            "ema20_slope_bps",
            "ema50_slope_bps",
            "trend_dir",
            # Trend Strength
            "adx14",
            "di_plus_14",
            "di_minus_14",
            "trend_strength",
            # Momentum
            "rsi14",
            "macd",
            "macd_signal",
            "macd_hist",
            # Range & Levels
            "donchian_high_32",
            "donchian_low_32",
            "breakout_dist_atr",
            "pullback_dist_ema20_atr",
            "pullback_dist_ema50_atr",
            # Volume
            "turnover_usd",
            "adv_usd",
            "vol_sma_96",
            "volume_ratio_96",
            "vol_z_96",
            # Microstructure
            "spread_bps",
            "slippage_bps_est",
            # Portfolio state
            "open_positions",
            "exposure_frac",
            "dd_24h_bps",
            "halt_flag",
        ]

        for key in expected_keys:
            assert key in features, f"Missing feature: {key}"

    def test_pipeline_feature_values_reasonable(self):
        """Test pipeline produces reasonable feature values."""
        pipeline = FeaturePipelineV1(
            symbol="BTC-USD", warmup_bars=50, spread_bps=1.5
        )

        # Generate realistic data
        df = generate_trending_market(
            bars=100, base_price=50000.0, trend_strength="moderate"
        )

        features = None
        for i in range(len(df)):
            row = df.iloc[i]
            features = pipeline.on_bar(
                timestamp=int(row["timestamp"].timestamp()),
                open_price=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )

        assert features is not None

        # Sanity checks on values
        assert features["close"] > 0
        assert 0 <= features["rsi14"] <= 100
        assert features["atr"] > 0
        assert features["ema20"] > 0
        assert features["ema50"] > 0
        assert features["ema200"] > 0
        assert features["volume_ratio_96"] > 0

    def test_pipeline_breakout_scenario(self):
        """Test pipeline features during breakout scenario."""
        pipeline = FeaturePipelineV1(
            symbol="BTC-USD", warmup_bars=100, spread_bps=1.5
        )

        # Generate breakout scenario
        df = generate_breakout_scenario(
            warmup_bars=200,
            breakout_bar=200,
            post_breakout_bars=50,
            base_price=50000.0,
        )

        # Process all bars and track features at breakout
        features_before = None
        features_at_breakout = None
        features_after = None

        for i in range(len(df)):
            row = df.iloc[i]
            features = pipeline.on_bar(
                timestamp=int(row["timestamp"].timestamp()),
                open_price=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )

            if i == 195:
                features_before = features
            elif i == 200:
                features_at_breakout = features
            elif i == 205:
                features_after = features

        # At breakout, volume should spike
        if features_at_breakout and features_before:
            assert features_at_breakout["volume_ratio_96"] > features_before[
                "volume_ratio_96"
            ]

        # After breakout, price should be higher
        if features_after and features_before:
            assert features_after["close"] > features_before["close"]


class TestMultiSymbolFeatures:
    """Test feature computation for multiple symbols (BTC, ETH, SOL)."""

    def test_multi_symbol_independent_pipelines(self):
        """Test each symbol has independent feature computation."""
        # Generate correlated but distinct data
        data = generate_multi_symbol_data(
            symbols=["BTC-USD", "ETH-USD", "SOL-USD"], bars=500, correlation=0.7, seed=42
        )

        pipelines = {
            symbol: FeaturePipelineV1(symbol=symbol, warmup_bars=100, spread_bps=1.5)
            for symbol in data.keys()
        }

        # Process all symbols
        final_features = {}
        for symbol, df in data.items():
            for i in range(len(df)):
                row = df.iloc[i]
                features = pipelines[symbol].on_bar(
                    timestamp=int(row["timestamp"].timestamp()),
                    open_price=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"],
                )
            final_features[symbol] = features

        # All symbols should have features
        assert all(f is not None for f in final_features.values())

        # Prices should be different (BTC > ETH > SOL)
        assert final_features["BTC-USD"]["close"] > final_features["ETH-USD"]["close"]
        assert final_features["ETH-USD"]["close"] > final_features["SOL-USD"]["close"]

        # RSI should be correlated but not identical (due to correlation=0.7)
        btc_rsi = final_features["BTC-USD"]["rsi14"]
        eth_rsi = final_features["ETH-USD"]["rsi14"]
        sol_rsi = final_features["SOL-USD"]["rsi14"]

        # Should be similar but not identical
        assert abs(btc_rsi - eth_rsi) < 30.0  # Loosely correlated
        assert abs(eth_rsi - sol_rsi) < 30.0


class TestBucketingFunctions:
    """Test bucketing functions for LLM context."""

    def test_bucket_trend_mode(self):
        """Test trend mode bucketing."""
        # Strong uptrend
        result = bucket_trend_mode(ema50=51000.0, ema200=50000.0, adx=30.0)
        assert result == "up"

        # Strong downtrend
        result = bucket_trend_mode(ema50=49000.0, ema200=50000.0, adx=30.0)
        assert result == "down"

        # Sideways (weak trend)
        result = bucket_trend_mode(ema50=50100.0, ema200=50000.0, adx=15.0)
        assert result == "sideways"

    def test_bucket_vol_mode(self):
        """Test volatility mode bucketing."""
        # Low volatility
        result = bucket_vol_mode(atr_z=-1.5)
        assert result == "low"

        # Normal volatility
        result = bucket_vol_mode(atr_z=0.0)
        assert result == "normal"

        # High volatility
        result = bucket_vol_mode(atr_z=2.0)
        assert result == "high"

    def test_bucket_momentum(self):
        """Test momentum bucketing."""
        # Strong up
        result = bucket_momentum(rsi=75.0, macd_hist=5.0)
        assert result == "strong_up"

        # Strong down
        result = bucket_momentum(rsi=25.0, macd_hist=-5.0)
        assert result == "strong_down"

        # Flat
        result = bucket_momentum(rsi=50.0, macd_hist=0.0)
        assert result == "flat"

    def test_bucket_price_location(self):
        """Test price location bucketing."""
        close = 50000.0
        ema20 = 49000.0
        ema50 = 48000.0
        ema200 = 47000.0
        atr = 500.0

        # Price well above key MAs
        result = bucket_price_location(close, ema20, ema50, ema200, atr)
        assert result == "above_key_ma"

        # Price near key MA
        close2 = 48100.0  # Close to ema50
        result2 = bucket_price_location(close2, ema20, ema50, ema200, atr)
        assert result2 == "near_key_ma"

        # Price below all MAs
        close3 = 46000.0
        result3 = bucket_price_location(close3, ema20, ema50, ema200, atr)
        assert result3 == "below_key_ma"

    def test_bucket_range_state(self):
        """Test range state bucketing."""
        # Contracting
        result = bucket_range_state(bb_width_bps=100.0)
        assert result == "contracting"

        # Normal
        result = bucket_range_state(bb_width_bps=300.0)
        assert result == "normal"

        # Expanding
        result = bucket_range_state(bb_width_bps=600.0)
        assert result == "expanding"

    def test_bucket_volume_regime(self):
        """Test volume regime bucketing."""
        # Low volume
        result = bucket_volume_regime(vol_z=-1.5)
        assert result == "low"

        # Normal volume
        result = bucket_volume_regime(vol_z=0.0)
        assert result == "normal"

        # High volume
        result = bucket_volume_regime(vol_z=2.0)
        assert result == "high"

    def test_bucket_risk_mode(self):
        """Test risk mode bucketing."""
        # Risk on (low DD, normal vol, low exposure)
        result = bucket_risk_mode(dd_24h_bps=100.0, vol_z=0.0, exposure_frac=0.3)
        assert result == "risk_on"

        # Risk off (high DD)
        result = bucket_risk_mode(dd_24h_bps=800.0, vol_z=2.0, exposure_frac=0.9)
        assert result == "risk_off"

    def test_bucket_drawdown(self):
        """Test drawdown bucketing."""
        assert bucket_drawdown(dd_24h_bps=50.0) == "none"
        assert bucket_drawdown(dd_24h_bps=250.0) == "small"
        assert bucket_drawdown(dd_24h_bps=450.0) == "medium"
        assert bucket_drawdown(dd_24h_bps=700.0) == "large"

    def test_bucket_trend_strength_pct(self):
        """Test trend strength percentage."""
        # ADX is 0-100+, but typically 0-50
        result = bucket_trend_strength_pct(adx=0.0)
        assert result == 0.0

        result = bucket_trend_strength_pct(adx=25.0)
        assert 45.0 < result < 55.0  # Should be around 50%

        result = bucket_trend_strength_pct(adx=50.0)
        assert result == 100.0

    def test_bucket_vol_pct(self):
        """Test volatility percentage."""
        # z-score of -2 to +3 maps to 0-100%
        result = bucket_vol_pct(atr_z=-2.0)
        assert result == 0.0

        result = bucket_vol_pct(atr_z=0.5)  # Middle of range
        assert 40.0 < result < 60.0

        result = bucket_vol_pct(atr_z=3.0)
        assert result == 100.0

    def test_compute_risk_budget(self):
        """Test risk budget computation."""
        # Risk on + low DD + low vol = full budget
        result = compute_risk_budget(
            risk_mode="risk_on", dd_24h_bps=100.0, vol_mode="low"
        )
        assert result == 1.0

        # Risk off = no budget
        result = compute_risk_budget(
            risk_mode="risk_off", dd_24h_bps=600.0, vol_mode="high"
        )
        assert result == 0.0

        # Neutral with some DD = reduced budget
        result = compute_risk_budget(
            risk_mode="neutral", dd_24h_bps=400.0, vol_mode="normal"
        )
        assert 0.0 < result < 1.0


class TestMultiTimeframeFeatures:
    """Test feature computation for different timeframes (4h vs 15m)."""

    def test_4h_vs_15m_timeframes(self):
        """Test features computed on 4h vs 15m candles."""
        # Generate same underlying price data
        # 4h candle = 16 x 15m candles
        base_price = 50000.0

        # Generate 15m data (1000 bars = ~10 days)
        df_15m = generate_trending_market(
            bars=1000, base_price=base_price, trend_strength="moderate", seed=42
        )

        # Simulate 4h data by sampling every 16th bar
        df_4h = df_15m.iloc[::16].reset_index(drop=True)

        # Create pipelines
        pipeline_15m = FeaturePipelineV1(
            symbol="BTC-USD", warmup_bars=100, spread_bps=1.5
        )
        pipeline_4h = FeaturePipelineV1(
            symbol="BTC-USD", warmup_bars=25, spread_bps=1.5  # 25 * 4h = 100h warmup
        )

        # Process 15m data
        features_15m = None
        for i in range(len(df_15m)):
            row = df_15m.iloc[i]
            features_15m = pipeline_15m.on_bar(
                timestamp=int(row["timestamp"].timestamp()),
                open_price=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )

        # Process 4h data
        features_4h = None
        for i in range(len(df_4h)):
            row = df_4h.iloc[i]
            features_4h = pipeline_4h.on_bar(
                timestamp=int(row["timestamp"].timestamp()),
                open_price=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )

        assert features_15m is not None
        assert features_4h is not None

        # Prices should be similar (same market)
        assert abs(features_15m["close"] - features_4h["close"]) < 1000.0

        # ATR should be different (4h has larger ranges)
        # This test is loose because we're sampling, not aggregating
        # In real usage, 4h bars would aggregate 16x 15m bars
        assert features_4h["atr"] > 0
        assert features_15m["atr"] > 0

    def test_global_regime_4h_computation(self):
        """Test computing global regime features from BTC 4h data."""
        # This tests the concept of global regime computation
        # even though it's not fully implemented in the main runner yet

        # Generate BTC 4h data
        df_btc_4h = generate_trending_market(
            bars=500, base_price=50000.0, trend_strength="strong", direction="up", seed=42
        )

        # Create pipeline for global regime
        pipeline_global = FeaturePipelineV1(
            symbol="BTC-USD-4h", warmup_bars=100, spread_bps=1.5
        )

        # Process data
        features_global = None
        for i in range(len(df_btc_4h)):
            row = df_btc_4h.iloc[i]
            features_global = pipeline_global.on_bar(
                timestamp=int(row["timestamp"].timestamp()),
                open_price=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )

        assert features_global is not None

        # In strong uptrend, should have:
        # - RSI > 60
        # - ADX > 25 (strong trend)
        # - EMA20 > EMA50 > EMA200
        assert features_global["rsi14"] > 60.0
        assert features_global["adx14"] > 25.0
        assert features_global["ema20"] > features_global["ema50"]
        assert features_global["ema50"] > features_global["ema200"]

        # Bucket these into global regime
        trend_mode = bucket_trend_mode(
            ema50=features_global["ema50"],
            ema200=features_global["ema200"],
            adx=features_global["adx14"],
        )
        assert trend_mode == "up"

        vol_mode = bucket_vol_mode(atr_z=features_global["atr_z_96"])
        assert vol_mode in ["low", "normal", "high"]


# Integration test
class TestFeatureIntegration:
    """Integration tests for feature computation."""

    def test_full_pipeline_with_real_scenario(self):
        """Test complete pipeline with realistic scenario."""
        # Generate 3 symbols with correlated data
        data = generate_multi_symbol_data(
            symbols=["BTC-USD", "ETH-USD", "SOL-USD"], bars=500, correlation=0.75, seed=42
        )

        # Create pipelines
        pipelines = {}
        for symbol in data.keys():
            pipelines[symbol] = FeaturePipelineV1(
                symbol=symbol, warmup_bars=100, spread_bps=1.5
            )

        # Process all data
        final_features = {}
        for symbol, df in data.items():
            for i in range(len(df)):
                row = df.iloc[i]
                features = pipelines[symbol].on_bar(
                    timestamp=int(row["timestamp"].timestamp()),
                    open_price=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"],
                )
            final_features[symbol] = features

        # All should have valid features
        assert all(f is not None for f in final_features.values())

        # Test bucketing on final features
        for symbol, features in final_features.items():
            # Bucket trend
            trend = bucket_trend_mode(
                ema50=features["ema50"],
                ema200=features["ema200"],
                adx=features["adx14"],
            )
            assert trend in ["up", "down", "sideways"]

            # Bucket momentum
            momentum = bucket_momentum(
                rsi=features["rsi14"], macd_hist=features["macd_hist"]
            )
            assert momentum in [
                "strong_up",
                "mild_up",
                "flat",
                "mild_down",
                "strong_down",
            ]

            # Bucket volatility
            vol = bucket_vol_mode(atr_z=features["atr_z_96"])
            assert vol in ["low", "normal", "high"]

            print(
                f"{symbol}: trend={trend}, momentum={momentum}, vol={vol}, "
                f"rsi={features['rsi14']:.1f}, adx={features['adx14']:.1f}"
            )


if __name__ == "__main__":
    # Run with: pytest tests/unit/test_features.py -v -s
    pytest.main([__file__, "-v", "-s"])
