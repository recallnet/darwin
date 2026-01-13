"""Hyperparameters for RL training.

This module contains default and tuned hyperparameters for:
- PPO training (learning rate, clip range, entropy coefficient, etc.)
- Reward shaping (coefficients for different reward components)
- Graduation thresholds (data requirements, performance thresholds)
"""

from typing import Any, Dict

# ==============================================================================
# PPO Hyperparameters
# ==============================================================================

# Default PPO hyperparameters for all agents
DEFAULT_PPO_PARAMS: Dict[str, Any] = {
    "learning_rate": 3e-4,
    "n_steps": 2048,
    "batch_size": 64,
    "n_epochs": 10,
    "gamma": 0.99,
    "gae_lambda": 0.95,
    "clip_range": 0.2,
    "clip_range_vf": None,
    "normalize_advantage": True,
    "ent_coef": 0.0,
    "vf_coef": 0.5,
    "max_grad_norm": 0.5,
    "target_kl": None,
    "verbose": 1,
}

# Gate Agent PPO hyperparameters (tuned for binary classification)
GATE_AGENT_PPO_PARAMS: Dict[str, Any] = {
    **DEFAULT_PPO_PARAMS,
    "learning_rate": 1e-4,  # Lower LR for stability
    "ent_coef": 0.01,  # Small entropy for exploration
    "clip_range": 0.15,  # Tighter clip for conservative policy
}

# Portfolio Agent PPO hyperparameters (tuned for continuous control)
PORTFOLIO_AGENT_PPO_PARAMS: Dict[str, Any] = {
    **DEFAULT_PPO_PARAMS,
    "learning_rate": 3e-4,
    "ent_coef": 0.05,  # Higher entropy for exploration of position sizes
    "clip_range": 0.2,
    "n_steps": 1024,  # Smaller steps for faster updates
}

# Meta-Learner Agent PPO hyperparameters (tuned for override decisions)
META_LEARNER_AGENT_PPO_PARAMS: Dict[str, Any] = {
    **DEFAULT_PPO_PARAMS,
    "learning_rate": 5e-5,  # Very low LR for conservative overrides
    "ent_coef": 0.001,  # Very low entropy to agree with LLM most of the time
    "clip_range": 0.1,  # Very tight clip for minimal policy change
    "n_epochs": 15,  # More epochs for careful training
}


# ==============================================================================
# Reward Shaping Coefficients
# ==============================================================================

# Gate Agent reward shaping
GATE_AGENT_REWARD_PARAMS: Dict[str, float] = {
    "skip_loser_bonus": 1.0,  # Reward for correctly skipping a losing trade
    "skip_winner_penalty": -1.5,  # Penalty for missing a winning trade (higher cost)
    "pass_cost": -0.1,  # Cost of calling LLM (small negative)
    "r_multiple_scale": 1.0,  # Scale factor for R-multiple in reward
}

# Portfolio Agent reward shaping
PORTFOLIO_AGENT_REWARD_PARAMS: Dict[str, float] = {
    "r_multiple_scale": 1.0,  # Base R-multiple reward
    "drawdown_penalty_coef": 0.5,  # Penalty coefficient for drawdown
    "diversification_bonus_coef": 0.2,  # Bonus for diversification
    "max_drawdown_threshold": 0.2,  # 20% drawdown threshold for penalty
}

# Meta-Learner Agent reward shaping
META_LEARNER_AGENT_REWARD_PARAMS: Dict[str, float] = {
    "r_multiple_scale": 1.0,  # Base R-multiple reward
    "agreement_bonus": 0.1,  # Small bonus for agreeing with LLM
    "override_penalty": -0.3,  # Penalty for disagreeing with LLM
    "correct_override_bonus": 1.5,  # Large bonus for correct override
}


# ==============================================================================
# Graduation Thresholds
# ==============================================================================

# Gate Agent graduation thresholds
GATE_AGENT_GRADUATION_THRESHOLDS: Dict[str, Any] = {
    "min_training_samples": 1000,
    "min_validation_samples": 200,
    "min_validation_metric": 0.1,  # Min mean R-multiple
    "baseline_type": "pass_all",
    "min_improvement_pct": 20.0,  # Must save 20%+ API costs
    "min_stability_windows": 3,  # Must be stable across 3 time windows
}

# Portfolio Agent graduation thresholds
PORTFOLIO_AGENT_GRADUATION_THRESHOLDS: Dict[str, Any] = {
    "min_training_samples": 500,
    "min_validation_samples": 100,
    "min_validation_metric": 1.5,  # Min Sharpe ratio
    "baseline_type": "equal_weight",
    "min_improvement_pct": 10.0,  # Must beat baseline by 10%+
    "max_drawdown_pct": 20.0,  # Max 20% drawdown allowed
    "min_stability_windows": 3,
}

# Meta-Learner Agent graduation thresholds
META_LEARNER_AGENT_GRADUATION_THRESHOLDS: Dict[str, Any] = {
    "min_training_samples": 2000,
    "min_validation_samples": 400,
    "min_validation_metric": 1.0,  # Min Sharpe ratio (improvement over LLM)
    "baseline_type": "llm_only",
    "min_improvement_pct": 10.0,  # Must improve Sharpe by 10%+
    "min_agreement_rate": 0.80,  # Must agree with LLM 80%+ of time
    "max_agreement_rate": 0.95,  # Must override some decisions (not 100% agreement)
    "min_override_accuracy": 0.60,  # Overrides must be 60%+ correct
    "min_stability_windows": 3,
}


# ==============================================================================
# Safety Thresholds
# ==============================================================================

SAFETY_PARAMS: Dict[str, Any] = {
    "enable_circuit_breakers": True,
    "circuit_breaker_threshold": 5,  # Open circuit after 5 failures
    "circuit_breaker_timeout": 300,  # 5 minutes timeout
    "max_override_rate": 0.20,  # Max 20% override rate for meta-learner
    "override_rate_window_minutes": 60,  # Check override rate over 60 min
    "enable_fallback_on_degradation": True,
    "fallback_window_days": 7,  # Check performance over 7 days
    "fallback_threshold": -0.5,  # Fallback if mean R < -0.5
}


# ==============================================================================
# Training Configuration
# ==============================================================================

TRAINING_PARAMS: Dict[str, Any] = {
    "total_timesteps": 100_000,  # Default training timesteps
    "eval_freq": 10_000,  # Evaluate every 10k steps
    "n_eval_episodes": 100,  # Number of episodes for evaluation
    "save_freq": 10_000,  # Save model every 10k steps
    "log_interval": 10,  # Log every 10 updates
    "tensorboard_log": "./tensorboard_logs/",
    "seed": 42,  # Random seed for reproducibility
}


# ==============================================================================
# Helper Functions
# ==============================================================================


def get_ppo_params(agent_name: str) -> Dict[str, Any]:
    """Get PPO hyperparameters for an agent.

    Args:
        agent_name: Name of agent ("gate", "portfolio", "meta_learner")

    Returns:
        Dictionary of PPO hyperparameters

    Raises:
        ValueError: If agent name is unknown
    """
    if agent_name == "gate":
        return GATE_AGENT_PPO_PARAMS.copy()
    elif agent_name == "portfolio":
        return PORTFOLIO_AGENT_PPO_PARAMS.copy()
    elif agent_name == "meta_learner":
        return META_LEARNER_AGENT_PPO_PARAMS.copy()
    else:
        raise ValueError(f"Unknown agent name: {agent_name}")


def get_reward_params(agent_name: str) -> Dict[str, float]:
    """Get reward shaping parameters for an agent.

    Args:
        agent_name: Name of agent ("gate", "portfolio", "meta_learner")

    Returns:
        Dictionary of reward shaping parameters

    Raises:
        ValueError: If agent name is unknown
    """
    if agent_name == "gate":
        return GATE_AGENT_REWARD_PARAMS.copy()
    elif agent_name == "portfolio":
        return PORTFOLIO_AGENT_REWARD_PARAMS.copy()
    elif agent_name == "meta_learner":
        return META_LEARNER_AGENT_REWARD_PARAMS.copy()
    else:
        raise ValueError(f"Unknown agent name: {agent_name}")


def get_graduation_thresholds(agent_name: str) -> Dict[str, Any]:
    """Get graduation thresholds for an agent.

    Args:
        agent_name: Name of agent ("gate", "portfolio", "meta_learner")

    Returns:
        Dictionary of graduation thresholds

    Raises:
        ValueError: If agent name is unknown
    """
    if agent_name == "gate":
        return GATE_AGENT_GRADUATION_THRESHOLDS.copy()
    elif agent_name == "portfolio":
        return PORTFOLIO_AGENT_GRADUATION_THRESHOLDS.copy()
    elif agent_name == "meta_learner":
        return META_LEARNER_AGENT_GRADUATION_THRESHOLDS.copy()
    else:
        raise ValueError(f"Unknown agent name: {agent_name}")
