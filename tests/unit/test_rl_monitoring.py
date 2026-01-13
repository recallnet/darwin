"""Unit tests for Monitoring and Safety (Phase 7).

Tests:
- AgentMonitor (alerts)
- CircuitBreaker
- SafetyMonitor
"""

import tempfile
import time
from datetime import datetime, timedelta

import pytest

from darwin.rl.monitoring.alerts import AgentMonitor, Alert, AlertType, log_alerts
from darwin.rl.monitoring.safety import CircuitBreaker, SafetyMonitor, SafetyConfig
from darwin.rl.schemas.agent_state import AgentDecisionV1
from darwin.rl.schemas.rl_config import (
    AgentConfigV1,
    GraduationThresholdsV1,
    RLConfigV1,
)
from darwin.rl.storage.agent_state import AgentStateSQLite


class TestAgentMonitor:
    """Test agent monitoring."""

    def create_agent_state_with_decisions(
        self, agent_name: str, good_count: int = 50, bad_count: int = 0
    ) -> AgentStateSQLite:
        """Create agent state with sample decisions.

        Args:
            agent_name: Agent name
            good_count: Number of good decisions (R=1.5)
            bad_count: Number of bad decisions (R=-1.0)

        Returns:
            Agent state with data
        """
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
        temp_db.close()

        agent_state = AgentStateSQLite(temp_db.name)

        # Add good decisions (older)
        base_time = datetime.now() - timedelta(days=60)
        for i in range(good_count):
            decision = AgentDecisionV1(
                agent_name=agent_name,
                candidate_id=f"cand_{i:03d}",
                run_id="run_001",
                timestamp=base_time + timedelta(days=i / 2),
                state_hash="test_hash",
                action=1,
                mode="observe",
                model_version="v1.0",
            )
            agent_state.record_decision(decision)
            agent_state.update_decision_outcome(
                agent_name=agent_name,
                candidate_id=f"cand_{i:03d}",
                outcome_r_multiple=1.5,
                outcome_pnl_usd=1500.0,
            )

        # Add bad decisions (recent)
        recent_time = datetime.now() - timedelta(days=10)
        for i in range(bad_count):
            idx = good_count + i
            decision = AgentDecisionV1(
                agent_name=agent_name,
                candidate_id=f"cand_{idx:03d}",
                run_id="run_001",
                timestamp=recent_time + timedelta(days=i / 2),
                state_hash="test_hash",
                action=1,
                mode="observe",
                model_version="v1.0",
            )
            agent_state.record_decision(decision)
            agent_state.update_decision_outcome(
                agent_name=agent_name,
                candidate_id=f"cand_{idx:03d}",
                outcome_r_multiple=-1.0,
                outcome_pnl_usd=-1000.0,
            )

        return agent_state

    def test_monitor_no_degradation(self):
        """Test monitoring with no performance degradation."""
        agent_state = self.create_agent_state_with_decisions("gate", good_count=50)
        monitor = AgentMonitor(agent_state)

        alert = monitor.check_performance_degradation("gate")

        # Should be no alert
        assert alert is None

        agent_state.close()

    def test_monitor_performance_degradation(self):
        """Test monitoring detects performance degradation."""
        # Create good baseline, then bad recent performance
        agent_state = self.create_agent_state_with_decisions(
            "gate", good_count=30, bad_count=20
        )
        monitor = AgentMonitor(agent_state)

        alert = monitor.check_performance_degradation(
            "gate",
            baseline_window_days=90,
            recent_window_days=30,
            degradation_threshold=0.3,
        )

        # Should detect degradation
        assert alert is not None
        assert alert.alert_type == AlertType.PERFORMANCE_DEGRADATION
        assert alert.agent_name == "gate"
        assert alert.severity == "warning"
        assert "degraded" in alert.message.lower()

        agent_state.close()

    def test_monitor_excessive_overrides(self):
        """Test monitoring detects excessive meta-learner overrides."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
        temp_db.close()

        agent_state = AgentStateSQLite(temp_db.name)

        # Add decisions with many overrides
        for i in range(50):
            # 70% overrides (action != 0)
            action = 1 if i < 35 else 0

            decision = AgentDecisionV1(
                agent_name="meta_learner",
                candidate_id=f"cand_{i:03d}",
                run_id="run_001",
                timestamp=datetime.now() - timedelta(days=3 - i / 20),
                state_hash="test_hash",
                action=action,
                mode="observe",
                model_version="v1.0",
            )
            agent_state.record_decision(decision)

            # Add outcome so decision is included in queries
            agent_state.update_decision_outcome(
                agent_name="meta_learner",
                candidate_id=f"cand_{i:03d}",
                outcome_r_multiple=1.0,
                outcome_pnl_usd=1000.0,
            )

        monitor = AgentMonitor(agent_state)

        alert = monitor.check_excessive_overrides(
            "meta_learner", window_days=7, max_override_rate=0.3
        )

        # Should detect excessive overrides (70% > 30%)
        assert alert is not None
        assert alert.alert_type == AlertType.EXCESSIVE_OVERRIDES
        assert alert.agent_name == "meta_learner"
        assert alert.details["override_rate"] > 0.3

        agent_state.close()

    def test_monitor_low_decision_rate(self):
        """Test monitoring detects low decision rate."""
        agent_state = self.create_agent_state_with_decisions("gate", good_count=2)
        monitor = AgentMonitor(agent_state)

        alert = monitor.check_decision_rate(
            "gate", window_days=7, min_decisions_per_day=1.0
        )

        # Should detect low decision rate (2 decisions over 7 days < 1/day)
        assert alert is not None
        assert alert.alert_type == AlertType.LOW_DECISION_RATE
        assert alert.agent_name == "gate"

        agent_state.close()

    def test_monitor_check_all(self):
        """Test running all checks."""
        agent_state = self.create_agent_state_with_decisions(
            "gate", good_count=30, bad_count=20
        )
        monitor = AgentMonitor(agent_state)

        alerts = monitor.check_all("gate")

        # Should have at least performance degradation alert
        assert len(alerts) > 0
        assert any(a.alert_type == AlertType.PERFORMANCE_DEGRADATION for a in alerts)

        agent_state.close()


class TestCircuitBreaker:
    """Test circuit breaker."""

    def test_circuit_breaker_starts_closed(self):
        """Test circuit breaker starts in closed state."""
        breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=5)

        assert breaker.can_proceed()
        assert not breaker.is_open

    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures."""
        breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=5)

        # Record 3 failures
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()

        # Should be open
        assert breaker.is_open
        assert not breaker.can_proceed()

    def test_circuit_breaker_resets_on_success(self):
        """Test circuit breaker resets on success."""
        breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=5)

        # Record 2 failures
        breaker.record_failure()
        breaker.record_failure()

        # Record success
        breaker.record_success()

        # Should be closed
        assert not breaker.is_open
        assert breaker.can_proceed()

    def test_circuit_breaker_closes_after_timeout(self):
        """Test circuit breaker attempts to close after timeout."""
        breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=1)

        # Record failures to open circuit
        breaker.record_failure()
        breaker.record_failure()

        assert breaker.is_open
        assert not breaker.can_proceed()

        # Wait for timeout
        time.sleep(1.1)

        # Should attempt to close
        assert breaker.can_proceed()
        assert not breaker.is_open


class TestSafetyMonitor:
    """Test safety monitor."""

    def create_rl_config(self) -> RLConfigV1:
        """Create sample RL config.

        Returns:
            RL config
        """
        return RLConfigV1(
            enabled=True,
            gate_agent=AgentConfigV1(
                name="gate",
                enabled=True,
                mode="observe",
                model_path=None,
                graduation_thresholds=GraduationThresholdsV1(
                    min_training_samples=100,
                    min_validation_samples=20,
                    min_validation_metric=0.1,
                    baseline_type="pass_all",
                    min_improvement_pct=10.0,
                ),
            ),
            meta_learner_agent=AgentConfigV1(
                name="meta_learner",
                enabled=True,
                mode="observe",
                model_path=None,
                graduation_thresholds=GraduationThresholdsV1(
                    min_training_samples=2000,
                    min_validation_samples=400,
                    min_validation_metric=0.1,
                    baseline_type="llm_only",
                    min_improvement_pct=10.0,
                ),
            ),
            agent_state_db="test.sqlite",
            max_override_rate=0.2,
        )

    def test_safety_monitor_circuit_breaker(self):
        """Test safety monitor circuit breaker."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
        temp_db.close()

        agent_state = AgentStateSQLite(temp_db.name)
        config = self.create_rl_config()
        monitor = SafetyMonitor(config, agent_state)

        # Initially can act
        assert monitor.can_agent_act("gate")

        # Record failures
        for _ in range(5):
            monitor.record_agent_failure("gate", Exception("test error"))

        # Should be blocked
        assert not monitor.can_agent_act("gate")

        # Record success
        monitor.record_agent_success("gate")

        # Should be unblocked
        assert monitor.can_agent_act("gate")

        agent_state.close()

    def test_safety_monitor_override_rate_limit(self):
        """Test safety monitor override rate limiting."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
        temp_db.close()

        agent_state = AgentStateSQLite(temp_db.name)

        # Add decisions with high override rate
        for i in range(50):
            # 80% overrides
            action = 1 if i < 40 else 0

            decision = AgentDecisionV1(
                agent_name="meta_learner",
                candidate_id=f"cand_{i:03d}",
                run_id="run_001",
                timestamp=datetime.now() - timedelta(minutes=30 - i / 2),
                state_hash="test_hash",
                action=action,
                mode="observe",
                model_version="v1.0",
            )
            agent_state.record_decision(decision)

            # Add outcome so decision is included in queries
            agent_state.update_decision_outcome(
                agent_name="meta_learner",
                candidate_id=f"cand_{i:03d}",
                outcome_r_multiple=1.0,
                outcome_pnl_usd=1000.0,
            )

        config = self.create_rl_config()
        config.max_override_rate = 0.2  # 20% max
        monitor = SafetyMonitor(config, agent_state)

        # Should exceed limit (80% > 20%)
        within_limit = monitor.check_override_rate_limit("meta_learner", window_minutes=60)
        assert not within_limit

        agent_state.close()


class TestAlert:
    """Test alert object."""

    def test_alert_creation(self):
        """Test alert creation."""
        alert = Alert(
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            agent_name="gate",
            severity="warning",
            message="Performance degraded",
            details={"degradation_pct": 30.0},
        )

        assert alert.alert_type == AlertType.PERFORMANCE_DEGRADATION
        assert alert.agent_name == "gate"
        assert alert.severity == "warning"
        assert alert.message == "Performance degraded"

    def test_alert_to_dict(self):
        """Test alert conversion to dictionary."""
        alert = Alert(
            alert_type=AlertType.EXCESSIVE_OVERRIDES,
            agent_name="meta_learner",
            severity="error",
            message="Too many overrides",
            details={"override_rate": 0.5},
        )

        alert_dict = alert.to_dict()

        assert alert_dict["alert_type"] == AlertType.EXCESSIVE_OVERRIDES
        assert alert_dict["agent_name"] == "meta_learner"
        assert alert_dict["severity"] == "error"
        assert "timestamp" in alert_dict
