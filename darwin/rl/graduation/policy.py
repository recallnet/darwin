"""Graduation policy for agent promotion/demotion."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

from darwin.rl.graduation.baselines import get_baseline_strategy
from darwin.rl.graduation.metrics import AgentPerformanceMetrics
from darwin.rl.schemas.rl_config import GraduationThresholdsV1
from darwin.rl.storage.agent_state import AgentStateSQLite

logger = logging.getLogger(__name__)


class GraduationDecision:
    """Result of graduation evaluation."""

    def __init__(
        self,
        can_graduate: bool,
        reason: str,
        checks: Dict[str, bool],
        metrics: Dict[str, float],
    ):
        """Initialize graduation decision.

        Args:
            can_graduate: Whether agent can graduate
            reason: Human-readable reason
            checks: Individual check results
            metrics: Performance metrics
        """
        self.can_graduate = can_graduate
        self.reason = reason
        self.checks = checks
        self.metrics = metrics

    def __repr__(self) -> str:
        """String representation."""
        return f"GraduationDecision(can_graduate={self.can_graduate}, reason='{self.reason}')"


class GraduationPolicy:
    """Evaluates whether agents can graduate from observe to active mode."""

    def __init__(
        self,
        agent_state: AgentStateSQLite,
        thresholds: GraduationThresholdsV1,
    ):
        """Initialize graduation policy.

        Args:
            agent_state: Agent state storage
            thresholds: Graduation thresholds configuration
        """
        self.agent_state = agent_state
        self.thresholds = thresholds
        self.metrics_tracker = AgentPerformanceMetrics(agent_state)

    def evaluate_graduation(
        self, agent_name: str, episodes: Optional[List[Dict[str, Any]]] = None
    ) -> GraduationDecision:
        """Evaluate if agent can graduate to active mode.

        Args:
            agent_name: Name of agent to evaluate
            episodes: Optional episodes for baseline comparison (if not provided, uses stored data)

        Returns:
            Graduation decision with details
        """
        checks = {}
        metrics = {}

        # Check 1: Data requirements
        data_req = self.metrics_tracker.get_data_requirements(
            agent_name,
            self.thresholds.min_training_samples,
            self.thresholds.min_validation_samples,
        )
        checks["has_sufficient_data"] = (
            data_req["has_min_training_samples"]
            and data_req["has_min_validation_samples"]
        )
        metrics["total_samples"] = data_req["total_samples"]
        metrics["recent_samples"] = data_req["recent_samples"]

        if not checks["has_sufficient_data"]:
            return GraduationDecision(
                can_graduate=False,
                reason=(
                    f"Insufficient data: {data_req['total_samples']} total samples "
                    f"(need {self.thresholds.min_training_samples}), "
                    f"{data_req['recent_samples']} recent samples "
                    f"(need {self.thresholds.min_validation_samples})"
                ),
                checks=checks,
                metrics=metrics,
            )

        # Check 2: Performance metrics
        rolling_metrics = self.metrics_tracker.compute_rolling_metrics(
            agent_name, window_days=30
        )

        if rolling_metrics is None:
            checks["has_performance_metrics"] = False
            return GraduationDecision(
                can_graduate=False,
                reason="No performance metrics available (no outcomes recorded)",
                checks=checks,
                metrics=metrics,
            )

        checks["has_performance_metrics"] = True
        metrics.update(rolling_metrics)

        # Check 3: Meets minimum performance threshold
        validation_metric = rolling_metrics.get(
            self._get_validation_metric_name(agent_name), 0.0
        )
        checks["meets_min_performance"] = (
            validation_metric >= self.thresholds.min_validation_metric
        )
        metrics["validation_metric"] = validation_metric

        if not checks["meets_min_performance"]:
            return GraduationDecision(
                can_graduate=False,
                reason=(
                    f"Performance below threshold: {validation_metric:.3f} "
                    f"(need {self.thresholds.min_validation_metric:.3f})"
                ),
                checks=checks,
                metrics=metrics,
            )

        # Check 4: Compare to baseline
        if episodes:
            baseline_comparison = self._compare_to_baseline(
                agent_name, episodes, rolling_metrics
            )
            checks["beats_baseline"] = baseline_comparison["beats_baseline"]
            metrics["baseline_improvement_pct"] = baseline_comparison["improvement_pct"]

            if not checks["beats_baseline"]:
                return GraduationDecision(
                    can_graduate=False,
                    reason=(
                        f"Does not beat baseline: {baseline_comparison['improvement_pct']:.1f}% improvement "
                        f"(need {self.thresholds.min_improvement_pct:.1f}%)"
                    ),
                    checks=checks,
                    metrics=metrics,
                )
        else:
            # No episodes provided, skip baseline check
            checks["beats_baseline"] = True
            logger.warning(
                f"Skipping baseline comparison for {agent_name} (no episodes provided)"
            )

        # Check 5: Stability across time windows
        stability_check = self._check_stability(agent_name)
        checks["is_stable"] = stability_check["is_stable"]
        metrics["stability_variance"] = stability_check["variance"]

        if not checks["is_stable"]:
            return GraduationDecision(
                can_graduate=False,
                reason=(
                    f"Performance unstable: variance {stability_check['variance']:.3f} "
                    f"(threshold {stability_check['max_variance']:.3f})"
                ),
                checks=checks,
                metrics=metrics,
            )

        # All checks passed
        return GraduationDecision(
            can_graduate=True,
            reason="All graduation criteria met",
            checks=checks,
            metrics=metrics,
        )

    def _get_validation_metric_name(self, agent_name: str) -> str:
        """Get validation metric name for agent type.

        Args:
            agent_name: Agent name

        Returns:
            Metric name to use for validation
        """
        metric_map = {
            "gate": "mean_r_multiple",  # Gate agent optimizes for not missing winners
            "portfolio": "sharpe_ratio",  # Portfolio agent optimizes risk-adjusted returns
            "meta_learner": "sharpe_ratio",  # Meta-learner optimizes overall performance
        }
        return metric_map.get(agent_name, "sharpe_ratio")

    def _compare_to_baseline(
        self, agent_name: str, episodes: List[Dict[str, Any]], agent_metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """Compare agent performance to baseline.

        Args:
            agent_name: Agent name
            episodes: Episodes for comparison
            agent_metrics: Agent performance metrics

        Returns:
            Comparison results
        """
        # Get baseline strategy
        baseline_strategy = get_baseline_strategy(self.thresholds.baseline_type)

        # Compute baseline performance
        baseline_metrics = baseline_strategy.compute_baseline_performance(episodes)

        # Compare on validation metric
        validation_metric_name = self._get_validation_metric_name(agent_name)
        agent_value = agent_metrics.get(validation_metric_name, 0.0)
        baseline_value = baseline_metrics.get(validation_metric_name, 0.0)

        if baseline_value != 0:
            improvement_pct = ((agent_value - baseline_value) / abs(baseline_value)) * 100
        else:
            improvement_pct = 100.0 if agent_value > 0 else 0.0

        beats_baseline = improvement_pct >= self.thresholds.min_improvement_pct

        return {
            "beats_baseline": beats_baseline,
            "improvement_pct": improvement_pct,
            "agent_value": agent_value,
            "baseline_value": baseline_value,
            "baseline_type": self.thresholds.baseline_type,
        }

    def _check_stability(self, agent_name: str, lookback_days: int = 90) -> Dict[str, Any]:
        """Check performance stability across time windows.

        Args:
            agent_name: Agent name
            lookback_days: Days to look back

        Returns:
            Stability check results
        """
        # Get performance across 3 windows
        window_size = lookback_days // 3
        windows = []

        for i in range(3):
            start_date = datetime.now() - timedelta(days=lookback_days - i * window_size)
            end_date = start_date + timedelta(days=window_size)

            # Get decisions in window
            decisions = self.agent_state.get_decisions_with_outcomes(
                agent_name, since=start_date
            )

            if decisions:
                r_multiples = [
                    d["outcome_r_multiple"]
                    for d in decisions
                    if d["outcome_r_multiple"] is not None
                ]
                if r_multiples:
                    mean_r = float(np.mean(r_multiples))
                    windows.append(mean_r)

        if len(windows) < 2:
            # Not enough data to check stability
            return {"is_stable": True, "variance": 0.0, "max_variance": 1.0}

        # Compute variance across windows
        variance = float(np.var(windows))
        max_variance = 1.0  # Maximum acceptable variance

        is_stable = variance <= max_variance

        return {
            "is_stable": is_stable,
            "variance": variance,
            "max_variance": max_variance,
            "window_means": windows,
        }

    def should_demote(self, agent_name: str) -> bool:
        """Check if agent should be demoted from active to observe mode.

        Args:
            agent_name: Agent name

        Returns:
            True if agent should be demoted
        """
        # Get recent performance (last 30 days)
        recent_metrics = self.metrics_tracker.compute_rolling_metrics(
            agent_name, window_days=30
        )

        if recent_metrics is None:
            logger.warning(f"No recent metrics for {agent_name}, not demoting")
            return False

        # Check if performance has degraded significantly below threshold
        validation_metric = recent_metrics.get(
            self._get_validation_metric_name(agent_name), 0.0
        )

        # Demote if performance drops below 50% of graduation threshold
        demote_threshold = self.thresholds.min_validation_metric * 0.5

        if validation_metric < demote_threshold:
            logger.warning(
                f"Agent {agent_name} performance degraded: {validation_metric:.3f} "
                f"< {demote_threshold:.3f}, considering demotion"
            )
            return True

        return False
