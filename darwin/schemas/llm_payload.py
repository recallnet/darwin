"""LLM payload schema - what the LLM sees."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GlobalRegimeV1(BaseModel):
    """Global market regime (BTC 4h context)."""

    risk_mode: str = Field(..., description="risk_on | neutral | risk_off")
    risk_budget: float = Field(..., description="0.0/0.1/0.25/0.5/1.0")
    trend_mode: str = Field(..., description="up | sideways | down")
    trend_strength_pct: float = Field(..., description="0-100")
    vol_mode: str = Field(..., description="low | normal | high")
    vol_pct: float = Field(..., description="0-100")
    drawdown_bucket: str = Field(..., description="none | small | medium | large")


class TrendInfo(BaseModel):
    """Trend information."""

    direction: str = Field(..., description="up | sideways | down")
    strength_pct: float = Field(..., description="0-100")


class VolatilityInfo(BaseModel):
    """Volatility information."""

    atr_pct_15m: float = Field(..., description="ATR as % of price")
    atr_pct_1h: float = Field(..., description="ATR as % of price (1h)")
    vol_regime_15m: str = Field(..., description="low | normal | high")


class VolumeInfo(BaseModel):
    """Volume information."""

    regime_15m: str = Field(..., description="low | normal | high")
    zscore_15m: float = Field(..., description="Z-score of volume")


class AssetStateV1(BaseModel):
    """Asset-specific state (per symbol, 15m + 1h)."""

    symbol: str = Field(..., description="Trading symbol")
    price_location_1h: str = Field(..., description="above_key_ma | near_key_ma | below_key_ma")
    trend_1h: TrendInfo = Field(..., description="Trend information")
    momentum_15m: str = Field(..., description="strong_up | mild_up | flat | mild_down | strong_down")
    volatility: VolatilityInfo = Field(..., description="Volatility information")
    volume: VolumeInfo = Field(..., description="Volume information")
    range_state_15m: str = Field(..., description="contracting | normal | expanding")
    chop_score: str = Field(..., description="low | medium | high")
    recent_events: List[str] = Field(default_factory=list, description="Recent event flags")


class CandidateSetupV1(BaseModel):
    """Candidate setup card (playbook-specific)."""

    playbook: str = Field(..., description="breakout | pullback")
    direction: str = Field(..., description="long | short")
    setup_stage: str = Field(..., description="early | ok | late")
    trigger_type: str = Field(..., description="Varies by playbook")
    stop_atr: float = Field(..., description="Stop loss in ATR units")
    expected_rr_bucket: str = Field(..., description="<1.5 | 1.5-2 | 2-3 | >3")
    distance_to_structure: str = Field(..., description="near | medium | far")

    # Playbook-specific quality indicators
    quality_indicators: Dict[str, Any] = Field(
        default_factory=dict, description="Playbook-specific indicators"
    )


class PolicyConstraintsV1(BaseModel):
    """Policy constraints for decision-making."""

    required_quality: str = Field(..., description="A+ | A | A-")
    max_risk_budget: float = Field(..., description="Maximum risk budget")
    notes: str = Field(default="", description="Additional policy notes")


class LLMPayloadV1(BaseModel):
    """
    Complete LLM payload.

    This is what the LLM sees when evaluating a candidate.
    """

    global_regime: GlobalRegimeV1 = Field(..., description="Global market regime")
    asset_state: AssetStateV1 = Field(..., description="Asset-specific state")
    candidate_setup: CandidateSetupV1 = Field(..., description="Candidate setup")
    policy_constraints: PolicyConstraintsV1 = Field(..., description="Policy constraints")

    # Optional derivatives data
    derivatives: Optional[Dict[str, Any]] = Field(
        None, description="Derivatives data if available"
    )

    # Metadata
    candidate_id: str = Field(..., description="Candidate identifier")
    timestamp: str = Field(..., description="Timestamp")
