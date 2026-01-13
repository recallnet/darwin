"""Safety mechanisms for RL agents."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from darwin.rl.schemas.rl_config import RLConfigV1
from darwin.rl.storage.agent_state import AgentStateSQLite

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker for agent failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 300,
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout_seconds: Seconds before attempting to close circuit
        """
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.is_open = False

    def record_success(self) -> None:
        """Record successful operation."""
        self.failure_count = 0
        self.is_open = False

    def record_failure(self) -> None:
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            logger.error(
                f"Circuit breaker OPEN after {self.failure_count} failures. "
                f"Will retry after {self.timeout_seconds}s."
            )

    def can_proceed(self) -> bool:
        """Check if operation can proceed.

        Returns:
            True if circuit is closed or timeout expired
        """
        if not self.is_open:
            return True

        # Check if timeout expired
        if self.last_failure_time:
            elapsed = (datetime.now() - self.last_failure_time).total_seconds()
            if elapsed >= self.timeout_seconds:
                logger.info("Circuit breaker attempting to close (timeout expired)")
                self.is_open = False
                self.failure_count = 0
                return True

        return False


class SafetyMonitor:
    """Safety monitor for RL system."""

    def __init__(
        self,
        config: RLConfigV1,
        agent_state: AgentStateSQLite,
    ):
        """Initialize safety monitor.

        Args:
            config: RL configuration
            agent_state: Agent state storage
        """
        self.config = config
        self.agent_state = agent_state

        # Circuit breakers for each agent
        self.circuit_breakers: Dict[str, CircuitBreaker] = {
            "gate": CircuitBreaker(),
            "portfolio": CircuitBreaker(),
            "meta_learner": CircuitBreaker(),
        }

    def can_agent_act(self, agent_name: str) -> bool:
        """Check if agent can act (circuit breaker check).

        Args:
            agent_name: Name of agent

        Returns:
            True if agent can act
        """
        breaker = self.circuit_breakers.get(agent_name)
        if not breaker:
            return True

        return breaker.can_proceed()

    def record_agent_success(self, agent_name: str) -> None:
        """Record successful agent operation.

        Args:
            agent_name: Name of agent
        """
        breaker = self.circuit_breakers.get(agent_name)
        if breaker:
            breaker.record_success()

    def record_agent_failure(self, agent_name: str, error: Exception) -> None:
        """Record failed agent operation.

        Args:
            agent_name: Name of agent
            error: Exception that occurred
        """
        logger.error(f"Agent {agent_name} failure: {error}")

        breaker = self.circuit_breakers.get(agent_name)
        if breaker:
            breaker.record_failure()

    def check_override_rate_limit(
        self,
        agent_name: str,
        window_minutes: int = 60,
    ) -> bool:
        """Check if override rate is within limits (meta-learner only).

        Args:
            agent_name: Name of agent
            window_minutes: Time window in minutes

        Returns:
            True if within limits, False if exceeded
        """
        if agent_name != "meta_learner":
            return True  # Only applies to meta-learner

        if not self.config.meta_learner_agent:
            return True

        # Get max override rate from config (default 20%)
        max_override_rate = getattr(self.config, "max_override_rate", 0.2)

        # Get recent decisions
        since = datetime.now() - timedelta(minutes=window_minutes)
        decisions = self.agent_state.get_decisions_with_outcomes(agent_name, since=since)

        if not decisions:
            return True  # No decisions yet

        # Count overrides (action != 0)
        overrides = sum(1 for d in decisions if d["action"] != 0)
        total = len(decisions)
        override_rate = overrides / total

        if override_rate > max_override_rate:
            logger.warning(
                f"Meta-learner override rate limit exceeded: {override_rate*100:.1f}% "
                f"(max: {max_override_rate*100:.1f}%, window: {window_minutes}min)"
            )
            return False

        return True

    def should_fallback_to_baseline(
        self,
        agent_name: str,
        window_days: int = 7,
        min_performance_threshold: float = -0.5,
    ) -> bool:
        """Check if agent should fallback to baseline due to poor performance.

        Args:
            agent_name: Name of agent
            window_days: Days to check
            min_performance_threshold: Minimum acceptable mean R-multiple

        Returns:
            True if should fallback to baseline
        """
        # Get recent performance
        since = datetime.now() - timedelta(days=window_days)
        decisions = self.agent_state.get_decisions_with_outcomes(agent_name, since=since)

        if not decisions:
            return False  # Not enough data

        # Calculate mean R-multiple
        r_multiples = [
            d["outcome_r_multiple"]
            for d in decisions
            if d["outcome_r_multiple"] is not None
        ]

        if not r_multiples:
            return False

        import numpy as np

        mean_r = float(np.mean(r_multiples))

        if mean_r < min_performance_threshold:
            logger.warning(
                f"Agent {agent_name} performance below threshold: {mean_r:.3f} "
                f"(threshold: {min_performance_threshold:.3f}). Consider fallback."
            )
            return True

        return False


class SafetyConfig:
    """Safety configuration for RL system."""

    def __init__(
        self,
        enable_circuit_breakers: bool = True,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: int = 300,
        max_override_rate: float = 0.2,
        override_rate_window_minutes: int = 60,
        enable_fallback_on_degradation: bool = True,
        fallback_window_days: int = 7,
        fallback_threshold: float = -0.5,
    ):
        """Initialize safety configuration.

        Args:
            enable_circuit_breakers: Enable circuit breakers
            circuit_breaker_threshold: Failures before opening circuit
            circuit_breaker_timeout: Timeout before retrying (seconds)
            max_override_rate: Maximum override rate (0.2 = 20%)
            override_rate_window_minutes: Window for override rate check
            enable_fallback_on_degradation: Enable automatic fallback
            fallback_window_days: Days to check for fallback decision
            fallback_threshold: Minimum R-multiple before fallback
        """
        self.enable_circuit_breakers = enable_circuit_breakers
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self.max_override_rate = max_override_rate
        self.override_rate_window_minutes = override_rate_window_minutes
        self.enable_fallback_on_degradation = enable_fallback_on_degradation
        self.fallback_window_days = fallback_window_days
        self.fallback_threshold = fallback_threshold
