"""Pullback playbook implementation."""

from typing import Dict, Optional

from darwin.playbooks.base import CandidateInfo, PlaybookBase
from darwin.schemas import ExitSpecV1


class PullbackPlaybook(PlaybookBase):
    """
    Pullback strategy playbook.

    Concept:
        In an uptrend, buy the dip when price pulls back to a moving average band,
        shows stabilization, and resumes upward momentum.

    Entry Conditions (ALL must be true):
        1. EMA50 > EMA200 (uptrend)
        2. ADX14 >= 16 (minimum trend strength)
        3. low <= EMA20 AND close >= EMA20 (tagged EMA20 and reclaimed by close)
        4. close >= open OR close > close[-1] (reversal confirmation)
        5. RSI14 <= 55 (not overheated)
        6. Optional: distance_to_EMA50 <= 1.0 * ATR

    Exit Specifications:
        - Stop Loss: 1.0 * ATR
        - Take Profit: 1.8 * ATR (~1.8R)
        - Time Stop: 48 bars (12 hours on 15m)
        - Trailing: Activates at +0.8R, trails at 1.0 * ATR

    Quality Indicators:
        - ema_alignment: EMA50 > EMA200 and slopes positive
        - pullback_depth: How deep the pullback is (distance to EMA50)
        - reversal_confirm: Bullish close or higher close
    """

    def __init__(
        self,
        min_trend_strength: float = 16.0,
        max_rsi: float = 55.0,
        max_distance_to_ema50_atr: float = 1.0,
        check_ema50_distance: bool = True,
        stop_loss_atr: float = 1.0,
        take_profit_atr: float = 1.8,
        time_stop_bars: int = 48,
        trailing_activation_r: float = 0.8,
        trailing_distance_atr: float = 1.0,
    ):
        """
        Initialize pullback playbook with parameters.

        Args:
            min_trend_strength: Minimum ADX14 value (default: 16.0)
            max_rsi: Maximum RSI14 value (default: 55.0)
            max_distance_to_ema50_atr: Max distance to EMA50 in ATR (default: 1.0)
            check_ema50_distance: Whether to enforce EMA50 distance check (default: True)
            stop_loss_atr: Stop loss in ATR units (default: 1.0)
            take_profit_atr: Take profit in ATR units (default: 1.8)
            time_stop_bars: Time stop in bars (default: 48)
            trailing_activation_r: Trailing activation in R units (default: 0.8)
            trailing_distance_atr: Trailing distance in ATR units (default: 1.0)
        """
        self.min_trend_strength = min_trend_strength
        self.max_rsi = max_rsi
        self.max_distance_to_ema50_atr = max_distance_to_ema50_atr
        self.check_ema50_distance = check_ema50_distance
        self.stop_loss_atr = stop_loss_atr
        self.take_profit_atr = take_profit_atr
        self.time_stop_bars = time_stop_bars
        self.trailing_activation_r = trailing_activation_r
        self.trailing_distance_atr = trailing_distance_atr

    def evaluate(
        self,
        features: Dict[str, float],
        bar_data: Dict[str, float],
    ) -> Optional[CandidateInfo]:
        """
        Evaluate pullback entry conditions.

        Args:
            features: Feature dictionary with required keys:
                - close, open, low, atr, adx14, rsi14
                - ema20, ema50, ema200
                - pullback_dist_ema50_atr
                - prev_close (close[t-1])
            bar_data: Raw OHLCV bar data

        Returns:
            CandidateInfo if all entry conditions met, None otherwise.
        """
        # Extract required features
        close = self._safe_get(features, "close", 0.0)
        open_price = self._safe_get(features, "open", 0.0)
        low = self._safe_get(features, "low", 0.0)
        atr = self._safe_get(features, "atr", 0.0)
        adx14 = self._safe_get(features, "adx14", 0.0)
        rsi14 = self._safe_get(features, "rsi14", 50.0)
        ema20 = self._safe_get(features, "ema20", 0.0)
        ema50 = self._safe_get(features, "ema50", 0.0)
        ema200 = self._safe_get(features, "ema200", 0.0)
        prev_close = self._safe_get(features, "prev_close", close)
        pullback_dist_ema50_atr = self._safe_get(features, "pullback_dist_ema50_atr", 0.0)

        # Guard against invalid values
        if close <= 0 or atr <= 0:
            return None

        # Check entry conditions (ALL must be true)

        # 1. Uptrend: EMA50 > EMA200
        if ema50 <= ema200:
            return None

        # 2. Minimum trend strength (ADX14)
        if adx14 < self.min_trend_strength:
            return None

        # 3. Tagged EMA20 and reclaimed by close
        # low <= EMA20 (tagged) AND close >= EMA20 (reclaimed)
        if not (low <= ema20 and close >= ema20):
            return None

        # 4. Reversal confirmation: bullish close OR higher close
        reversal_confirmed = (close >= open_price) or (close > prev_close)
        if not reversal_confirmed:
            return None

        # 5. Not overheated (RSI <= 55)
        if rsi14 > self.max_rsi:
            return None

        # 6. Optional: Distance to EMA50 check
        if self.check_ema50_distance:
            if pullback_dist_ema50_atr > self.max_distance_to_ema50_atr:
                return None

        # All conditions met - calculate quality indicators
        quality_flags = self._calculate_quality_flags(features)

        # Generate exit spec
        exit_spec = self.get_exit_spec(
            entry_price=close,
            atr=atr,
            direction="long"
        )

        # Build notes
        notes = self._build_notes(
            close=close,
            ema20=ema20,
            adx14=adx14,
            rsi14=rsi14,
            pullback_dist_ema50_atr=pullback_dist_ema50_atr,
        )

        return CandidateInfo(
            entry_price=close,
            atr_at_entry=atr,
            exit_spec=exit_spec,
            quality_flags=quality_flags,
            notes=notes,
        )

    def get_exit_spec(
        self,
        entry_price: float,
        atr: float,
        direction: str = "long"
    ) -> ExitSpecV1:
        """
        Generate exit specification for pullback playbook.

        Args:
            entry_price: Entry price
            atr: ATR(14) value at entry
            direction: Trade direction ('long' or 'short')

        Returns:
            ExitSpecV1 with pullback-specific exit parameters.
        """
        if direction == "long":
            stop_loss_price = entry_price - (self.stop_loss_atr * atr)
            take_profit_price = entry_price + (self.take_profit_atr * atr)
            # Trailing activates at +0.8R (entry + 0.8 * stop_distance)
            stop_distance = self.stop_loss_atr * atr
            trailing_activation_price = entry_price + (self.trailing_activation_r * stop_distance)
        else:
            # Short logic (for future implementation)
            stop_loss_price = entry_price + (self.stop_loss_atr * atr)
            take_profit_price = entry_price - (self.take_profit_atr * atr)
            stop_distance = self.stop_loss_atr * atr
            trailing_activation_price = entry_price - (self.trailing_activation_r * stop_distance)

        return ExitSpecV1(
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            time_stop_bars=self.time_stop_bars,
            trailing_enabled=True,
            trailing_activation_price=trailing_activation_price,
            trailing_distance_atr=self.trailing_distance_atr,
        )

    def _calculate_quality_flags(self, features: Dict[str, float]) -> Dict[str, bool]:
        """
        Calculate quality indicators for pullback setup.

        Args:
            features: Feature dictionary

        Returns:
            Dictionary of quality flags.
        """
        # EMA alignment: EMA50 > EMA200 and slopes positive
        ema50 = self._safe_get(features, "ema50", 0.0)
        ema200 = self._safe_get(features, "ema200", 0.0)
        ema20_slope_bps = self._safe_get(features, "ema20_slope_bps", 0.0)
        ema50_slope_bps = self._safe_get(features, "ema50_slope_bps", 0.0)

        ema_alignment = (
            ema50 > ema200
            and ema20_slope_bps > 0
            and ema50_slope_bps > 0
        )

        # Pullback depth: shallow pullback is better quality
        pullback_dist_ema50_atr = self._safe_get(features, "pullback_dist_ema50_atr", 0.0)
        pullback_depth_shallow = abs(pullback_dist_ema50_atr) < 0.5

        # Reversal confirm: bullish close
        close = self._safe_get(features, "close", 0.0)
        open_price = self._safe_get(features, "open", 0.0)
        prev_close = self._safe_get(features, "prev_close", close)

        reversal_confirm = (close >= open_price) or (close > prev_close)

        return {
            "ema_alignment": ema_alignment,
            "pullback_depth_shallow": pullback_depth_shallow,
            "reversal_confirm": reversal_confirm,
        }

    def _build_notes(
        self,
        close: float,
        ema20: float,
        adx14: float,
        rsi14: float,
        pullback_dist_ema50_atr: float,
    ) -> str:
        """
        Build notes string for candidate.

        Args:
            close: Current close price
            ema20: EMA20 value
            adx14: ADX value
            rsi14: RSI value
            pullback_dist_ema50_atr: Distance to EMA50 in ATR units

        Returns:
            Notes string describing the setup.
        """
        distance_to_ema20_pct = ((close - ema20) / ema20) * 100
        return (
            f"Pullback: {distance_to_ema20_pct:.2f}% from EMA20, "
            f"ADX={adx14:.1f}, RSI={rsi14:.1f}, "
            f"dist_to_EMA50={pullback_dist_ema50_atr:.2f}ATR"
        )
