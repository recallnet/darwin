"""
Darwin Features Module

Provides incremental indicator implementations, feature pipeline,
and bucketing functions for LLM-assisted trading.
"""

# Indicator classes
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

# Feature pipeline
from darwin.features.pipeline import FeaturePipelineV1
# Backwards compatibility alias
FeaturePipeline = FeaturePipelineV1

# Bucketing functions
from darwin.features.bucketing import (
    bucket_trend_mode,
    bucket_vol_mode,
    bucket_momentum,
    bucket_range_state,
    bucket_chop_score,
    bucket_rr,
    bucket_volume_regime,
    bucket_price_location,
    bucket_setup_stage,
    bucket_distance_to_structure,
    bucket_risk_mode,
    bucket_drawdown,
    bucket_trend_strength_pct,
    bucket_vol_pct,
    compute_risk_budget,
    bucket_quality_grade,
)

__all__ = [
    # Indicators
    "RollingWindow",
    "EMAState",
    "WilderEMAState",
    "ATRState",
    "ADXState",
    "RSIState",
    "MACDState",
    "BollingerBandsState",
    "DonchianState",
    # Pipeline
    "FeaturePipelineV1",
    "FeaturePipeline",  # Backwards compatibility
    # Bucketing
    "bucket_trend_mode",
    "bucket_vol_mode",
    "bucket_momentum",
    "bucket_range_state",
    "bucket_chop_score",
    "bucket_rr",
    "bucket_volume_regime",
    "bucket_price_location",
    "bucket_setup_stage",
    "bucket_distance_to_structure",
    "bucket_risk_mode",
    "bucket_drawdown",
    "bucket_trend_strength_pct",
    "bucket_vol_pct",
    "compute_risk_budget",
    "bucket_quality_grade",
]
