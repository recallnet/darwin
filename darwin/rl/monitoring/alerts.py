"""Monitoring and alerting for RL agents."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

from darwin.rl.storage.agent_state import AgentStateSQLite

logger = logging.getLogger(__name__)


class AlertType:
    """Alert type constants."""

    PERFORMANCE_DEGRADATION = "performance_degradation"
    EXCESSIVE_OVERRIDES = "excessive_overrides"
    LOW_DECISION_RATE = "low_decision_rate"
    HIGH_ERROR_RATE = "high_error_rate"
    TRAINING_DATA_INSUFFICIENT = "training_data_insufficient"


class Alert:
    """Alert object."""

    def __init__(
        self,
        alert_type: str,
        agent_name: str,
        severity: str,  # "warning", "error", "critical"
        message: str,
        details: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ):
        """Initialize alert.

        Args:
            alert_type: Type of alert
            agent_name: Name of agent
            severity: Alert severity level
            message: Human-readable message
            details: Additional details
            timestamp: Alert timestamp (defaults to now)
        """
        self.alert_type = alert_type
        self.agent_name = agent_name
        self.severity = severity
        self.message = message
        self.details = details
        self.timestamp = timestamp or datetime.now()

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"Alert(type={self.alert_type}, agent={self.agent_name}, "
            f"severity={self.severity}, message='{self.message}')"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "alert_type": self.alert_type,
            "agent_name": self.agent_name,
            "severity": self.severity,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class AgentMonitor:
    """Monitor RL agent health and performance."""

    def __init__(self, agent_state: AgentStateSQLite):
        """Initialize monitor.

        Args:
            agent_state: Agent state storage
        """
        self.agent_state = agent_state

    def check_performance_degradation(
        self,
        agent_name: str,
        baseline_window_days: int = 90,
        recent_window_days: int = 30,
        degradation_threshold: float = 0.3,
    ) -> Optional[Alert]:
        """Check if agent performance has degraded.

        Args:
            agent_name: Name of agent
            baseline_window_days: Days for baseline comparison
            recent_window_days: Days for recent performance
            degradation_threshold: Threshold for degradation (0.3 = 30% drop)

        Returns:
            Alert if performance degraded, None otherwise
        """
        # Get baseline performance (older window)
        baseline_start = datetime.now() - timedelta(days=baseline_window_days)
        baseline_end = datetime.now() - timedelta(days=recent_window_days)
        baseline_decisions = self.agent_state.get_decisions_with_outcomes(
            agent_name, since=baseline_start
        )
        baseline_decisions = [
            d for d in baseline_decisions
            if datetime.fromisoformat(d["timestamp"]) <= baseline_end
        ]

        # Get recent performance
        recent_start = datetime.now() - timedelta(days=recent_window_days)
        recent_decisions = self.agent_state.get_decisions_with_outcomes(
            agent_name, since=recent_start
        )

        if not baseline_decisions or not recent_decisions:
            return None  # Not enough data

        # Calculate mean R-multiple for both windows
        baseline_r = [
            d["outcome_r_multiple"]
            for d in baseline_decisions
            if d["outcome_r_multiple"] is not None
        ]
        recent_r = [
            d["outcome_r_multiple"]
            for d in recent_decisions
            if d["outcome_r_multiple"] is not None
        ]

        if not baseline_r or not recent_r:
            return None

        baseline_mean = float(np.mean(baseline_r))
        recent_mean = float(np.mean(recent_r))

        # Check for degradation
        if baseline_mean > 0:  # Only check if baseline was positive
            degradation = (baseline_mean - recent_mean) / baseline_mean
            if degradation >= degradation_threshold:
                return Alert(
                    alert_type=AlertType.PERFORMANCE_DEGRADATION,
                    agent_name=agent_name,
                    severity="warning",
                    message=(
                        f"Performance degraded by {degradation*100:.1f}%: "
                        f"{baseline_mean:.3f} -> {recent_mean:.3f}"
                    ),
                    details={
                        "baseline_mean_r": baseline_mean,
                        "recent_mean_r": recent_mean,
                        "degradation_pct": degradation * 100,
                        "baseline_sample_count": len(baseline_r),
                        "recent_sample_count": len(recent_r),
                    },
                )

        return None

    def check_excessive_overrides(
        self,
        agent_name: str,
        window_days: int = 7,
        max_override_rate: float = 0.3,
    ) -> Optional[Alert]:
        """Check if meta-learner has excessive override rate.

        Args:
            agent_name: Name of agent (should be "meta_learner")
            window_days: Days to check
            max_override_rate: Maximum acceptable override rate

        Returns:
            Alert if override rate too high, None otherwise
        """
        if agent_name != "meta_learner":
            return None  # Only applies to meta-learner

        since = datetime.now() - timedelta(days=window_days)
        decisions = self.agent_state.get_decisions_with_outcomes(agent_name, since=since)

        if not decisions:
            return None

        # Count overrides (action != 0 means override)
        overrides = sum(1 for d in decisions if d["action"] != 0)
        total = len(decisions)
        override_rate = overrides / total

        if override_rate > max_override_rate:
            return Alert(
                alert_type=AlertType.EXCESSIVE_OVERRIDES,
                agent_name=agent_name,
                severity="warning",
                message=(
                    f"Override rate too high: {override_rate*100:.1f}% "
                    f"({overrides}/{total} decisions)"
                ),
                details={
                    "override_rate": override_rate,
                    "override_count": overrides,
                    "total_decisions": total,
                    "max_override_rate": max_override_rate,
                },
            )

        return None

    def check_decision_rate(
        self,
        agent_name: str,
        window_days: int = 7,
        min_decisions_per_day: float = 1.0,
    ) -> Optional[Alert]:
        """Check if agent decision rate is too low.

        Args:
            agent_name: Name of agent
            window_days: Days to check
            min_decisions_per_day: Minimum expected decisions per day

        Returns:
            Alert if decision rate too low, None otherwise
        """
        since = datetime.now() - timedelta(days=window_days)
        decision_count = self.agent_state.get_decision_count(agent_name, since=since)

        decisions_per_day = decision_count / window_days

        if decisions_per_day < min_decisions_per_day:
            return Alert(
                alert_type=AlertType.LOW_DECISION_RATE,
                agent_name=agent_name,
                severity="warning",
                message=(
                    f"Decision rate too low: {decisions_per_day:.1f} per day "
                    f"(expected >= {min_decisions_per_day:.1f})"
                ),
                details={
                    "decisions_per_day": decisions_per_day,
                    "total_decisions": decision_count,
                    "window_days": window_days,
                    "min_decisions_per_day": min_decisions_per_day,
                },
            )

        return None

    def check_all(
        self,
        agent_name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> List[Alert]:
        """Run all health checks for an agent.

        Args:
            agent_name: Name of agent
            config: Optional configuration for thresholds

        Returns:
            List of alerts
        """
        config = config or {}
        alerts = []

        # Check performance degradation
        alert = self.check_performance_degradation(
            agent_name,
            baseline_window_days=config.get("baseline_window_days", 90),
            recent_window_days=config.get("recent_window_days", 30),
            degradation_threshold=config.get("degradation_threshold", 0.3),
        )
        if alert:
            alerts.append(alert)

        # Check excessive overrides (meta-learner only)
        if agent_name == "meta_learner":
            alert = self.check_excessive_overrides(
                agent_name,
                window_days=config.get("override_window_days", 7),
                max_override_rate=config.get("max_override_rate", 0.3),
            )
            if alert:
                alerts.append(alert)

        # Check decision rate
        alert = self.check_decision_rate(
            agent_name,
            window_days=config.get("decision_rate_window_days", 7),
            min_decisions_per_day=config.get("min_decisions_per_day", 1.0),
        )
        if alert:
            alerts.append(alert)

        return alerts


def log_alerts(alerts: List[Alert]) -> None:
    """Log alerts to logger.

    Args:
        alerts: List of alerts to log
    """
    for alert in alerts:
        log_func = {
            "warning": logger.warning,
            "error": logger.error,
            "critical": logger.critical,
        }.get(alert.severity, logger.info)

        log_func(
            f"[{alert.agent_name}] {alert.alert_type}: {alert.message} "
            f"(details: {alert.details})"
        )
