"""Position record schema."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ExitReason(str, Enum):
    """Reason for position exit."""

    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    TIME_STOP = "time_stop"
    MANUAL = "manual"
    END_OF_RUN = "end_of_run"


class PositionRowV1(BaseModel):
    """
    Position record in ledger.

    The position ledger is the single source of truth for PnL.
    """

    # Identity
    position_id: str = Field(..., description="Unique position identifier")
    run_id: str = Field(..., description="Run ID")
    candidate_id: str = Field(..., description="Candidate ID that triggered this position")

    # Market context
    symbol: str = Field(..., description="Trading symbol")
    direction: str = Field(..., description="long | short")

    # Entry
    entry_timestamp: datetime = Field(..., description="Entry timestamp")
    entry_bar_index: int = Field(..., description="Entry bar index")
    entry_price: float = Field(..., description="Actual entry price (with slippage)")
    entry_fees_usd: float = Field(..., description="Entry fees in USD")
    size_usd: float = Field(..., description="Position size in USD")
    size_units: float = Field(..., description="Position size in units")

    # Exit
    exit_timestamp: Optional[datetime] = Field(None, description="Exit timestamp (null if open)")
    exit_bar_index: Optional[int] = Field(None, description="Exit bar index (null if open)")
    exit_price: Optional[float] = Field(None, description="Exit price (null if open)")
    exit_fees_usd: Optional[float] = Field(None, description="Exit fees in USD (null if open)")
    exit_reason: Optional[ExitReason] = Field(None, description="Exit reason (null if open)")

    # PnL
    pnl_usd: Optional[float] = Field(None, description="Realized PnL in USD (null if open)")
    pnl_pct: Optional[float] = Field(None, description="Realized PnL as % (null if open)")
    r_multiple: Optional[float] = Field(None, description="R multiple (null if open)")

    # Exit spec (stored for reference)
    stop_loss_price: float = Field(..., description="Initial stop loss price")
    take_profit_price: float = Field(..., description="Take profit price")
    time_stop_bars: int = Field(..., description="Time stop bars")

    # Trailing stop tracking
    trailing_enabled: bool = Field(..., description="Whether trailing was enabled")
    trailing_activated: bool = Field(default=False, description="Whether trailing was activated")
    highest_price: Optional[float] = Field(None, description="Highest price since entry (for trailing)")
    lowest_price: Optional[float] = Field(None, description="Lowest price since entry (for trailing)")

    # Status
    is_open: bool = Field(default=True, description="Whether position is open")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        use_enum_values = True
