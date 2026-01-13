"""LLM response schema."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class RiskFlag(str, Enum):
    """Risk flags that LLM can identify."""

    CROWDED_LONGS = "crowded_longs"
    CROWDED_SHORTS = "crowded_shorts"
    LATE_ENTRY = "late_entry"
    HIGH_CHOP = "high_chop"
    NO_VOLUME_CONFIRM = "no_volume_confirm"
    REGIME_MISMATCH = "regime_mismatch"
    WEAK_SETUP = "weak_setup"
    EXTENDED_MOVE = "extended_move"
    LOW_LIQUIDITY = "low_liquidity"


class LLMResponseV1(BaseModel):
    """
    LLM response schema (strict JSON output).

    This is parsed from the LLM's output and validated.
    """

    decision: str = Field(..., description="take | skip")
    setup_quality: str = Field(..., description="A+ | A | B | C")
    confidence: float = Field(..., description="Confidence score [0.0, 1.0]")
    risk_flags: List[str] = Field(default_factory=list, description="Risk flags identified")
    notes: Optional[str] = Field(None, description="One or two sentences max")

    @field_validator("decision")
    @classmethod
    def decision_must_be_valid(cls, v: str) -> str:
        if v not in ["take", "skip"]:
            raise ValueError(f"decision must be 'take' or 'skip', got '{v}'")
        return v

    @field_validator("setup_quality")
    @classmethod
    def setup_quality_must_be_valid(cls, v: str) -> str:
        if v not in ["A+", "A", "B", "C"]:
            raise ValueError(f"setup_quality must be 'A+', 'A', 'B', or 'C', got '{v}'")
        return v

    @field_validator("confidence")
    @classmethod
    def confidence_must_be_in_range(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {v}")
        return v

    @field_validator("notes")
    @classmethod
    def notes_must_be_short(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 500:
            raise ValueError(f"notes must be <= 500 characters, got {len(v)}")
        return v

    class Config:
        use_enum_values = True
