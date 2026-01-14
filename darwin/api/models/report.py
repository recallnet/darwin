"""
Pydantic models for report API.

Defines request and response schemas for:
- Performance metrics
- Equity curves
- Trade logs
- Candidate analysis
- Export formats
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class MetricsSummaryResponse(BaseModel):
    """Response model for performance metrics summary."""

    # Core performance metrics
    total_return: float = Field(..., description="Total return as decimal (0.15 = 15%)")
    total_return_pct: float = Field(..., description="Total return as percentage")
    sharpe_ratio: float = Field(..., description="Annualized Sharpe ratio")
    sortino_ratio: float = Field(..., description="Annualized Sortino ratio")
    max_drawdown: float = Field(..., description="Maximum drawdown as decimal")
    max_drawdown_pct: float = Field(..., description="Maximum drawdown as percentage")

    # Trade statistics
    total_trades: int = Field(..., description="Total number of closed trades")
    winning_trades: int = Field(..., description="Number of winning trades")
    losing_trades: int = Field(..., description="Number of losing trades")
    win_rate: float = Field(..., description="Win rate as decimal (0.6 = 60%)")
    win_rate_pct: float = Field(..., description="Win rate as percentage")

    # Risk/reward metrics
    profit_factor: float = Field(..., description="Profit factor (gross profits / gross losses)")
    avg_win_loss_ratio: float = Field(..., description="Average win / average loss ratio")

    # Equity
    starting_equity: float = Field(..., description="Starting equity in USD")
    final_equity: float = Field(..., description="Final equity in USD")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_return": 0.125,
                "total_return_pct": 12.5,
                "sharpe_ratio": 1.25,
                "sortino_ratio": 1.45,
                "max_drawdown": 0.08,
                "max_drawdown_pct": 8.0,
                "total_trades": 24,
                "winning_trades": 16,
                "losing_trades": 8,
                "win_rate": 0.667,
                "win_rate_pct": 66.7,
                "profit_factor": 1.8,
                "avg_win_loss_ratio": 1.5,
                "starting_equity": 10000.0,
                "final_equity": 11250.0,
            }
        }
    )


class EquityCurvePoint(BaseModel):
    """Single point on equity curve."""

    timestamp: datetime = Field(..., description="Bar timestamp")
    equity: float = Field(..., description="Equity value in USD")
    cumulative_pnl: float = Field(..., description="Cumulative PnL in USD")
    cumulative_return: float = Field(..., description="Cumulative return as decimal")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2024-01-15T10:30:00Z",
                "equity": 10250.0,
                "cumulative_pnl": 250.0,
                "cumulative_return": 0.025,
            }
        }
    )


class EquityCurveResponse(BaseModel):
    """Response model for equity curve data."""

    run_id: str = Field(..., description="Run ID")
    starting_equity: float = Field(..., description="Starting equity")
    final_equity: float = Field(..., description="Final equity")
    data_points: List[EquityCurvePoint] = Field(..., description="Equity curve data points")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "my-run-001",
                "starting_equity": 10000.0,
                "final_equity": 11250.0,
                "data_points": [
                    {
                        "timestamp": "2024-01-15T10:30:00Z",
                        "equity": 10250.0,
                        "cumulative_pnl": 250.0,
                        "cumulative_return": 0.025,
                    }
                ],
            }
        }
    )


class TradeListItem(BaseModel):
    """Trade item for list view."""

    position_id: str = Field(..., description="Position ID")
    symbol: str = Field(..., description="Trading symbol")
    direction: str = Field(..., description="Direction (long or short)")
    playbook: str = Field(..., description="Playbook name")

    # Entry/exit
    entry_timestamp: datetime = Field(..., description="Entry timestamp")
    entry_price: float = Field(..., description="Entry price")
    exit_timestamp: Optional[datetime] = Field(None, description="Exit timestamp")
    exit_price: Optional[float] = Field(None, description="Exit price")
    exit_reason: Optional[str] = Field(None, description="Exit reason")

    # Position size
    size_usd: float = Field(..., description="Position size in USD")
    size_units: float = Field(..., description="Position size in units")

    # Performance
    pnl_usd: Optional[float] = Field(None, description="PnL in USD")
    pnl_pct: Optional[float] = Field(None, description="PnL as percentage")
    r_multiple: Optional[float] = Field(None, description="R-multiple")

    # Duration
    bars_held: int = Field(..., description="Bars held")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "position_id": "pos_001",
                "symbol": "BTC-USD",
                "direction": "long",
                "playbook": "breakout",
                "entry_timestamp": "2024-01-15T10:30:00Z",
                "entry_price": 42000.0,
                "exit_timestamp": "2024-01-16T14:15:00Z",
                "exit_price": 43500.0,
                "exit_reason": "take_profit",
                "size_usd": 1000.0,
                "size_units": 0.0238,
                "pnl_usd": 85.0,
                "pnl_pct": 8.5,
                "r_multiple": 2.1,
                "bars_held": 24,
            }
        },
    )


class TradeListResponse(BaseModel):
    """Response model for paginated trade list."""

    run_id: str = Field(..., description="Run ID")
    trades: List[TradeListItem] = Field(..., description="List of trades")
    total: int = Field(..., description="Total number of trades")
    page: int = Field(..., description="Current page (0-indexed)")
    page_size: int = Field(..., description="Page size")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "my-run-001",
                "trades": [
                    {
                        "position_id": "pos_001",
                        "symbol": "BTC-USD",
                        "direction": "long",
                        "playbook": "breakout",
                        "entry_timestamp": "2024-01-15T10:30:00Z",
                        "entry_price": 42000.0,
                        "exit_timestamp": "2024-01-16T14:15:00Z",
                        "exit_price": 43500.0,
                        "exit_reason": "take_profit",
                        "size_usd": 1000.0,
                        "size_units": 0.0238,
                        "pnl_usd": 85.0,
                        "pnl_pct": 8.5,
                        "r_multiple": 2.1,
                        "bars_held": 24,
                    }
                ],
                "total": 24,
                "page": 0,
                "page_size": 20,
            }
        }
    )


class TradeDetailResponse(BaseModel):
    """Response model for detailed trade information."""

    # Use PositionRowV1 from Darwin directly for full detail
    position: Dict[str, Any] = Field(..., description="Full position data")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "position": {
                    "position_id": "pos_001",
                    "symbol": "BTC-USD",
                    "direction": "long",
                    "entry_price": 42000.0,
                    "exit_price": 43500.0,
                    "pnl_usd": 85.0,
                    "# ... full position data": "...",
                }
            }
        }
    )


class CandidateStats(BaseModel):
    """Statistics about candidates."""

    total_candidates: int = Field(..., description="Total candidates generated")
    taken: int = Field(..., description="Candidates taken as trades")
    skipped: int = Field(..., description="Candidates skipped")
    take_rate: float = Field(..., description="Take rate as decimal")
    take_rate_pct: float = Field(..., description="Take rate as percentage")

    # Breakdown by playbook
    by_playbook: Dict[str, Dict[str, int]] = Field(
        ..., description="Candidate counts by playbook"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_candidates": 48,
                "taken": 24,
                "skipped": 24,
                "take_rate": 0.5,
                "take_rate_pct": 50.0,
                "by_playbook": {
                    "breakout": {"total": 28, "taken": 16, "skipped": 12},
                    "pullback": {"total": 20, "taken": 8, "skipped": 12},
                },
            }
        }
    )


class FullReportResponse(BaseModel):
    """Response model for complete run report."""

    run_id: str = Field(..., description="Run ID")
    generated_at: datetime = Field(..., description="Report generation timestamp")

    # Summary metrics
    metrics: MetricsSummaryResponse = Field(..., description="Performance metrics")

    # Candidate statistics
    candidate_stats: CandidateStats = Field(..., description="Candidate statistics")

    # Configuration summary
    config_summary: Dict[str, Any] = Field(..., description="Run configuration summary")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "my-run-001",
                "generated_at": "2024-01-20T10:00:00Z",
                "metrics": {"total_return": 0.125, "...": "..."},
                "candidate_stats": {"total_candidates": 48, "...": "..."},
                "config_summary": {"symbols": ["BTC-USD"], "...": "..."},
            }
        }
    )
