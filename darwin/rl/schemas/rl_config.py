"""RL configuration schemas."""

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class GraduationThresholdsV1(BaseModel):
    """Thresholds for agent graduation from observe → active mode.

    An agent must meet ALL thresholds to graduate.
    """

    # Data requirements
    min_training_samples: int
    min_validation_samples: int
    min_candidates_seen: int = 2000  # Minimum total candidates agent must see

    # Performance requirements (all must pass)
    min_validation_metric: float  # Agent-specific metric (e.g., pass rate, Sharpe)
    min_win_rate: float | None = None
    min_sharpe_ratio: float | None = None
    max_drawdown_pct: float | None = None

    # Baseline comparison (must beat baseline)
    baseline_type: str  # "llm_only", "equal_weight", "pass_all"
    min_improvement_pct: float  # e.g., 10% improvement required

    # Stability requirements (consistency check)
    num_validation_windows: int = 5
    min_passing_windows: int = 4  # 4/5 windows must pass


class AgentConfigV1(BaseModel):
    """Configuration for a single RL agent."""

    name: str  # "gate", "portfolio", "meta_learner"
    enabled: bool = False
    mode: Literal["observe", "active"] = "observe"

    # Model paths
    model_path: Optional[str] = None
    model_version: Optional[str] = None

    # Training config
    training_config: Optional[Dict[str, Any]] = None

    # Graduation config
    graduation_thresholds: GraduationThresholdsV1
    current_status: Literal["training", "graduated", "degraded"] = "training"

    # Tracking
    last_evaluation_date: Optional[datetime] = None
    total_decisions: int = 0
    decisions_in_current_epoch: int = 0


class RLConfigV1(BaseModel):
    """Top-level RL configuration."""

    enabled: bool = False

    # Agent configurations (all optional)
    gate_agent: Optional[AgentConfigV1] = None
    portfolio_agent: Optional[AgentConfigV1] = None
    meta_learner_agent: Optional[AgentConfigV1] = None

    # Training settings
    training_frequency: str = "weekly"  # "daily", "weekly", "monthly"
    min_new_samples_for_retrain: int = 100

    # Storage paths
    models_dir: str = "artifacts/rl_models"
    agent_state_db: str = "artifacts/rl_state/agent_state.sqlite"
    training_logs_db: str = "artifacts/rl_state/training_logs.sqlite"

    # Safety settings
    max_override_rate: float = 0.2
    fallback_to_baseline_on_degradation: bool = True


# Rebuild RunConfigV1 to resolve forward reference
try:
    from darwin.schemas.run_config import RunConfigV1
    RunConfigV1.model_rebuild()
except (ImportError, AttributeError):
    # RunConfigV1 not yet loaded or doesn't need rebuild
    pass
