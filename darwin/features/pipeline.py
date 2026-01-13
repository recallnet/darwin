"""
Feature pipeline for incremental computation of all trading features.

FeaturePipelineV1 maintains rolling state and computes 80+ features per bar.
"""

from typing import Optional
import math
from collections import deque

from darwin.features.indicators import (
    RollingWindow,
    EMAState,
    WilderEMAState,
    ATRState,
    ADXState,
    RSIState,
    MACDState,
    BollingerBandsState,
    DonchianState,
)


class FeaturePipelineV1:
    """
    Incremental feature pipeline that computes all 80+ features from spec.

    Maintains rolling state for all indicators and updates incrementally.
    Returns feature dict on each bar, or None during warmup period.
    """

    def __init__(
        self,
        symbol: str,
        warmup_bars: int = 400,
        spread_bps: float = 1.5,
    ):
        """
        Initialize feature pipeline.

        Args:
            symbol: Trading symbol (e.g., "BTC-USD")
            warmup_bars: Number of bars before features are valid (default 400)
            spread_bps: Bid-ask spread in basis points (default 1.5 for BTC)
        """
        self.symbol = symbol
        self.warmup_bars = warmup_bars
        self.spread_bps = spread_bps

        # Bar counter
        self.bar_count = 0

        # Price/return history
        self.close_history: deque[float] = deque(maxlen=200)  # For lookbacks
        self.logret_history: deque[float] = deque(maxlen=100)  # For realized vol

        # EMAs
        self.ema20 = EMAState(20)
        self.ema50 = EMAState(50)
        self.ema200 = EMAState(200)

        # EMA slope tracking
        self.ema20_history: deque[float] = deque(maxlen=5)
        self.ema50_history: deque[float] = deque(maxlen=5)

        # Volatility indicators
        self.atr = ATRState(14)
        self.atr_bps_window = RollingWindow(96)  # For ATR z-score

        # Trend indicators
        self.adx = ADXState(14)

        # Momentum indicators
        self.rsi = RSIState(14)
        self.macd = MACDState(12, 26, 9)

        # Bollinger Bands
        self.bb = BollingerBandsState(20, 2.0)

        # Donchian Channels
        self.donchian = DonchianState(32)

        # Volume tracking
        self.volume_window = RollingWindow(96)
        self.turnover_window = RollingWindow(96)

        # Previous bar values (for returns, TR, etc.)
        self.prev_close: Optional[float] = None
        self.prev_high: Optional[float] = None
        self.prev_low: Optional[float] = None

    def on_bar(
        self,
        timestamp: int,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        open_positions: int = 0,
        exposure_frac: float = 0.0,
        dd_24h_bps: float = 0.0,
        halt_flag: int = 0,
    ) -> Optional[dict]:
        """
        Process new bar and compute all features.

        Args:
            timestamp: Bar timestamp (unix seconds or ms)
            open_price: Bar open price
            high: Bar high price
            low: Bar low price
            close: Bar close price
            volume: Bar volume
            open_positions: Number of currently open positions (default 0)
            exposure_frac: Current portfolio exposure fraction (default 0.0)
            dd_24h_bps: Current 24h drawdown in bps (default 0.0)
            halt_flag: Risk halt flag, 1 if halted (default 0)

        Returns:
            Feature dict if warmup complete, None otherwise
        """
        self.bar_count += 1

        # Update all indicators
        self._update_indicators(high, low, close, volume)

        # Check warmup
        if self.bar_count < self.warmup_bars:
            return None

        # Compute all features
        features = self._compute_features(
            timestamp=timestamp,
            open_price=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
            open_positions=open_positions,
            exposure_frac=exposure_frac,
            dd_24h_bps=dd_24h_bps,
            halt_flag=halt_flag,
        )

        return features

    def _update_indicators(
        self,
        high: float,
        low: float,
        close: float,
        volume: float,
    ) -> None:
        """Update all indicator states with new bar."""
        # Update EMAs
        ema20_val = self.ema20.update(close)
        ema50_val = self.ema50.update(close)
        self.ema200.update(close)

        # Track EMA history for slopes
        self.ema20_history.append(ema20_val)
        self.ema50_history.append(ema50_val)

        # Update volatility indicators
        self.atr.update(high, low, close)

        # Update trend indicators
        self.adx.update(high, low, close)

        # Update momentum indicators
        self.rsi.update(close)
        self.macd.update(close)

        # Update Bollinger Bands
        self.bb.update(close)

        # Update Donchian channels
        self.donchian.update(high, low)

        # Update volume tracking
        self.volume_window.update(volume)
        turnover = close * volume
        self.turnover_window.update(turnover)

        # Track close history for returns
        self.close_history.append(close)

        # Calculate and track log return
        if self.prev_close is not None and self.prev_close > 1e-12:
            logret = math.log(close / self.prev_close)
            self.logret_history.append(logret)

        # Update previous values
        self.prev_close = close
        self.prev_high = high
        self.prev_low = low

    def _compute_features(
        self,
        timestamp: int,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        open_positions: int,
        exposure_frac: float,
        dd_24h_bps: float,
        halt_flag: int,
    ) -> dict:
        """Compute all 80+ features from current state."""
        features = {}

        # --- A) Price / Returns ---
        features['timestamp'] = timestamp
        features['close'] = close

        # Returns at different horizons
        features['ret_1'] = self._safe_return(close, 1)
        features['ret_4'] = self._safe_return(close, 4)
        features['ret_16'] = self._safe_return(close, 16)
        features['ret_96'] = self._safe_return(close, 96)

        # Log return (1 bar)
        if len(self.close_history) >= 2:
            prev = self.close_history[-2]
            features['logret_1'] = math.log(close / prev) if prev > 1e-12 else 0.0
        else:
            features['logret_1'] = 0.0

        # Range in bps
        features['range_bps'] = self._bps((high - low) / close) if close > 1e-12 else 0.0

        # --- B) Volatility ---
        atr_val = self.atr.get()
        features['atr'] = atr_val

        atr_bps_val = self._bps(atr_val / close) if close > 1e-12 else 0.0
        features['atr_bps'] = atr_bps_val

        # Update ATR bps window for z-score
        self.atr_bps_window.update(atr_bps_val)

        # ATR z-score
        features['atr_z_96'] = self._zscore(
            atr_bps_val,
            self.atr_bps_window.mean(),
            self.atr_bps_window.std()
        )

        # Realized volatility (std of log returns over 96 bars)
        if len(self.logret_history) >= 96:
            recent_logrets = list(self.logret_history)[-96:]
            mean_lr = sum(recent_logrets) / len(recent_logrets)
            var_lr = sum((x - mean_lr) ** 2 for x in recent_logrets) / len(recent_logrets)
            features['realized_vol_96'] = math.sqrt(var_lr)
        else:
            features['realized_vol_96'] = 0.0

        # --- C) Trend / Regime ---
        features['ema20'] = self.ema20.get()
        features['ema50'] = self.ema50.get()
        features['ema200'] = self.ema200.get()

        # EMA slopes (over 4 bars ~1h)
        features['ema20_slope_bps'] = self._compute_slope(
            list(self.ema20_history), 4, close
        )
        features['ema50_slope_bps'] = self._compute_slope(
            list(self.ema50_history), 4, close
        )

        # ADX and directional indicators
        adx_val, di_plus_val, di_minus_val = self.adx.get()
        features['adx14'] = adx_val
        features['di_plus_14'] = di_plus_val
        features['di_minus_14'] = di_minus_val

        # Trend strength (required key)
        features['trend_strength'] = adx_val

        # Trend direction
        ema50_val = features['ema50']
        ema200_val = features['ema200']
        if ema50_val > ema200_val:
            features['trend_dir'] = 1
        elif ema50_val < ema200_val:
            features['trend_dir'] = -1
        else:
            features['trend_dir'] = 0

        # --- D) Momentum / Oscillators ---
        features['rsi14'] = self.rsi.get()

        macd_val, signal_val, hist_val = self.macd.get()
        features['macd'] = macd_val
        features['macd_signal'] = signal_val
        features['macd_hist'] = hist_val

        # --- E) Range / Levels ---
        don_upper, don_lower = self.donchian.get()
        features['donchian_high_32'] = don_upper
        features['donchian_low_32'] = don_lower

        # Breakout distance in ATR units
        if atr_val > 1e-12:
            features['breakout_dist_atr'] = (close - don_upper) / atr_val
        else:
            features['breakout_dist_atr'] = 0.0

        # Pullback distances to EMAs in ATR units
        ema20_val = features['ema20']
        if atr_val > 1e-12:
            features['pullback_dist_ema20_atr'] = (close - ema20_val) / atr_val
            features['pullback_dist_ema50_atr'] = (close - ema50_val) / atr_val
        else:
            features['pullback_dist_ema20_atr'] = 0.0
            features['pullback_dist_ema50_atr'] = 0.0

        # Bollinger Bands
        bb_upper, bb_mid, bb_lower = self.bb.get()
        features['bb_mid'] = bb_mid
        features['bb_upper'] = bb_upper
        features['bb_lower'] = bb_lower
        features['bb_std'] = (bb_upper - bb_mid) / 2.0 if bb_upper > bb_mid else 0.0

        bb_width = self.bb.get_width()
        features['bb_width_bps'] = self._bps(bb_width)
        features['bb_pos'] = self.bb.get_position()

        # --- F) Volume / Liquidity ---
        turnover_usd = close * volume
        features['turnover_usd'] = turnover_usd

        # Average daily volume (ADV) - required key
        if self.turnover_window.is_full():
            features['adv_usd'] = self.turnover_window.mean()
        else:
            features['adv_usd'] = turnover_usd  # Use current as placeholder

        # Volume SMA and ratios
        if self.volume_window.is_full():
            vol_sma = self.volume_window.mean()
            features['vol_sma_96'] = vol_sma

            if vol_sma > 1e-12:
                features['volume_ratio_96'] = volume / vol_sma
            else:
                features['volume_ratio_96'] = 1.0

            # Volume z-score
            features['vol_z_96'] = self._zscore(
                volume,
                self.volume_window.mean(),
                self.volume_window.std()
            )
        else:
            features['vol_sma_96'] = volume
            features['volume_ratio_96'] = 1.0
            features['vol_z_96'] = 0.0

        # --- G) Microstructure ---
        # Spread is constant per asset (required key)
        features['spread_bps'] = self.spread_bps

        # Slippage estimate
        features['slippage_bps_est'] = 0.5 * self.spread_bps + 0.02 * atr_bps_val
        # Cap at 15 bps
        features['slippage_bps_est'] = min(features['slippage_bps_est'], 15.0)

        # --- H) Portfolio / Risk State (required keys) ---
        features['open_positions'] = open_positions
        features['exposure_frac'] = exposure_frac
        features['dd_24h_bps'] = dd_24h_bps
        features['halt_flag'] = halt_flag

        # --- I) Derivatives Context (optional, set to 0 if not available) ---
        features['funding_rate'] = 0.0
        features['funding_rate_24h_avg'] = 0.0
        features['open_interest_usd'] = 0.0
        features['open_interest_chg_24h_pct'] = 0.0
        features['derivs_data_available'] = 0

        # --- J) LLM Output (placeholder, will be set by system) ---
        features['llm_confidence'] = 0.0  # Required key, will be populated later

        return features

    def _safe_return(self, current: float, lookback: int) -> float:
        """
        Calculate return over lookback bars safely.

        Args:
            current: Current close price
            lookback: Number of bars to look back

        Returns:
            Simple return (current/past - 1)
        """
        if len(self.close_history) < lookback + 1:
            return 0.0

        past_price = self.close_history[-(lookback + 1)]

        if past_price < 1e-12:
            return 0.0

        return (current / past_price) - 1.0

    def _bps(self, value: float) -> float:
        """Convert to basis points."""
        return value * 10000.0

    def _zscore(self, value: float, mean: float, std: float) -> float:
        """
        Calculate z-score with safe division.

        Args:
            value: Current value
            mean: Mean of distribution
            std: Standard deviation of distribution

        Returns:
            Z-score
        """
        if std < 1e-12:
            return 0.0

        return (value - mean) / std

    def _compute_slope(
        self,
        history: list[float],
        lookback: int,
        normalize_by: float,
    ) -> float:
        """
        Compute slope over lookback bars, normalized and in bps.

        Args:
            history: Value history
            lookback: Number of bars for slope
            normalize_by: Value to normalize by (typically close price)

        Returns:
            Slope in basis points
        """
        if len(history) < lookback + 1:
            return 0.0

        current = history[-1]
        past = history[-(lookback + 1)]

        if normalize_by < 1e-12:
            return 0.0

        change = current - past
        return self._bps(change / normalize_by)

    def reset(self) -> None:
        """Reset pipeline state (useful for testing or restarting)."""
        self.bar_count = 0
        self.close_history.clear()
        self.logret_history.clear()
        self.ema20_history.clear()
        self.ema50_history.clear()

        # Reinitialize all indicators
        self.ema20 = EMAState(20)
        self.ema50 = EMAState(50)
        self.ema200 = EMAState(200)
        self.atr = ATRState(14)
        self.atr_bps_window = RollingWindow(96)
        self.adx = ADXState(14)
        self.rsi = RSIState(14)
        self.macd = MACDState(12, 26, 9)
        self.bb = BollingerBandsState(20, 2.0)
        self.donchian = DonchianState(32)
        self.volume_window = RollingWindow(96)
        self.turnover_window = RollingWindow(96)

        self.prev_close = None
        self.prev_high = None
        self.prev_low = None

    def is_warmed_up(self) -> bool:
        """Check if pipeline has completed warmup."""
        return self.bar_count >= self.warmup_bars

    def get_bar_count(self) -> int:
        """Get number of bars processed."""
        return self.bar_count
