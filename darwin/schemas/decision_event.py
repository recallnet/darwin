"""Decision event schema."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class DecisionType(str, Enum):
    """Type of decision."""

    TAKE = "take"
    SKIP = "skip"


class SetupQuality(str, Enum):
    """Setup quality assessment."""

    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"


class DecisionEventV1(BaseModel):
    """
    Decision event recorded in decision_events.jsonl.

    One event per candidate evaluation.
    """

    # Identity
    event_id: str = Field(..., description="Unique event identifier")
    candidate_id: str = Field(..., description="Candidate ID")
    run_id: str = Field(..., description="Run ID")
    timestamp: datetime = Field(..., description="Event timestamp")

    # Context
    symbol: str = Field(..., description="Trading symbol")
    playbook: str = Field(..., description="Playbook name")
    bar_index: int = Field(..., description="Bar index")

    # LLM decision
    decision: DecisionType = Field(..., description="Decision: take or skip")
    setup_quality: SetupQuality = Field(..., description="Setup quality")
    confidence: float = Field(..., description="Confidence score [0, 1]")
    risk_flags: List[str] = Field(default_factory=list, description="Risk flags identified")
    notes: Optional[str] = Field(None, description="LLM notes")

    # Gate/budget result
    passed_gate: bool = Field(..., description="Whether candidate passed gate policy")
    rejection_reason: Optional[str] = Field(
        None, description="Reason for rejection if didn't pass gate"
    )

    # Execution
    was_executed: bool = Field(..., description="Whether trade was actually executed")

    # Prompt version tracking
    prompt_version: str = Field(default="v1", description="Prompt version used")

    # Fallback indicator
    fallback_used: bool = Field(default=False, description="Whether fallback decision was used")
    llm_error: Optional[str] = Field(None, description="LLM error if fallback was used")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        use_enum_values = True
