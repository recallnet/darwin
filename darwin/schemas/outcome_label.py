"""Outcome label schema."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class OutcomeLabelV1(BaseModel):
    """
    Post-hoc outcome label attached to a candidate.

    These labels are computed after the fact to enable:
    - Supervised learning (predict LLM decision quality)
    - Reinforcement learning (optimize gate/budget policies)
    - Counterfactual analysis (what if we took skipped candidates?)
    """

    # Identity
    label_id: str = Field(..., description="Unique label identifier")
    candidate_id: str = Field(..., description="Candidate ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Label creation timestamp")

    # Actual outcome (if taken)
    was_taken: bool = Field(..., description="Whether candidate was actually traded")
    position_id: Optional[str] = Field(None, description="Position ID if taken")
    actual_pnl_usd: Optional[float] = Field(None, description="Actual PnL if taken")
    actual_r_multiple: Optional[float] = Field(None, description="Actual R multiple if taken")
    actual_exit_reason: Optional[str] = Field(None, description="Actual exit reason if taken")

    # Counterfactual outcome (if skipped)
    counterfactual_pnl_usd: Optional[float] = Field(
        None, description="Simulated PnL if we had taken it"
    )
    counterfactual_r_multiple: Optional[float] = Field(
        None, description="Simulated R multiple if we had taken it"
    )
    counterfactual_exit_reason: Optional[str] = Field(
        None, description="Simulated exit reason if we had taken it"
    )

    # Policy-specific labels
    policy_labels: Dict[str, Any] = Field(
        default_factory=dict,
        description="Policy-specific labels (e.g., 'should_have_taken', 'quality_score')"
    )

    # Feature snapshot (optional, for offline learning)
    feature_snapshot: Optional[Dict[str, float]] = Field(
        None, description="Feature snapshot at decision time"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
