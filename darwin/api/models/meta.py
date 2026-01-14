"""
Pydantic models for meta-analysis API.

Defines request and response schemas for:
- Multi-run comparisons
- Equity curve overlays
- Run rankings
- Statistical tests
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


class CompareRunsRequest(BaseModel):
    """Request model for comparing multiple runs."""

    run_ids: List[str] = Field(..., min_length=2, description="List of run IDs to compare (min 2)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_ids": ["run-001", "run-002", "run-003"],
            }
        }
    )


class RunMetricsComparison(BaseModel):
    """Metrics for a single run in comparison."""

    run_id: str = Field(..., description="Run ID")
    description: str = Field(..., description="Run description")

    # Configuration
    symbols: List[str] = Field(..., description="Trading symbols")
    playbooks: List[str] = Field(..., description="Playbook names")
    start_date: Optional[str] = Field(None, description="Start date")
    end_date: Optional[str] = Field(None, description="End date")

    # Performance metrics
    total_return: float = Field(..., description="Total return")
    total_return_pct: float = Field(..., description="Total return percentage")
    sharpe_ratio: float = Field(..., description="Sharpe ratio")
    sortino_ratio: float = Field(..., description="Sortino ratio")
    max_drawdown: float = Field(..., description="Maximum drawdown")
    max_drawdown_pct: float = Field(..., description="Maximum drawdown percentage")
    win_rate: float = Field(..., description="Win rate")
    win_rate_pct: float = Field(..., description="Win rate percentage")
    profit_factor: float = Field(..., description="Profit factor")
    total_trades: int = Field(..., description="Total trades")
    final_equity: float = Field(..., description="Final equity")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "run-001",
                "description": "Breakout strategy on BTC",
                "symbols": ["BTC-USD"],
                "playbooks": ["breakout"],
                "start_date": "2024-01-01",
                "end_date": "2024-03-01",
                "total_return": 0.125,
                "total_return_pct": 12.5,
                "sharpe_ratio": 1.25,
                "sortino_ratio": 1.45,
                "max_drawdown": 0.08,
                "max_drawdown_pct": 8.0,
                "win_rate": 0.667,
                "win_rate_pct": 66.7,
                "profit_factor": 1.8,
                "total_trades": 24,
                "final_equity": 11250.0,
            }
        }
    )


class MetricRanking(BaseModel):
    """Ranking information for a specific metric."""

    rank: int = Field(..., description="Rank (1 = best)")
    value: float = Field(..., description="Metric value")
    is_best: bool = Field(..., description="Whether this is the best value")
    is_worst: bool = Field(..., description="Whether this is the worst value")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "rank": 1,
                "value": 1.25,
                "is_best": True,
                "is_worst": False,
            }
        }
    )


class ComparisonResponse(BaseModel):
    """Response model for multi-run comparison."""

    runs: List[RunMetricsComparison] = Field(..., description="List of run metrics")
    best_by_metric: Dict[str, str] = Field(..., description="Best run ID for each metric")
    generated_at: datetime = Field(..., description="Comparison generation timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "runs": [
                    {
                        "run_id": "run-001",
                        "description": "Breakout strategy",
                        "total_return_pct": 12.5,
                        "sharpe_ratio": 1.25,
                        "...": "...",
                    }
                ],
                "best_by_metric": {
                    "total_return": "run-001",
                    "sharpe_ratio": "run-002",
                    "max_drawdown": "run-003",
                },
                "generated_at": "2024-01-20T10:00:00Z",
            }
        }
    )


class EquityOverlayPoint(BaseModel):
    """Single point for equity curve overlay."""

    timestamp: datetime = Field(..., description="Bar timestamp")
    equities: Dict[str, float] = Field(..., description="Equity for each run at this timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2024-01-15T10:30:00Z",
                "equities": {
                    "run-001": 10250.0,
                    "run-002": 10180.0,
                    "run-003": 10320.0,
                },
            }
        }
    )


class EquityOverlayResponse(BaseModel):
    """Response model for overlaid equity curves."""

    run_ids: List[str] = Field(..., description="List of run IDs")
    starting_equity: Dict[str, float] = Field(..., description="Starting equity for each run")
    final_equity: Dict[str, float] = Field(..., description="Final equity for each run")
    data_points: List[EquityOverlayPoint] = Field(..., description="Overlaid equity curve points")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_ids": ["run-001", "run-002", "run-003"],
                "starting_equity": {
                    "run-001": 10000.0,
                    "run-002": 10000.0,
                    "run-003": 10000.0,
                },
                "final_equity": {
                    "run-001": 11250.0,
                    "run-002": 11180.0,
                    "run-003": 11320.0,
                },
                "data_points": [
                    {
                        "timestamp": "2024-01-15T10:30:00Z",
                        "equities": {
                            "run-001": 10250.0,
                            "run-002": 10180.0,
                            "run-003": 10320.0,
                        },
                    }
                ],
            }
        }
    )


class RankingEntry(BaseModel):
    """Single entry in rankings."""

    rank: int = Field(..., description="Rank (1 = best)")
    run_id: str = Field(..., description="Run ID")
    description: str = Field(..., description="Run description")
    value: float = Field(..., description="Metric value")
    symbols: List[str] = Field(..., description="Trading symbols")
    playbooks: List[str] = Field(..., description="Playbook names")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "rank": 1,
                "run_id": "run-001",
                "description": "Breakout strategy on BTC",
                "value": 1.25,
                "symbols": ["BTC-USD"],
                "playbooks": ["breakout"],
            }
        }
    )


class RankingsResponse(BaseModel):
    """Response model for run rankings by metric."""

    metric: str = Field(..., description="Metric name")
    rankings: List[RankingEntry] = Field(..., description="Ranked list of runs")
    total_runs: int = Field(..., description="Total number of runs ranked")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metric": "sharpe_ratio",
                "rankings": [
                    {
                        "rank": 1,
                        "run_id": "run-002",
                        "description": "Pullback strategy",
                        "value": 1.45,
                        "symbols": ["BTC-USD"],
                        "playbooks": ["pullback"],
                    }
                ],
                "total_runs": 3,
            }
        }
    )


class StatisticalTest(BaseModel):
    """Statistical test result."""

    test_name: str = Field(..., description="Test name (e.g., 't-test')")
    run_a: str = Field(..., description="First run ID")
    run_b: str = Field(..., description="Second run ID")
    statistic: float = Field(..., description="Test statistic")
    p_value: float = Field(..., description="P-value")
    significant: bool = Field(..., description="Whether difference is statistically significant (p < 0.05)")
    interpretation: str = Field(..., description="Human-readable interpretation")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "test_name": "t-test",
                "run_a": "run-001",
                "run_b": "run-002",
                "statistic": 2.45,
                "p_value": 0.023,
                "significant": True,
                "interpretation": "Run run-001 significantly outperforms run-002 (p=0.023)",
            }
        }
    )


class StatisticalComparisonResponse(BaseModel):
    """Response model for statistical comparison."""

    metric: str = Field(..., description="Metric being compared")
    tests: List[StatisticalTest] = Field(..., description="List of statistical tests")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metric": "returns",
                "tests": [
                    {
                        "test_name": "t-test",
                        "run_a": "run-001",
                        "run_b": "run-002",
                        "statistic": 2.45,
                        "p_value": 0.023,
                        "significant": True,
                        "interpretation": "Run run-001 significantly outperforms run-002",
                    }
                ],
            }
        }
    )
