"""Breakout playbook implementation."""

from typing import Dict, Optional

from darwin.playbooks.base import CandidateInfo, PlaybookBase
from darwin.schemas import ExitSpecV1


class BreakoutPlaybook(PlaybookBase):
    """
    Breakout strategy playbook.

    Concept:
        Trade continuation when price breaks a well-defined recent range
        with trend + volume confirmation.

    Entry Conditions (ALL must be true):
        1. close >= donchian_high_32 + 0.10 * ATR (break with buffer)
        2. ADX14 >= 18 (minimum trend strength)
        3. close > EMA200 (trend alignment)
        4. volume_ratio_96 >= 1.2 OR vol_z_96 >= 0.5 (volume confirmation)
        5. adv_usd >= 5,000,000 (minimum liquidity)

    Exit Specifications:
        - Stop Loss: 1.2 * ATR
        - Take Profit: 2.4 * ATR (~2R)
        - Time Stop: 32 bars (8 hours on 15m)
        - Trailing: Activates at +1.0R, trails at 1.2 * ATR

    Quality Indicators:
        - compression_present: BB width percentile < 20 over last 24 bars
        - vol_expansion: ATR increasing or atr_pct jump
        - volume_confirm: vol z-score > 0.5
    """

    def __init__(
        self,
        n_bars: int = 32,
        break_buffer_atr: float = 0.10,
        min_trend_strength: float = 18.0,
        min_vol_ratio: float = 1.2,
        min_vol_z: float = 0.5,
        min_adv_usd: float = 5_000_000.0,
        stop_loss_atr: float = 1.2,
        take_profit_atr: float = 2.4,
        time_stop_bars: int = 32,
        trailing_activation_r: float = 1.0,
        trailing_distance_atr: float = 1.2,
    ):
        """
        Initialize breakout playbook with parameters.

        Args:
            n_bars: Donchian channel lookback period (default: 32)
            break_buffer_atr: Buffer above high in ATR units (default: 0.10)
            min_trend_strength: Minimum ADX14 value (default: 18.0)
            min_vol_ratio: Minimum volume ratio (default: 1.2)
            min_vol_z: Minimum volume z-score (default: 0.5)
            min_adv_usd: Minimum average dollar volume (default: 5M)
            stop_loss_atr: Stop loss in ATR units (default: 1.2)
            take_profit_atr: Take profit in ATR units (default: 2.4)
            time_stop_bars: Time stop in bars (default: 32)
            trailing_activation_r: Trailing activation in R units (default: 1.0)
            trailing_distance_atr: Trailing distance in ATR units (default: 1.2)
        """
        self.n_bars = n_bars
        self.break_buffer_atr = break_buffer_atr
        self.min_trend_strength = min_trend_strength
        self.min_vol_ratio = min_vol_ratio
        self.min_vol_z = min_vol_z
        self.min_adv_usd = min_adv_usd
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
        Evaluate breakout entry conditions.

        Args:
            features: Feature dictionary with required keys:
                - close, atr, adx14, ema200, donchian_high_32
                - volume_ratio_96, vol_z_96, adv_usd
            bar_data: Raw OHLCV bar data

        Returns:
            CandidateInfo if all entry conditions met, None otherwise.
        """
        # Extract required features
        close = self._safe_get(features, "close", 0.0)
        atr = self._safe_get(features, "atr", 0.0)
        adx14 = self._safe_get(features, "adx14", 0.0)
        ema200 = self._safe_get(features, "ema200", 0.0)
        donchian_high_32 = self._safe_get(features, "donchian_high_32", 0.0)
        volume_ratio_96 = self._safe_get(features, "volume_ratio_96", 0.0)
        vol_z_96 = self._safe_get(features, "vol_z_96", 0.0)
        adv_usd = self._safe_get(features, "adv_usd", 0.0)

        # Guard against invalid values
        if close <= 0 or atr <= 0:
            return None

        # Calculate breakout threshold
        break_threshold = donchian_high_32 + (self.break_buffer_atr * atr)

        # Check entry conditions (ALL must be true)

        # 1. Price breaks above recent high with buffer
        if close < break_threshold:
            return None

        # 2. Minimum trend strength (ADX14)
        if adx14 < self.min_trend_strength:
            return None

        # 3. Trend alignment (close > EMA200)
        if close <= ema200:
            return None

        # 4. Volume confirmation (ratio OR z-score)
        volume_confirmed = (
            volume_ratio_96 >= self.min_vol_ratio or vol_z_96 >= self.min_vol_z
        )
        if not volume_confirmed:
            return None

        # 5. Minimum liquidity
        if adv_usd < self.min_adv_usd:
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
            break_threshold=break_threshold,
            adx14=adx14,
            volume_ratio_96=volume_ratio_96,
            vol_z_96=vol_z_96,
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
        Generate exit specification for breakout playbook.

        Args:
            entry_price: Entry price
            atr: ATR(14) value at entry
            direction: Trade direction ('long' or 'short')

        Returns:
            ExitSpecV1 with breakout-specific exit parameters.
        """
        if direction == "long":
            stop_loss_price = entry_price - (self.stop_loss_atr * atr)
            take_profit_price = entry_price + (self.take_profit_atr * atr)
            # Trailing activates at +1.0R (entry + 1.0 * stop_distance)
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
        Calculate quality indicators for breakout setup.

        Args:
            features: Feature dictionary

        Returns:
            Dictionary of quality flags.
        """
        # Compression present: BB width percentile < 20 over last 24 bars
        # Note: This requires historical percentile data, using simple heuristic for now
        bb_width_pct = self._safe_get(features, "bb_width_pct", 50.0)
        compression_present = bb_width_pct < 20.0

        # Vol expansion: ATR increasing or atr_pct jump
        atr_z_96 = self._safe_get(features, "atr_z_96", 0.0)
        vol_expansion = atr_z_96 > 0.3

        # Volume confirm: strict threshold
        vol_z_96 = self._safe_get(features, "vol_z_96", 0.0)
        volume_confirm = vol_z_96 > 0.5

        return {
            "compression_present": compression_present,
            "vol_expansion": vol_expansion,
            "volume_confirm": volume_confirm,
        }

    def _build_notes(
        self,
        close: float,
        break_threshold: float,
        adx14: float,
        volume_ratio_96: float,
        vol_z_96: float,
    ) -> str:
        """
        Build notes string for candidate.

        Args:
            close: Current close price
            break_threshold: Breakout threshold price
            adx14: ADX value
            volume_ratio_96: Volume ratio
            vol_z_96: Volume z-score

        Returns:
            Notes string describing the setup.
        """
        buffer_pct = ((close - break_threshold) / break_threshold) * 100
        return (
            f"Breakout: {buffer_pct:.2f}% above threshold, "
            f"ADX={adx14:.1f}, vol_ratio={volume_ratio_96:.2f}, "
            f"vol_z={vol_z_96:.2f}"
        )
