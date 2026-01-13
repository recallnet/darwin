"""Graduation metrics tracking for RL agents."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

from darwin.rl.schemas.agent_state import AgentDecisionV1
from darwin.rl.storage.agent_state import AgentStateSQLite

logger = logging.getLogger(__name__)


class AgentPerformanceMetrics:
    """Track agent performance metrics for graduation evaluation."""

    def __init__(self, agent_state: AgentStateSQLite):
        """Initialize performance metrics tracker.

        Args:
            agent_state: Agent state storage instance
        """
        self.agent_state = agent_state

    def get_data_requirements(
        self, agent_name: str, min_training_samples: int, min_validation_samples: int
    ) -> Dict[str, bool]:
        """Check if agent has sufficient training data.

        Args:
            agent_name: Name of agent
            min_training_samples: Minimum training samples required
            min_validation_samples: Minimum validation samples required

        Returns:
            Dictionary with data requirement checks
        """
        total_decisions = self.agent_state.get_decision_count(agent_name)
        recent_decisions = self.agent_state.get_decision_count(
            agent_name, since=datetime.now() - timedelta(days=30)
        )

        return {
            "has_min_training_samples": total_decisions >= min_training_samples,
            "has_min_validation_samples": recent_decisions >= min_validation_samples,
            "total_samples": total_decisions,
            "recent_samples": recent_decisions,
        }

    def compute_rolling_metrics(
        self,
        agent_name: str,
        window_days: int = 30,
        min_decisions: int = 10,
    ) -> Optional[Dict[str, float]]:
        """Compute rolling performance metrics.

        Args:
            agent_name: Name of agent
            window_days: Rolling window in days
            min_decisions: Minimum decisions required

        Returns:
            Dictionary of metrics or None if insufficient data
        """
        # Get recent decisions with outcomes
        since = datetime.now() - timedelta(days=window_days)
        decisions = self.agent_state.get_decisions_with_outcomes(agent_name, since=since)

        if len(decisions) < min_decisions:
            logger.info(
                f"Insufficient decisions for {agent_name}: {len(decisions)} < {min_decisions}"
            )
            return None

        # Extract R-multiples
        r_multiples = [
            d["outcome_r_multiple"]
            for d in decisions
            if d["outcome_r_multiple"] is not None
        ]

        if not r_multiples:
            return None

        # Compute metrics
        mean_r = np.mean(r_multiples)
        std_r = np.std(r_multiples) if len(r_multiples) > 1 else 0.0
        sharpe = mean_r / std_r if std_r > 0 else 0.0

        win_rate = np.mean([r > 0 for r in r_multiples])
        max_r = np.max(r_multiples)
        min_r = np.min(r_multiples)

        # Compute drawdown
        cumulative_r = np.cumsum(r_multiples)
        running_max = np.maximum.accumulate(cumulative_r)
        drawdown = running_max - cumulative_r
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0.0

        return {
            "mean_r_multiple": float(mean_r),
            "std_r_multiple": float(std_r),
            "sharpe_ratio": float(sharpe),
            "win_rate": float(win_rate),
            "max_r_multiple": float(max_r),
            "min_r_multiple": float(min_r),
            "max_drawdown": float(max_drawdown),
            "num_decisions": len(r_multiples),
            "window_days": window_days,
        }

    def compare_to_baseline(
        self,
        agent_name: str,
        baseline_metric_name: str,
        baseline_metric_value: float,
        agent_metric_value: float,
        min_improvement_pct: float = 10.0,
    ) -> Dict[str, bool]:
        """Compare agent performance to baseline.

        Args:
            agent_name: Name of agent
            baseline_metric_name: Name of baseline metric (e.g., "mean_r_multiple")
            baseline_metric_value: Baseline metric value
            agent_metric_value: Agent metric value
            min_improvement_pct: Minimum improvement percentage required

        Returns:
            Dictionary with comparison results
        """
        if baseline_metric_value == 0:
            # Avoid division by zero
            improvement_pct = (
                100.0 if agent_metric_value > 0 else 0.0
            )
        else:
            improvement_pct = (
                (agent_metric_value - baseline_metric_value) / abs(baseline_metric_value)
            ) * 100.0

        meets_threshold = improvement_pct >= min_improvement_pct

        logger.info(
            f"{agent_name} {baseline_metric_name}: "
            f"baseline={baseline_metric_value:.4f}, "
            f"agent={agent_metric_value:.4f}, "
            f"improvement={improvement_pct:.2f}%, "
            f"threshold={min_improvement_pct:.2f}%, "
            f"meets_threshold={meets_threshold}"
        )

        return {
            "baseline_value": baseline_metric_value,
            "agent_value": agent_metric_value,
            "improvement_pct": improvement_pct,
            "min_improvement_pct": min_improvement_pct,
            "meets_threshold": meets_threshold,
        }

    def evaluate_stability(
        self,
        agent_name: str,
        metric_name: str,
        num_windows: int = 3,
        window_days: int = 14,
        max_std_pct: float = 20.0,
    ) -> Dict[str, bool]:
        """Evaluate performance stability across multiple windows.

        Args:
            agent_name: Name of agent
            metric_name: Name of metric to evaluate (e.g., "mean_r_multiple")
            num_windows: Number of windows to evaluate
            window_days: Window size in days
            max_std_pct: Maximum acceptable standard deviation percentage

        Returns:
            Dictionary with stability evaluation
        """
        window_metrics = []

        for i in range(num_windows):
            # Get metrics for each window
            since = datetime.now() - timedelta(days=(i + 1) * window_days)
            until = datetime.now() - timedelta(days=i * window_days)

            decisions = self.agent_state.get_decisions_with_outcomes(
                agent_name, since=since, until=until
            )

            if decisions:
                r_multiples = [
                    d["outcome_r_multiple"]
                    for d in decisions
                    if d["outcome_r_multiple"] is not None
                ]
                if r_multiples:
                    if metric_name == "mean_r_multiple":
                        window_metrics.append(np.mean(r_multiples))
                    elif metric_name == "sharpe_ratio":
                        mean_r = np.mean(r_multiples)
                        std_r = np.std(r_multiples) if len(r_multiples) > 1 else 0.0
                        sharpe = mean_r / std_r if std_r > 0 else 0.0
                        window_metrics.append(sharpe)
                    elif metric_name == "win_rate":
                        window_metrics.append(np.mean([r > 0 for r in r_multiples]))

        if len(window_metrics) < num_windows:
            logger.info(
                f"Insufficient windows for {agent_name} stability check: "
                f"{len(window_metrics)} < {num_windows}"
            )
            return {
                "is_stable": False,
                "num_windows_evaluated": len(window_metrics),
                "reason": "insufficient_data",
            }

        # Compute stability
        mean_metric = np.mean(window_metrics)
        std_metric = np.std(window_metrics)
        std_pct = (std_metric / abs(mean_metric) * 100.0) if mean_metric != 0 else 100.0

        is_stable = std_pct <= max_std_pct

        logger.info(
            f"{agent_name} {metric_name} stability: "
            f"mean={mean_metric:.4f}, std={std_metric:.4f}, "
            f"std_pct={std_pct:.2f}%, max_std_pct={max_std_pct:.2f}%, "
            f"is_stable={is_stable}"
        )

        return {
            "is_stable": is_stable,
            "mean_metric": float(mean_metric),
            "std_metric": float(std_metric),
            "std_pct": float(std_pct),
            "max_std_pct": max_std_pct,
            "num_windows_evaluated": len(window_metrics),
            "window_metrics": [float(m) for m in window_metrics],
        }

    def get_gate_agent_metrics(
        self, agent_name: str, window_days: int = 30
    ) -> Optional[Dict[str, float]]:
        """Get gate agent specific metrics.

        Args:
            agent_name: Name of gate agent
            window_days: Rolling window in days

        Returns:
            Dictionary of gate agent metrics or None
        """
        metrics = self.compute_rolling_metrics(agent_name, window_days)
        if metrics is None:
            return None

        # Get decisions for gate-specific metrics
        since = datetime.now() - timedelta(days=window_days)
        decisions = self.agent_state.get_decisions_with_outcomes(agent_name, since=since)

        # Compute skip rate and cost savings
        skip_actions = [d for d in decisions if d["action"] == 0]  # 0 = SKIP
        skip_rate = len(skip_actions) / len(decisions) if decisions else 0.0

        # Estimate cost savings (skipped LLM calls)
        cost_per_call = 0.01  # $0.01 per LLM call
        estimated_cost_savings = len(skip_actions) * cost_per_call

        # Compute miss rate (skipped winners)
        missed_winners = [
            d
            for d in skip_actions
            if d["outcome_r_multiple"] is not None and d["outcome_r_multiple"] > 0
        ]
        miss_rate = len(missed_winners) / len(skip_actions) if skip_actions else 0.0

        metrics.update(
            {
                "skip_rate": float(skip_rate),
                "estimated_cost_savings_usd": float(estimated_cost_savings),
                "miss_rate": float(miss_rate),
            }
        )

        return metrics

    def get_portfolio_agent_metrics(
        self, agent_name: str, window_days: int = 30
    ) -> Optional[Dict[str, float]]:
        """Get portfolio agent specific metrics.

        Args:
            agent_name: Name of portfolio agent
            window_days: Rolling window in days

        Returns:
            Dictionary of portfolio agent metrics or None
        """
        metrics = self.compute_rolling_metrics(agent_name, window_days)
        if metrics is None:
            return None

        # Get decisions for portfolio-specific metrics
        since = datetime.now() - timedelta(days=window_days)
        decisions = self.agent_state.get_decisions_with_outcomes(agent_name, since=since)

        # Compute average position size
        avg_position_size = np.mean([d["action"] for d in decisions]) if decisions else 0.0

        # TODO: Add more portfolio-specific metrics (Kelly criterion, risk parity, etc.)

        metrics.update(
            {
                "avg_position_size": float(avg_position_size),
            }
        )

        return metrics

    def get_meta_learner_metrics(
        self, agent_name: str, window_days: int = 30
    ) -> Optional[Dict[str, float]]:
        """Get meta-learner agent specific metrics.

        Args:
            agent_name: Name of meta-learner agent
            window_days: Rolling window in days

        Returns:
            Dictionary of meta-learner agent metrics or None
        """
        metrics = self.compute_rolling_metrics(agent_name, window_days)
        if metrics is None:
            return None

        # Get decisions for meta-learner-specific metrics
        since = datetime.now() - timedelta(days=window_days)
        decisions = self.agent_state.get_decisions_with_outcomes(agent_name, since=since)

        # Compute agreement rate (action = 0 = AGREE)
        agree_actions = [d for d in decisions if d["action"] == 0]
        agreement_rate = len(agree_actions) / len(decisions) if decisions else 0.0

        # Compute override rate
        override_actions = [d for d in decisions if d["action"] != 0]
        override_rate = len(override_actions) / len(decisions) if decisions else 0.0

        # Compute override accuracy (when override, was it correct?)
        correct_overrides = [
            d
            for d in override_actions
            if d["outcome_r_multiple"] is not None and d["outcome_r_multiple"] > 0
        ]
        override_accuracy = (
            len(correct_overrides) / len(override_actions) if override_actions else 0.0
        )

        metrics.update(
            {
                "agreement_rate": float(agreement_rate),
                "override_rate": float(override_rate),
                "override_accuracy": float(override_accuracy),
            }
        )

        return metrics
