"""Agent state and decision tracking schemas."""

from datetime import datetime
from typing import Any, Dict, Literal

from pydantic import BaseModel


class AgentDecisionV1(BaseModel):
    """Record of a single agent decision."""

    agent_name: str  # "gate", "portfolio", "meta_learner"
    candidate_id: str
    run_id: str
    timestamp: datetime

    # State and action
    state_hash: str  # Hash of the state vector for deduplication
    action: float  # int for discrete actions, float for continuous

    # Mode and version
    mode: Literal["observe", "active"]
    model_version: str

    # Outcome (filled later)
    outcome_r_multiple: float | None = None
    outcome_pnl_usd: float | None = None


class GraduationRecordV1(BaseModel):
    """Record of graduation evaluation."""

    agent_name: str
    evaluation_date: datetime
    passed: bool
    reason: str

    # Metrics at evaluation
    metrics: Dict[str, float]
    baseline_comparison: Dict[str, float] | None = None

    # Graduation decision
    promoted: bool = False  # observe → active
    demoted: bool = False  # active → observe


class AgentPerformanceSnapshotV1(BaseModel):
    """Periodic snapshot of agent performance."""

    agent_name: str
    snapshot_date: datetime
    window_size: int  # Number of decisions in this snapshot

    # Performance metrics
    mean_r_multiple: float
    win_rate: float
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None

    # Agent-specific metrics
    pass_rate: float | None = None  # Gate agent
    override_rate: float | None = None  # Meta-learner agent
    agreement_rate: float | None = None  # Meta-learner agent

    # Cost savings (gate agent)
    cost_savings_pct: float | None = None
    llm_calls_avoided: int | None = None
