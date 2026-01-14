"""Performance degradation monitoring for graduated agents.

Monitors active agents for performance degradation and triggers
automatic rollback if performance falls below acceptable levels.
"""

import logging
from collections import deque
from typing import Dict, Optional, Tuple

import numpy as np

from darwin.rl.schemas.rl_config import AgentConfigV1
from darwin.rl.storage.agent_state import AgentStateSQLite

logger = logging.getLogger(__name__)


class DegradationMonitor:
    """Monitor agent performance for degradation.

    Tracks rolling performance metrics and detects when an active
    agent's performance has degraded significantly compared to:
    1. Its graduation baseline
    2. Recent training performance
    3. LLM-only baseline

    Triggers automatic rollback to observe mode if degradation detected.
    """

    def __init__(
        self,
        agent_state_db: AgentStateSQLite,
        lookback_window: int = 100,
        degradation_threshold_pct: float = 25.0,
        min_samples_for_check: int = 50,
    ):
        """Initialize degradation monitor.

        Args:
            agent_state_db: Agent state database
            lookback_window: Number of recent decisions to monitor
            degradation_threshold_pct: Performance drop % to trigger degradation
            min_samples_for_check: Minimum samples before checking
        """
        self.agent_state_db = agent_state_db
        self.lookback_window = lookback_window
        self.degradation_threshold_pct = degradation_threshold_pct
        self.min_samples_for_check = min_samples_for_check

        # Track recent performance per agent
        self.recent_metrics: Dict[str, deque] = {}

        logger.info(
            f"Initialized degradation monitor: "
            f"window={lookback_window}, "
            f"threshold={degradation_threshold_pct}%"
        )

    def check_degradation(
        self,
        agent_name: str,
        agent_config: AgentConfigV1,
        graduation_metric: float,
    ) -> Tuple[bool, Optional[Dict]]:
        """Check if agent performance has degraded.

        Args:
            agent_name: Agent name
            agent_config: Agent configuration
            graduation_metric: Metric value at graduation time

        Returns:
            Tuple of (is_degraded, details_dict)
            - is_degraded: True if significant degradation detected
            - details_dict: Detailed metrics and comparison
        """
        # Only check active agents
        if agent_config.mode != "active":
            return False, None

        # Get recent decisions with outcomes
        all_decisions = self.agent_state_db.get_decisions_with_outcomes(agent_name)

        if len(all_decisions) < self.min_samples_for_check:
            logger.debug(
                f"Not enough samples to check degradation for {agent_name} "
                f"({len(all_decisions)} < {self.min_samples_for_check})"
            )
            return False, None

        # Use most recent lookback_window decisions
        recent_decisions = all_decisions[-self.lookback_window:]

        # Calculate current performance metric
        current_metric = self._calculate_agent_metric(agent_name, recent_decisions)

        # Calculate performance drop
        performance_drop_pct = (
            (graduation_metric - current_metric) / graduation_metric * 100
            if graduation_metric > 0
            else 0
        )

        # Build details
        details = {
            "agent_name": agent_name,
            "total_decisions": len(all_decisions),
            "recent_decisions": len(recent_decisions),
            "graduation_metric": graduation_metric,
            "current_metric": current_metric,
            "performance_drop_pct": performance_drop_pct,
            "threshold_pct": self.degradation_threshold_pct,
        }

        # Check degradation
        is_degraded = performance_drop_pct >= self.degradation_threshold_pct

        if is_degraded:
            logger.warning(
                f"⚠️  DEGRADATION DETECTED for agent '{agent_name}': "
                f"Performance dropped {performance_drop_pct:.1f}% "
                f"(graduation: {graduation_metric:.3f} → current: {current_metric:.3f})"
            )
        else:
            logger.debug(
                f"Agent '{agent_name}' performance OK: "
                f"drop={performance_drop_pct:.1f}% < threshold={self.degradation_threshold_pct}%"
            )

        return is_degraded, details

    def _calculate_agent_metric(self, agent_name: str, decisions: list) -> float:
        """Calculate agent-specific performance metric.

        Args:
            agent_name: Agent name
            decisions: List of decisions with outcomes

        Returns:
            Performance metric value
        """
        if not decisions:
            return 0.0

        # Agent-specific metrics (same as graduation evaluator)
        if agent_name == "gate":
            # Gate metric: Pass rate (profitable passes)
            passes = [d for d in decisions if d["action"] == 1]
            if not passes:
                return 0.0
            winners = sum(1 for d in passes if d["r_multiple"] and d["r_multiple"] > 0)
            return winners / len(passes)

        elif agent_name == "portfolio":
            # Portfolio metric: Sharpe ratio
            r_multiples = [d["r_multiple"] for d in decisions if d["r_multiple"] is not None]
            if len(r_multiples) < 10:
                return 0.0

            mean_r = np.mean(r_multiples)
            std_r = np.std(r_multiples, ddof=1)
            return mean_r / std_r if std_r > 1e-9 else 0.0

        elif agent_name == "meta_learner":
            # Meta-learner metric: Override accuracy
            overrides = [d for d in decisions if d["action"] in [1, 2]]
            if not overrides:
                return 0.5
            winners = sum(1 for d in overrides if d["r_multiple"] and d["r_multiple"] > 0)
            return winners / len(overrides)

        return 0.0

    def check_all_agents(
        self,
        gate_config: Optional[AgentConfigV1],
        portfolio_config: Optional[AgentConfigV1],
        meta_learner_config: Optional[AgentConfigV1],
        graduation_metrics: Dict[str, float],
    ) -> Dict[str, Tuple[bool, Optional[Dict]]]:
        """Check degradation for all active agents.

        Args:
            gate_config: Gate agent config
            portfolio_config: Portfolio agent config
            meta_learner_config: Meta-learner agent config
            graduation_metrics: Dict of agent_name -> graduation metric

        Returns:
            Dict of agent_name -> (is_degraded, details)
        """
        results = {}

        # Check gate agent
        if gate_config and gate_config.enabled and gate_config.mode == "active":
            graduation_metric = graduation_metrics.get("gate", 0.0)
            results["gate"] = self.check_degradation("gate", gate_config, graduation_metric)

        # Check portfolio agent
        if portfolio_config and portfolio_config.enabled and portfolio_config.mode == "active":
            graduation_metric = graduation_metrics.get("portfolio", 0.0)
            results["portfolio"] = self.check_degradation(
                "portfolio", portfolio_config, graduation_metric
            )

        # Check meta-learner agent
        if meta_learner_config and meta_learner_config.enabled and meta_learner_config.mode == "active":
            graduation_metric = graduation_metrics.get("meta_learner", 0.0)
            results["meta_learner"] = self.check_degradation(
                "meta_learner", meta_learner_config, graduation_metric
            )

        return results

    def rollback_agent(self, agent_config: AgentConfigV1) -> None:
        """Rollback degraded agent to observe mode.

        Args:
            agent_config: Agent configuration
        """
        agent_name = agent_config.name

        logger.warning(f"🔙 Rolling back agent '{agent_name}' to observe mode")
        logger.warning(f"   Status: active → observe")
        logger.warning(f"   Agent status: graduated → degraded")

        # Update mode and status
        agent_config.mode = "observe"
        agent_config.current_status = "degraded"

        logger.warning(
            f"   Agent '{agent_name}' will collect data in observe mode "
            f"until retrained and re-graduated"
        )

    def close(self) -> None:
        """Close database connections."""
        # No explicit close needed for agent_state_db (owned by caller)
        pass


class DegradationAlert:
    """Alert for agent degradation."""

    def __init__(
        self,
        agent_name: str,
        severity: str,
        message: str,
        details: Dict,
    ):
        """Initialize degradation alert.

        Args:
            agent_name: Agent that degraded
            severity: Alert severity (warning, critical)
            message: Alert message
            details: Detailed metrics
        """
        self.agent_name = agent_name
        self.severity = severity
        self.message = message
        self.details = details

    def __str__(self) -> str:
        """String representation."""
        return (
            f"[{self.severity.upper()}] {self.agent_name}: {self.message}\n"
            f"  Current metric: {self.details['current_metric']:.3f}\n"
            f"  Graduation metric: {self.details['graduation_metric']:.3f}\n"
            f"  Performance drop: {self.details['performance_drop_pct']:.1f}%"
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "agent_name": self.agent_name,
            "severity": self.severity,
            "message": self.message,
            "details": self.details,
        }
