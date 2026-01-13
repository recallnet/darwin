"""Candidate record schema."""

from datetime import datetime
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field


class PlaybookType(str, Enum):
    """Type of playbook."""

    BREAKOUT = "breakout"
    PULLBACK = "pullback"


class ExitSpecV1(BaseModel):
    """Exit specification for a candidate."""

    stop_loss_price: float = Field(..., description="Stop loss price")
    take_profit_price: float = Field(..., description="Take profit price")
    time_stop_bars: int = Field(..., description="Time stop in bars")
    trailing_enabled: bool = Field(..., description="Whether trailing stop is enabled")
    trailing_activation_price: Optional[float] = Field(
        None, description="Price level to activate trailing"
    )
    trailing_distance_atr: Optional[float] = Field(None, description="Trailing distance in ATR units")


class CandidateRecordV1(BaseModel):
    """
    Candidate record stored in cache.

    Every opportunity (taken or skipped) is stored as a candidate.
    This forms the learning substrate for future RL/supervised learning.
    """

    # Identity
    candidate_id: str = Field(..., description="Unique candidate identifier")
    run_id: str = Field(..., description="Run ID that generated this candidate")
    timestamp: datetime = Field(..., description="Bar timestamp when candidate was generated")

    # Market context
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Timeframe")
    bar_index: int = Field(..., description="Bar index in the run")

    # Playbook
    playbook: PlaybookType = Field(..., description="Playbook that generated this candidate")
    direction: str = Field(..., description="Direction: 'long' or 'short'")

    # Entry details
    entry_price: float = Field(..., description="Proposed entry price (next open)")
    atr_at_entry: float = Field(..., description="ATR value at entry")

    # Exit specification
    exit_spec: ExitSpecV1 = Field(..., description="Exit specification")

    # Features (stored as JSON)
    features: Dict[str, float] = Field(..., description="Feature vector")

    # LLM decision
    llm_decision: Optional[str] = Field(None, description="LLM decision: 'take' or 'skip'")
    llm_confidence: Optional[float] = Field(None, description="LLM confidence [0, 1]")
    llm_setup_quality: Optional[str] = Field(None, description="LLM setup quality assessment")

    # References to stored artifacts
    payload_ref: Optional[str] = Field(None, description="Path to stored LLM payload")
    response_ref: Optional[str] = Field(None, description="Path to stored LLM response")

    # Execution
    was_taken: bool = Field(..., description="Whether this candidate was actually traded")
    rejection_reason: Optional[str] = Field(
        None, description="Reason for rejection if not taken"
    )

    # Outcome (attached later via labels)
    position_id: Optional[str] = Field(None, description="Position ID if trade was taken")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        use_enum_values = True
