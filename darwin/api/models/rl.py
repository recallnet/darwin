"""
Pydantic models for RL monitoring API.

Provides endpoints for:
- Agent status and overview
- Performance metrics
- Graduation tracking
- Alert monitoring
- Model version management
"""

from datetime import datetime
from typing import Dict, List, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict


class AgentDecisionResponse(BaseModel):
    """Agent decision record."""

    agent_name: str = Field(..., description="Agent name")
    candidate_id: str = Field(..., description="Candidate ID")
    run_id: str = Field(..., description="Run ID")
    timestamp: datetime = Field(..., description="Decision timestamp")
    state_hash: str = Field(..., description="State hash")
    action: float = Field(..., description="Action taken")
    mode: Literal["observe", "active"] = Field(..., description="Agent mode")
    model_version: str = Field(..., description="Model version")
    outcome_r_multiple: Optional[float] = Field(None, description="Outcome R-multiple")
    outcome_pnl_usd: Optional[float] = Field(None, description="Outcome PnL in USD")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent_name": "gate",
                "candidate_id": "cand-123",
                "run_id": "run-001",
                "timestamp": "2024-01-15T10:30:00Z",
                "state_hash": "a1b2c3d4",
                "action": 0.0,
                "mode": "observe",
                "model_version": "v1.0.0",
                "outcome_r_multiple": 1.5,
                "outcome_pnl_usd": 150.0,
            }
        }
    )


class PerformanceMetricsResponse(BaseModel):
    """Agent performance metrics."""

    agent_name: str = Field(..., description="Agent name")
    window_days: int = Field(..., description="Window size in days")
    num_decisions: int = Field(..., description="Number of decisions")

    # Core performance metrics
    mean_r_multiple: float = Field(..., description="Mean R-multiple")
    std_r_multiple: float = Field(..., description="Std deviation of R-multiple")
    sharpe_ratio: float = Field(..., description="Sharpe ratio")
    win_rate: float = Field(..., description="Win rate")
    max_r_multiple: float = Field(..., description="Maximum R-multiple")
    min_r_multiple: float = Field(..., description="Minimum R-multiple")
    max_drawdown: float = Field(..., description="Maximum drawdown")

    # Agent-specific metrics (optional)
    skip_rate: Optional[float] = Field(None, description="Skip rate (gate agent)")
    estimated_cost_savings_usd: Optional[float] = Field(
        None, description="Estimated cost savings (gate agent)"
    )
    miss_rate: Optional[float] = Field(None, description="Miss rate (gate agent)")
    avg_position_size: Optional[float] = Field(
        None, description="Average position size (portfolio agent)"
    )
    agreement_rate: Optional[float] = Field(
        None, description="Agreement rate (meta-learner agent)"
    )
    override_rate: Optional[float] = Field(
        None, description="Override rate (meta-learner agent)"
    )
    override_accuracy: Optional[float] = Field(
        None, description="Override accuracy (meta-learner agent)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent_name": "gate",
                "window_days": 30,
                "num_decisions": 150,
                "mean_r_multiple": 0.85,
                "std_r_multiple": 1.2,
                "sharpe_ratio": 0.71,
                "win_rate": 0.55,
                "max_r_multiple": 5.2,
                "min_r_multiple": -2.1,
                "max_drawdown": 3.5,
                "skip_rate": 0.45,
                "estimated_cost_savings_usd": 67.5,
                "miss_rate": 0.12,
            }
        }
    )


class PerformanceSnapshotResponse(BaseModel):
    """Performance snapshot for time series."""

    snapshot_date: datetime = Field(..., description="Snapshot date")
    window_size: int = Field(..., description="Window size")
    mean_r_multiple: float = Field(..., description="Mean R-multiple")
    win_rate: float = Field(..., description="Win rate")
    sharpe_ratio: Optional[float] = Field(None, description="Sharpe ratio")
    max_drawdown: Optional[float] = Field(None, description="Max drawdown")
    pass_rate: Optional[float] = Field(None, description="Pass rate (gate agent)")
    override_rate: Optional[float] = Field(None, description="Override rate (meta-learner)")
    agreement_rate: Optional[float] = Field(None, description="Agreement rate (meta-learner)")
    cost_savings_pct: Optional[float] = Field(None, description="Cost savings percentage")
    llm_calls_avoided: Optional[int] = Field(None, description="LLM calls avoided")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "snapshot_date": "2024-01-15T00:00:00Z",
                "window_size": 30,
                "mean_r_multiple": 0.85,
                "win_rate": 0.55,
                "sharpe_ratio": 0.71,
                "max_drawdown": 3.5,
            }
        }
    )


class PerformanceHistoryResponse(BaseModel):
    """Performance history (time series)."""

    agent_name: str = Field(..., description="Agent name")
    snapshots: List[PerformanceSnapshotResponse] = Field(..., description="Performance snapshots")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent_name": "gate",
                "snapshots": [
                    {
                        "snapshot_date": "2024-01-15T00:00:00Z",
                        "window_size": 30,
                        "mean_r_multiple": 0.85,
                        "win_rate": 0.55,
                        "sharpe_ratio": 0.71,
                        "max_drawdown": 3.5,
                    }
                ],
            }
        }
    )


class GraduationStatusResponse(BaseModel):
    """Graduation status for an agent."""

    agent_name: str = Field(..., description="Agent name")
    current_mode: Literal["observe", "active"] = Field(..., description="Current mode")
    can_graduate: bool = Field(..., description="Whether agent can graduate")
    reason: str = Field(..., description="Reason for graduation decision")
    checks: Dict[str, bool] = Field(..., description="Individual check results")
    metrics: Dict[str, float] = Field(..., description="Performance metrics")

    # Data requirements
    total_samples: int = Field(..., description="Total training samples")
    recent_samples: int = Field(..., description="Recent validation samples")
    required_training_samples: int = Field(..., description="Required training samples")
    required_validation_samples: int = Field(..., description="Required validation samples")

    # Progress
    training_progress_pct: float = Field(..., description="Training progress percentage")
    validation_progress_pct: float = Field(..., description="Validation progress percentage")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent_name": "gate",
                "current_mode": "observe",
                "can_graduate": False,
                "reason": "Insufficient data: 450 total samples (need 1000)",
                "checks": {
                    "has_sufficient_data": False,
                    "has_performance_metrics": True,
                    "meets_min_performance": True,
                    "beats_baseline": True,
                    "is_stable": True,
                },
                "metrics": {
                    "total_samples": 450,
                    "recent_samples": 80,
                    "validation_metric": 0.85,
                },
                "total_samples": 450,
                "recent_samples": 80,
                "required_training_samples": 1000,
                "required_validation_samples": 100,
                "training_progress_pct": 45.0,
                "validation_progress_pct": 80.0,
            }
        }
    )


class GraduationHistoryResponse(BaseModel):
    """Graduation evaluation history."""

    agent_name: str = Field(..., description="Agent name")
    records: List["GraduationRecordResponse"] = Field(..., description="Graduation records")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent_name": "gate",
                "records": [
                    {
                        "evaluation_date": "2024-01-15T00:00:00Z",
                        "passed": True,
                        "reason": "All criteria met",
                        "metrics": {"mean_r_multiple": 0.85, "sharpe_ratio": 0.71},
                        "promoted": True,
                        "demoted": False,
                    }
                ],
            }
        }
    )


class GraduationRecordResponse(BaseModel):
    """Single graduation evaluation record."""

    evaluation_date: datetime = Field(..., description="Evaluation date")
    passed: bool = Field(..., description="Whether evaluation passed")
    reason: str = Field(..., description="Reason for decision")
    metrics: Dict[str, float] = Field(..., description="Metrics at evaluation")
    baseline_comparison: Optional[Dict[str, float]] = Field(
        None, description="Baseline comparison"
    )
    promoted: bool = Field(..., description="Whether agent was promoted")
    demoted: bool = Field(..., description="Whether agent was demoted")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "evaluation_date": "2024-01-15T00:00:00Z",
                "passed": True,
                "reason": "All graduation criteria met",
                "metrics": {"mean_r_multiple": 0.85, "sharpe_ratio": 0.71},
                "baseline_comparison": {"improvement_pct": 25.0},
                "promoted": True,
                "demoted": False,
            }
        }
    )


class AlertResponse(BaseModel):
    """Alert for agent monitoring."""

    alert_type: str = Field(..., description="Alert type")
    agent_name: str = Field(..., description="Agent name")
    severity: Literal["warning", "error", "critical"] = Field(..., description="Severity level")
    message: str = Field(..., description="Human-readable message")
    details: Dict[str, float | int | str] = Field(..., description="Additional details")
    timestamp: datetime = Field(..., description="Alert timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "alert_type": "performance_degradation",
                "agent_name": "gate",
                "severity": "warning",
                "message": "Performance degraded by 30%: 0.85 -> 0.60",
                "details": {
                    "baseline_mean_r": 0.85,
                    "recent_mean_r": 0.60,
                    "degradation_pct": 30.0,
                },
                "timestamp": "2024-01-15T10:30:00Z",
            }
        }
    )


class AlertsResponse(BaseModel):
    """List of alerts for an agent."""

    agent_name: str = Field(..., description="Agent name")
    alerts: List[AlertResponse] = Field(..., description="Active alerts")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent_name": "gate",
                "alerts": [
                    {
                        "alert_type": "performance_degradation",
                        "agent_name": "gate",
                        "severity": "warning",
                        "message": "Performance degraded by 30%",
                        "details": {"degradation_pct": 30.0},
                        "timestamp": "2024-01-15T10:30:00Z",
                    }
                ],
            }
        }
    )


class ModelVersionResponse(BaseModel):
    """Model version metadata."""

    version: str = Field(..., description="Version string")
    agent_name: str = Field(..., description="Agent name")
    saved_at: datetime = Field(..., description="Save timestamp")
    model_path: str = Field(..., description="Model file path")
    is_current: bool = Field(..., description="Whether this is the current version")

    # Optional training metadata
    training_steps: Optional[int] = Field(None, description="Training steps")
    training_episodes: Optional[int] = Field(None, description="Training episodes")
    final_mean_reward: Optional[float] = Field(None, description="Final mean reward")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version": "v1.0.0",
                "agent_name": "gate",
                "saved_at": "2024-01-15T00:00:00Z",
                "model_path": "/path/to/models/gate/v1.0.0_2024-01-15.zip",
                "is_current": True,
                "training_steps": 50000,
                "training_episodes": 1000,
                "final_mean_reward": 0.85,
            }
        }
    )


class ModelVersionsResponse(BaseModel):
    """List of model versions for an agent."""

    agent_name: str = Field(..., description="Agent name")
    current_version: Optional[str] = Field(None, description="Current version string")
    versions: List[ModelVersionResponse] = Field(..., description="All versions")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent_name": "gate",
                "current_version": "v1.1.0",
                "versions": [
                    {
                        "version": "v1.1.0",
                        "agent_name": "gate",
                        "saved_at": "2024-02-01T00:00:00Z",
                        "model_path": "/path/to/models/gate/v1.1.0_2024-02-01.zip",
                        "is_current": True,
                    },
                    {
                        "version": "v1.0.0",
                        "agent_name": "gate",
                        "saved_at": "2024-01-15T00:00:00Z",
                        "model_path": "/path/to/models/gate/v1.0.0_2024-01-15.zip",
                        "is_current": False,
                    },
                ],
            }
        }
    )


class RollbackModelRequest(BaseModel):
    """Request to rollback model to a specific version."""

    version: str = Field(..., description="Version to rollback to")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version": "v1.0.0",
            }
        }
    )


class AgentStatusSummary(BaseModel):
    """Summary status for a single agent."""

    agent_name: str = Field(..., description="Agent name")
    current_mode: Literal["observe", "active"] = Field(..., description="Current mode")
    model_version: Optional[str] = Field(None, description="Current model version")

    # Status indicators
    has_active_alerts: bool = Field(..., description="Whether agent has active alerts")
    alert_count: int = Field(..., description="Number of active alerts")
    can_graduate: bool = Field(..., description="Whether agent can graduate")

    # Recent performance
    recent_decisions: int = Field(..., description="Recent decisions (30 days)")
    recent_mean_r_multiple: Optional[float] = Field(None, description="Recent mean R-multiple")
    recent_win_rate: Optional[float] = Field(None, description="Recent win rate")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent_name": "gate",
                "current_mode": "observe",
                "model_version": "v1.0.0",
                "has_active_alerts": True,
                "alert_count": 1,
                "can_graduate": False,
                "recent_decisions": 150,
                "recent_mean_r_multiple": 0.85,
                "recent_win_rate": 0.55,
            }
        }
    )


class AgentsOverviewResponse(BaseModel):
    """Overview of all agents."""

    agents: List[AgentStatusSummary] = Field(..., description="Agent status summaries")
    generated_at: datetime = Field(..., description="Generation timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agents": [
                    {
                        "agent_name": "gate",
                        "current_mode": "observe",
                        "model_version": "v1.0.0",
                        "has_active_alerts": False,
                        "alert_count": 0,
                        "can_graduate": True,
                        "recent_decisions": 150,
                        "recent_mean_r_multiple": 0.85,
                        "recent_win_rate": 0.55,
                    },
                    {
                        "agent_name": "portfolio",
                        "current_mode": "active",
                        "model_version": "v2.1.0",
                        "has_active_alerts": False,
                        "alert_count": 0,
                        "can_graduate": True,
                        "recent_decisions": 200,
                        "recent_mean_r_multiple": 1.2,
                        "recent_win_rate": 0.62,
                    },
                    {
                        "agent_name": "meta_learner",
                        "current_mode": "active",
                        "model_version": "v1.5.0",
                        "has_active_alerts": False,
                        "alert_count": 0,
                        "can_graduate": True,
                        "recent_decisions": 180,
                        "recent_mean_r_multiple": 1.1,
                        "recent_win_rate": 0.58,
                    },
                ],
                "generated_at": "2024-01-15T10:30:00Z",
            }
        }
    )


class AgentDetailResponse(BaseModel):
    """Detailed information for a specific agent."""

    agent_name: str = Field(..., description="Agent name")
    current_mode: Literal["observe", "active"] = Field(..., description="Current mode")
    model_version: Optional[str] = Field(None, description="Current model version")

    # Graduation status
    graduation_status: GraduationStatusResponse = Field(..., description="Graduation status")

    # Performance metrics
    performance_metrics: PerformanceMetricsResponse = Field(..., description="Performance metrics")

    # Alerts
    active_alerts: List[AlertResponse] = Field(..., description="Active alerts")

    # Recent decisions
    recent_decisions_count: int = Field(..., description="Recent decisions count (7 days)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent_name": "gate",
                "current_mode": "observe",
                "model_version": "v1.0.0",
                "graduation_status": {
                    "agent_name": "gate",
                    "current_mode": "observe",
                    "can_graduate": False,
                    "reason": "Insufficient data",
                    "checks": {},
                    "metrics": {},
                    "total_samples": 450,
                    "recent_samples": 80,
                    "required_training_samples": 1000,
                    "required_validation_samples": 100,
                    "training_progress_pct": 45.0,
                    "validation_progress_pct": 80.0,
                },
                "performance_metrics": {
                    "agent_name": "gate",
                    "window_days": 30,
                    "num_decisions": 150,
                    "mean_r_multiple": 0.85,
                    "std_r_multiple": 1.2,
                    "sharpe_ratio": 0.71,
                    "win_rate": 0.55,
                    "max_r_multiple": 5.2,
                    "min_r_multiple": -2.1,
                    "max_drawdown": 3.5,
                },
                "active_alerts": [],
                "recent_decisions_count": 50,
            }
        }
    )
