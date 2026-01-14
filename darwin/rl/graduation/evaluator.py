"""Graduation evaluation for RL agents.

Evaluates whether an agent has met all graduation thresholds and is
ready to transition from observe mode to active mode.
"""

import logging
from typing import Dict, Tuple

import numpy as np

from darwin.rl.schemas.rl_config import AgentConfigV1, GraduationThresholdsV1
from darwin.rl.storage.agent_state import AgentStateSQLite

logger = logging.getLogger(__name__)


class GraduationEvaluator:
    """Evaluate agent graduation readiness.

    Checks if agent has:
    1. Seen enough candidates (2000+)
    2. Collected enough training/validation samples
    3. Achieved performance thresholds
    4. Beat baseline by required margin
    5. Demonstrated stability across validation windows
    """

    def __init__(self, agent_state_db: AgentStateSQLite):
        """Initialize graduation evaluator.

        Args:
            agent_state_db: Agent state database
        """
        self.agent_state_db = agent_state_db
        logger.info("Initialized graduation evaluator")

    def evaluate_graduation(
        self,
        agent_config: AgentConfigV1,
        baseline_metric: float,
    ) -> Tuple[bool, Dict[str, any]]:
        """Evaluate if agent is ready to graduate.

        Args:
            agent_config: Agent configuration with graduation thresholds
            baseline_metric: Baseline performance metric to beat

        Returns:
            Tuple of (is_ready, details_dict)
            - is_ready: True if agent meets ALL graduation criteria
            - details_dict: Detailed breakdown of each check
        """
        agent_name = agent_config.name
        thresholds = agent_config.graduation_thresholds

        logger.info(f"Evaluating graduation for agent '{agent_name}'")

        details = {
            "agent_name": agent_name,
            "checks_passed": [],
            "checks_failed": [],
            "metrics": {},
        }

        # Check 1: Minimum candidates seen
        total_decisions = self.agent_state_db.get_decision_count(agent_name)
        details["metrics"]["total_candidates_seen"] = total_decisions

        if total_decisions >= thresholds.min_candidates_seen:
            details["checks_passed"].append(
                f"✓ Candidates seen: {total_decisions} >= {thresholds.min_candidates_seen}"
            )
        else:
            details["checks_failed"].append(
                f"✗ Candidates seen: {total_decisions} < {thresholds.min_candidates_seen} "
                f"(need {thresholds.min_candidates_seen - total_decisions} more)"
            )

        # Check 2: Minimum training samples
        training_samples = self._count_training_samples(agent_name)
        details["metrics"]["training_samples"] = training_samples

        if training_samples >= thresholds.min_training_samples:
            details["checks_passed"].append(
                f"✓ Training samples: {training_samples} >= {thresholds.min_training_samples}"
            )
        else:
            details["checks_failed"].append(
                f"✗ Training samples: {training_samples} < {thresholds.min_training_samples}"
            )

        # Check 3: Minimum validation samples
        validation_samples = self._count_validation_samples(agent_name)
        details["metrics"]["validation_samples"] = validation_samples

        if validation_samples >= thresholds.min_validation_samples:
            details["checks_passed"].append(
                f"✓ Validation samples: {validation_samples} >= {thresholds.min_validation_samples}"
            )
        else:
            details["checks_failed"].append(
                f"✗ Validation samples: {validation_samples} < {thresholds.min_validation_samples}"
            )

        # Check 4: Validation metric (agent-specific)
        validation_metric = self._calculate_validation_metric(agent_name, agent_config)
        details["metrics"]["validation_metric"] = validation_metric

        if validation_metric >= thresholds.min_validation_metric:
            details["checks_passed"].append(
                f"✓ Validation metric: {validation_metric:.3f} >= {thresholds.min_validation_metric:.3f}"
            )
        else:
            details["checks_failed"].append(
                f"✗ Validation metric: {validation_metric:.3f} < {thresholds.min_validation_metric:.3f}"
            )

        # Check 5: Win rate (if specified)
        if thresholds.min_win_rate is not None:
            win_rate = self._calculate_win_rate(agent_name)
            details["metrics"]["win_rate"] = win_rate

            if win_rate >= thresholds.min_win_rate:
                details["checks_passed"].append(
                    f"✓ Win rate: {win_rate:.1%} >= {thresholds.min_win_rate:.1%}"
                )
            else:
                details["checks_failed"].append(
                    f"✗ Win rate: {win_rate:.1%} < {thresholds.min_win_rate:.1%}"
                )

        # Check 6: Sharpe ratio (if specified)
        if thresholds.min_sharpe_ratio is not None:
            sharpe = self._calculate_sharpe(agent_name)
            details["metrics"]["sharpe_ratio"] = sharpe

            if sharpe >= thresholds.min_sharpe_ratio:
                details["checks_passed"].append(
                    f"✓ Sharpe ratio: {sharpe:.2f} >= {thresholds.min_sharpe_ratio:.2f}"
                )
            else:
                details["checks_failed"].append(
                    f"✗ Sharpe ratio: {sharpe:.2f} < {thresholds.min_sharpe_ratio:.2f}"
                )

        # Check 7: Baseline improvement
        improvement_pct = ((validation_metric - baseline_metric) / baseline_metric * 100)
        details["metrics"]["baseline_metric"] = baseline_metric
        details["metrics"]["improvement_pct"] = improvement_pct

        if improvement_pct >= thresholds.min_improvement_pct:
            details["checks_passed"].append(
                f"✓ Improvement: {improvement_pct:.1f}% >= {thresholds.min_improvement_pct:.1f}%"
            )
        else:
            details["checks_failed"].append(
                f"✗ Improvement: {improvement_pct:.1f}% < {thresholds.min_improvement_pct:.1f}%"
            )

        # Check 8: Stability (pass in multiple validation windows)
        stability_passed, window_results = self._check_stability(
            agent_name, agent_config, baseline_metric
        )
        details["metrics"]["validation_windows"] = window_results

        passing_windows = sum(1 for w in window_results if w["passed"])
        if stability_passed:
            details["checks_passed"].append(
                f"✓ Stability: {passing_windows}/{len(window_results)} windows passed "
                f">= {thresholds.min_passing_windows}/{thresholds.num_validation_windows}"
            )
        else:
            details["checks_failed"].append(
                f"✗ Stability: {passing_windows}/{len(window_results)} windows passed "
                f"< {thresholds.min_passing_windows}/{thresholds.num_validation_windows}"
            )

        # Final decision
        is_ready = len(details["checks_failed"]) == 0

        if is_ready:
            logger.info(f"✅ Agent '{agent_name}' is READY to graduate!")
            logger.info(f"   All {len(details['checks_passed'])} checks passed")
        else:
            logger.info(f"❌ Agent '{agent_name}' is NOT ready to graduate")
            logger.info(f"   {len(details['checks_failed'])} checks failed:")
            for failure in details["checks_failed"]:
                logger.info(f"      {failure}")

        return is_ready, details

    def _count_training_samples(self, agent_name: str) -> int:
        """Count training samples (decisions with outcomes).

        Args:
            agent_name: Agent name

        Returns:
            Count of training samples
        """
        # Training samples = all decisions with outcomes
        decisions = self.agent_state_db.get_decisions_with_outcomes(agent_name)
        return len(decisions)

    def _count_validation_samples(self, agent_name: str) -> int:
        """Count validation samples (held-out data).

        For simplicity, use last 20% of data as validation set.

        Args:
            agent_name: Agent name

        Returns:
            Count of validation samples
        """
        decisions = self.agent_state_db.get_decisions_with_outcomes(agent_name)
        validation_size = int(len(decisions) * 0.2)
        return validation_size

    def _calculate_validation_metric(
        self, agent_name: str, agent_config: AgentConfigV1
    ) -> float:
        """Calculate agent-specific validation metric.

        Args:
            agent_name: Agent name
            agent_config: Agent configuration

        Returns:
            Validation metric value
        """
        decisions = self.agent_state_db.get_decisions_with_outcomes(agent_name)

        if len(decisions) < 10:
            return 0.0

        # Use last 20% as validation set
        validation_start = int(len(decisions) * 0.8)
        validation_decisions = decisions[validation_start:]

        if len(validation_decisions) < 5:
            return 0.0

        # Agent-specific metrics
        if agent_name == "gate":
            # Gate metric: Cost savings (% of candidates skipped that lost money)
            # Simplified: just use pass rate for now
            return self._calculate_pass_rate(validation_decisions)

        elif agent_name == "portfolio":
            # Portfolio metric: Sharpe ratio improvement
            return self._calculate_sharpe_from_decisions(validation_decisions)

        elif agent_name == "meta_learner":
            # Meta-learner metric: Override accuracy (improved decisions)
            return self._calculate_override_accuracy(validation_decisions)

        return 0.0

    def _calculate_pass_rate(self, decisions: list) -> float:
        """Calculate pass rate for gate agent."""
        if not decisions:
            return 0.0

        # For gate agent: what fraction of passes were profitable?
        passes = [d for d in decisions if d["action"] == 1]  # action=1 means PASS

        if not passes:
            return 0.0

        winners = sum(1 for d in passes if d["r_multiple"] and d["r_multiple"] > 0)
        return winners / len(passes)

    def _calculate_sharpe_from_decisions(self, decisions: list) -> float:
        """Calculate Sharpe ratio from decisions."""
        if len(decisions) < 10:
            return 0.0

        r_multiples = [d["r_multiple"] for d in decisions if d["r_multiple"] is not None]

        if len(r_multiples) < 10:
            return 0.0

        mean_r = np.mean(r_multiples)
        std_r = np.std(r_multiples, ddof=1)

        if std_r < 1e-9:
            return 0.0

        return float(mean_r / std_r)

    def _calculate_override_accuracy(self, decisions: list) -> float:
        """Calculate override accuracy for meta-learner."""
        if not decisions:
            return 0.0

        # For meta-learner: were overrides profitable?
        overrides = [d for d in decisions if d["action"] in [1, 2]]  # Override actions

        if not overrides:
            return 0.5  # No overrides = neutral

        winners = sum(1 for d in overrides if d["r_multiple"] and d["r_multiple"] > 0)
        return winners / len(overrides)

    def _calculate_win_rate(self, agent_name: str) -> float:
        """Calculate overall win rate."""
        decisions = self.agent_state_db.get_decisions_with_outcomes(agent_name)

        if not decisions:
            return 0.0

        winners = sum(1 for d in decisions if d["r_multiple"] and d["r_multiple"] > 0)
        return winners / len(decisions)

    def _calculate_sharpe(self, agent_name: str) -> float:
        """Calculate overall Sharpe ratio."""
        decisions = self.agent_state_db.get_decisions_with_outcomes(agent_name)
        return self._calculate_sharpe_from_decisions(decisions)

    def _check_stability(
        self,
        agent_name: str,
        agent_config: AgentConfigV1,
        baseline_metric: float,
    ) -> Tuple[bool, list]:
        """Check performance stability across validation windows.

        Args:
            agent_name: Agent name
            agent_config: Agent configuration
            baseline_metric: Baseline metric to beat

        Returns:
            Tuple of (passed, window_results)
        """
        thresholds = agent_config.graduation_thresholds
        decisions = self.agent_state_db.get_decisions_with_outcomes(agent_name)

        if len(decisions) < thresholds.num_validation_windows * 10:
            # Not enough data for windowed validation
            return False, []

        # Split validation set into windows
        validation_start = int(len(decisions) * 0.8)
        validation_decisions = decisions[validation_start:]

        window_size = len(validation_decisions) // thresholds.num_validation_windows
        if window_size < 5:
            return False, []

        window_results = []

        for i in range(thresholds.num_validation_windows):
            window_start = i * window_size
            window_end = window_start + window_size
            window_decisions = validation_decisions[window_start:window_end]

            # Calculate metric for this window
            if agent_name == "gate":
                window_metric = self._calculate_pass_rate(window_decisions)
            elif agent_name == "portfolio":
                window_metric = self._calculate_sharpe_from_decisions(window_decisions)
            elif agent_name == "meta_learner":
                window_metric = self._calculate_override_accuracy(window_decisions)
            else:
                window_metric = 0.0

            # Check if this window beats baseline
            improvement = (
                (window_metric - baseline_metric) / baseline_metric * 100
                if baseline_metric > 0
                else 0
            )

            passed = (
                window_metric >= thresholds.min_validation_metric
                and improvement >= thresholds.min_improvement_pct
            )

            window_results.append({
                "window": i + 1,
                "metric": window_metric,
                "improvement_pct": improvement,
                "passed": passed,
            })

        # Check if enough windows passed
        passing_windows = sum(1 for w in window_results if w["passed"])
        stability_passed = passing_windows >= thresholds.min_passing_windows

        return stability_passed, window_results
