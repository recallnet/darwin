"""
Feature bucketing functions for LLM context.

Converts continuous features into discrete, human-readable categories
that the LLM can reason about more effectively.
"""

from typing import Literal


def bucket_trend_mode(
    ema50: float,
    ema200: float,
    adx: float,
    threshold_low: float = 15.0,
    threshold_high: float = 25.0,
) -> Literal["up", "sideways", "down"]:
    """
    Bucket trend into up/sideways/down based on EMA alignment and ADX.

    Args:
        ema50: EMA50 value
        ema200: EMA200 value
        adx: ADX value
        threshold_low: ADX threshold below which trend is sideways (default 15)
        threshold_high: ADX threshold above which trend is strong (default 25)

    Returns:
        "up" | "sideways" | "down"
    """
    # Weak trend = sideways
    if adx < threshold_low:
        return "sideways"

    # Strong trend = up or down based on EMA alignment
    if ema50 > ema200:
        return "up"
    elif ema50 < ema200:
        return "down"
    else:
        return "sideways"


def bucket_vol_mode(
    atr_z: float,
    threshold_low: float = -0.5,
    threshold_high: float = 0.5,
) -> Literal["low", "normal", "high"]:
    """
    Bucket volatility into low/normal/high based on ATR z-score.

    Args:
        atr_z: ATR z-score (typically over 96 bars)
        threshold_low: Z-score below which vol is low (default -0.5)
        threshold_high: Z-score above which vol is high (default 0.5)

    Returns:
        "low" | "normal" | "high"
    """
    if atr_z < threshold_low:
        return "low"
    elif atr_z > threshold_high:
        return "high"
    else:
        return "normal"


def bucket_momentum(
    rsi: float,
    macd_hist: float,
    threshold_strong: float = 10.0,
    threshold_mild: float = 3.0,
) -> Literal["strong_up", "mild_up", "flat", "mild_down", "strong_down"]:
    """
    Bucket momentum into 5 categories based on RSI and MACD histogram.

    Args:
        rsi: RSI value (0-100)
        macd_hist: MACD histogram value
        threshold_strong: Strong momentum threshold (default 10)
        threshold_mild: Mild momentum threshold (default 3)

    Returns:
        "strong_up" | "mild_up" | "flat" | "mild_down" | "strong_down"
    """
    # Use RSI as primary indicator
    rsi_neutral = 50.0

    # Strong momentum
    if rsi > 65 and macd_hist > threshold_strong:
        return "strong_up"
    if rsi < 35 and macd_hist < -threshold_strong:
        return "strong_down"

    # Mild momentum
    if rsi > 55 or macd_hist > threshold_mild:
        return "mild_up"
    if rsi < 45 or macd_hist < -threshold_mild:
        return "mild_down"

    return "flat"


def bucket_range_state(
    bb_width_bps: float,
    percentile_rank: float,
    threshold_low: float = 30.0,
    threshold_high: float = 70.0,
) -> Literal["contracting", "normal", "expanding"]:
    """
    Bucket range state based on Bollinger Band width percentile.

    Args:
        bb_width_bps: Bollinger Band width in basis points
        percentile_rank: Percentile rank of BB width (0-100)
        threshold_low: Percentile below which range is contracting (default 30)
        threshold_high: Percentile above which range is expanding (default 70)

    Returns:
        "contracting" | "normal" | "expanding"
    """
    if percentile_rank < threshold_low:
        return "contracting"
    elif percentile_rank > threshold_high:
        return "expanding"
    else:
        return "normal"


def bucket_chop_score(
    close_current: float,
    close_history: list[float],
    lookback: int = 32,
) -> tuple[float, Literal["low", "medium", "high"]]:
    """
    Compute and bucket chop score (trend efficiency metric).

    Chop score = 1 - (net_movement / total_path_length)
    Higher chop = more sideways/choppy price action

    Args:
        close_current: Current close price
        close_history: List of historical close prices (most recent last)
        lookback: Number of bars to look back (default 32)

    Returns:
        Tuple of (chop_score, chop_bucket)
    """
    if len(close_history) < lookback:
        return 0.5, "medium"

    # Get last N bars (including current)
    prices = list(close_history[-(lookback-1):]) + [close_current]

    if len(prices) != lookback:
        return 0.5, "medium"

    # Calculate net movement
    net = abs(prices[-1] - prices[0])

    # Calculate total path length
    path = sum(abs(prices[i] - prices[i-1]) for i in range(1, len(prices)))

    # Avoid division by zero
    if path < 1e-12:
        return 0.5, "medium"

    # Chop score (0 = trending, 1 = choppy)
    efficiency = net / path
    chop = 1.0 - efficiency

    # Bucket
    if chop < 0.4:
        bucket = "low"  # Trending
    elif chop > 0.7:
        bucket = "high"  # Choppy
    else:
        bucket = "medium"

    return chop, bucket


def bucket_rr(
    expected_gain_atr: float,
    stop_atr: float,
) -> Literal["<1.5", "1.5-2", "2-3", ">3"]:
    """
    Bucket risk-reward ratio into categories.

    Args:
        expected_gain_atr: Expected gain in ATR units
        stop_atr: Stop loss in ATR units

    Returns:
        "<1.5" | "1.5-2" | "2-3" | ">3"
    """
    if stop_atr < 1e-12:
        return "<1.5"

    rr = expected_gain_atr / stop_atr

    if rr < 1.5:
        return "<1.5"
    elif rr < 2.0:
        return "1.5-2"
    elif rr < 3.0:
        return "2-3"
    else:
        return ">3"


def bucket_volume_regime(
    vol_z: float,
    threshold_low: float = -0.5,
    threshold_high: float = 0.5,
) -> Literal["low", "normal", "high"]:
    """
    Bucket volume regime based on z-score.

    Args:
        vol_z: Volume z-score
        threshold_low: Z-score below which volume is low (default -0.5)
        threshold_high: Z-score above which volume is high (default 0.5)

    Returns:
        "low" | "normal" | "high"
    """
    if vol_z < threshold_low:
        return "low"
    elif vol_z > threshold_high:
        return "high"
    else:
        return "normal"


def bucket_price_location(
    close: float,
    ema20: float,
    ema50: float,
    ema200: float,
    atr: float,
    threshold_near: float = 0.5,
) -> Literal["above_key_ma", "near_key_ma", "below_key_ma"]:
    """
    Bucket price location relative to key moving averages.

    Args:
        close: Current close price
        ema20: EMA20 value
        ema50: EMA50 value
        ema200: EMA200 value
        atr: ATR value
        threshold_near: ATR distance to be considered "near" (default 0.5)

    Returns:
        "above_key_ma" | "near_key_ma" | "below_key_ma"
    """
    if atr < 1e-12:
        return "near_key_ma"

    # Check distance to each MA in ATR units
    dist_20 = abs(close - ema20) / atr
    dist_50 = abs(close - ema50) / atr
    dist_200 = abs(close - ema200) / atr

    # Near any key MA?
    if min(dist_20, dist_50, dist_200) < threshold_near:
        return "near_key_ma"

    # Above all key MAs?
    if close > ema20 and close > ema50 and close > ema200:
        return "above_key_ma"

    # Below all key MAs?
    if close < ema20 and close < ema50 and close < ema200:
        return "below_key_ma"

    # Mixed (near but not at any specific MA)
    return "near_key_ma"


def bucket_setup_stage(
    time_since_trigger: int,
    max_early: int = 2,
    max_ok: int = 8,
) -> Literal["early", "ok", "late"]:
    """
    Bucket setup stage based on time since trigger.

    Args:
        time_since_trigger: Bars since setup trigger
        max_early: Max bars for "early" stage (default 2)
        max_ok: Max bars for "ok" stage (default 8)

    Returns:
        "early" | "ok" | "late"
    """
    if time_since_trigger <= max_early:
        return "early"
    elif time_since_trigger <= max_ok:
        return "ok"
    else:
        return "late"


def bucket_distance_to_structure(
    distance_atr: float,
    threshold_near: float = 0.3,
    threshold_far: float = 1.0,
) -> Literal["near", "medium", "far"]:
    """
    Bucket distance to key structure level in ATR units.

    Args:
        distance_atr: Distance in ATR units (absolute value)
        threshold_near: ATR distance for "near" (default 0.3)
        threshold_far: ATR distance for "far" (default 1.0)

    Returns:
        "near" | "medium" | "far"
    """
    abs_dist = abs(distance_atr)

    if abs_dist < threshold_near:
        return "near"
    elif abs_dist < threshold_far:
        return "medium"
    else:
        return "far"


def bucket_risk_mode(
    dd_24h_bps: float,
    vol_z: float,
    exposure_frac: float,
) -> Literal["risk_on", "neutral", "risk_off"]:
    """
    Bucket overall risk mode based on drawdown, volatility, and exposure.

    Args:
        dd_24h_bps: 24h drawdown in basis points
        vol_z: Volatility z-score
        exposure_frac: Current exposure fraction (0-1)

    Returns:
        "risk_on" | "neutral" | "risk_off"
    """
    # Risk-off conditions
    if dd_24h_bps > 500:  # >5% drawdown
        return "risk_off"
    if vol_z > 2.0:  # Extreme volatility
        return "risk_off"
    if exposure_frac > 0.8:  # Near max exposure
        return "risk_off"

    # Risk-on conditions
    if dd_24h_bps < 100 and vol_z < 0.5 and exposure_frac < 0.3:
        return "risk_on"

    return "neutral"


def bucket_drawdown(
    dd_24h_bps: float,
) -> Literal["none", "small", "medium", "large"]:
    """
    Bucket drawdown magnitude.

    Args:
        dd_24h_bps: 24h drawdown in basis points

    Returns:
        "none" | "small" | "medium" | "large"
    """
    if dd_24h_bps < 50:  # <0.5%
        return "none"
    elif dd_24h_bps < 200:  # <2%
        return "small"
    elif dd_24h_bps < 500:  # <5%
        return "medium"
    else:
        return "large"


def bucket_trend_strength_pct(
    adx: float,
    max_adx: float = 60.0,
) -> float:
    """
    Convert ADX to percentage (0-100).

    Args:
        adx: ADX value
        max_adx: Maximum ADX for scaling (default 60)

    Returns:
        Trend strength as percentage (0-100)
    """
    # Cap ADX at max_adx
    capped = min(adx, max_adx)

    # Convert to percentage
    return (capped / max_adx) * 100.0


def bucket_vol_pct(
    atr_z: float,
    max_z: float = 3.0,
) -> float:
    """
    Convert ATR z-score to percentage (0-100).

    Args:
        atr_z: ATR z-score
        max_z: Maximum z-score for scaling (default 3.0)

    Returns:
        Volatility as percentage (0-100)
    """
    # Shift and scale z-score to 0-100 range
    # z=-3 -> 0%, z=0 -> 50%, z=+3 -> 100%
    shifted = (atr_z + max_z) / (2 * max_z)

    # Clamp to 0-1
    clamped = max(0.0, min(1.0, shifted))

    return clamped * 100.0


def compute_risk_budget(
    risk_mode: Literal["risk_on", "neutral", "risk_off"],
    dd_24h_bps: float,
    vol_mode: Literal["low", "normal", "high"],
) -> float:
    """
    Compute risk budget multiplier based on current conditions.

    Args:
        risk_mode: Current risk mode
        dd_24h_bps: 24h drawdown in basis points
        vol_mode: Current volatility mode

    Returns:
        Risk budget multiplier (0.0 to 1.0)
    """
    # Base budget by risk mode
    if risk_mode == "risk_off":
        base = 0.1
    elif risk_mode == "neutral":
        base = 0.5
    else:  # risk_on
        base = 1.0

    # Adjust for drawdown
    if dd_24h_bps > 500:
        dd_factor = 0.1
    elif dd_24h_bps > 200:
        dd_factor = 0.5
    else:
        dd_factor = 1.0

    # Adjust for volatility
    if vol_mode == "high":
        vol_factor = 0.5
    elif vol_mode == "low":
        vol_factor = 1.2  # Can take more risk in low vol
    else:
        vol_factor = 1.0

    # Combine factors
    budget = base * dd_factor * vol_factor

    # Clamp to valid range
    return max(0.0, min(1.0, budget))


def bucket_quality_grade(
    score: float,
) -> Literal["A+", "A", "A-", "B", "C"]:
    """
    Convert numeric quality score to letter grade.

    Args:
        score: Quality score (0-100 or 0-1 depending on context)

    Returns:
        "A+" | "A" | "A-" | "B" | "C"
    """
    # Normalize to 0-100 if needed
    if score <= 1.0:
        score = score * 100.0

    if score >= 95:
        return "A+"
    elif score >= 85:
        return "A"
    elif score >= 75:
        return "A-"
    elif score >= 60:
        return "B"
    else:
        return "C"
