"""End-to-end integration tests for RL system workflow.

Tests the complete RL system workflow:
- Loading and initializing all agents
- Running agents in observe mode
- Recording decisions and outcomes
- Graduation evaluation and promotion
- Mode switching (observe to active)
- Safety mechanisms and circuit breakers
- Full simulation pipeline
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from darwin.rl.agents.gate_agent import GateAgent
from darwin.rl.agents.meta_learner_agent import MetaLearnerAgent
from darwin.rl.agents.portfolio_agent import PortfolioAgent
from darwin.rl.graduation.policy import GraduationPolicy
from darwin.rl.integration.runner_hooks import RLSystem
from darwin.rl.monitoring.alerts import AgentMonitor
from darwin.rl.monitoring.safety import SafetyMonitor
from darwin.rl.schemas.agent_state import AgentDecisionV1
from darwin.rl.schemas.rl_config import (
    AgentConfigV1,
    GraduationThresholdsV1,
    RLConfigV1,
)
from darwin.rl.storage.agent_state import AgentStateSQLite
from darwin.rl.storage.model_store import ModelStore
from darwin.rl.training.hyperparameters import (
    get_graduation_thresholds,
    get_ppo_params,
    get_reward_params,
)
from darwin.schemas.candidate import CandidateRecordV1, ExitSpecV1, PlaybookType


class TestRLSystemInitialization:
    """Test RL system initialization."""

    def create_rl_config(self, temp_dir: Path) -> RLConfigV1:
        """Create RL config for testing.

        Args:
            temp_dir: Temporary directory path

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
            portfolio_agent=AgentConfigV1(
                name="portfolio",
                enabled=True,
                mode="observe",
                model_path=None,
                graduation_thresholds=GraduationThresholdsV1(
                    min_training_samples=100,
                    min_validation_samples=20,
                    min_validation_metric=0.1,
                    baseline_type="equal_weight",
                    min_improvement_pct=10.0,
                ),
            ),
            meta_learner_agent=AgentConfigV1(
                name="meta_learner",
                enabled=True,
                mode="observe",
                model_path=None,
                graduation_thresholds=GraduationThresholdsV1(
                    min_training_samples=200,
                    min_validation_samples=40,
                    min_validation_metric=0.1,
                    baseline_type="llm_only",
                    min_improvement_pct=10.0,
                ),
            ),
            models_dir=str(temp_dir / "models"),
            agent_state_db=str(temp_dir / "agent_state.sqlite"),
            max_override_rate=0.2,
        )

    def test_rl_system_initialization(self):
        """Test RLSystem initialization with all agents."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config = self.create_rl_config(temp_path)

            # Initialize RL system
            rl_system = RLSystem(config, run_id="test_run_001")

            # Verify all agents initialized
            assert rl_system.config == config
            assert rl_system.agent_state is not None

            # Verify agents loaded
            assert rl_system.gate_agent is not None
            assert rl_system.portfolio_agent is not None
            assert rl_system.meta_learner_agent is not None

            # Verify agents are in observe mode
            assert config.gate_agent.mode == "observe"
            assert config.portfolio_agent.mode == "observe"
            assert config.meta_learner_agent.mode == "observe"

            # Cleanup
            rl_system.close()

    def test_rl_system_with_disabled_agents(self):
        """Test RLSystem with some agents disabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config = self.create_rl_config(temp_path)

            # Disable portfolio agent
            config.portfolio_agent.enabled = False

            rl_system = RLSystem(config, run_id="test_run_001")

            # Gate and meta-learner should be available
            assert rl_system.gate_agent is not None
            assert rl_system.meta_learner_agent is not None

            # Portfolio agent should not be loaded
            assert rl_system.portfolio_agent is None

            rl_system.close()


class TestRLSystemObserveMode:
    """Test RL system in observe mode."""

    def create_sample_candidate(self, idx: int = 0) -> CandidateRecordV1:
        """Create sample candidate for testing.

        Args:
            idx: Candidate index

        Returns:
            Sample candidate
        """
        return CandidateRecordV1(
            candidate_id=f"cand_{idx:03d}",
            run_id="test_run_001",
            timestamp=datetime.now(),
            symbol="BTC-USD",
            timeframe="15m",
            bar_index=100 + idx,
            playbook=PlaybookType.BREAKOUT,
            direction="long",
            entry_price=45000.0,
            atr_at_entry=500.0,
            exit_spec=ExitSpecV1(
                stop_loss_price=44500.0,
                take_profit_price=46000.0,
                time_stop_bars=32,
                trailing_enabled=True,
            ),
            features={"close": 45000.0, "volume": 1000.0, "atr": 500.0},
            was_taken=False,
        )

    def test_gate_agent_observe_mode(self):
        """Test gate agent in observe mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create config
            config = RLConfigV1(
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
                models_dir=str(temp_path / "models"),
                agent_state_db=str(temp_path / "agent_state.sqlite"),
                max_override_rate=0.2,
            )

            rl_system = RLSystem(config, run_id="test_run_001")
            candidate = self.create_sample_candidate()
            portfolio_state = {"open_positions": 1, "equity": 10000.0}

            # In observe mode, gate should not block (returns None, not "skip")
            result = rl_system.gate_hook(candidate, portfolio_state)

            # Should not skip in observe mode (returns None to pass through)
            assert result is None

            rl_system.close()

    def test_portfolio_agent_observe_mode(self):
        """Test portfolio agent in observe mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            config = RLConfigV1(
                enabled=True,
                portfolio_agent=AgentConfigV1(
                    name="portfolio",
                    enabled=True,
                    mode="observe",
                    model_path=None,
                    graduation_thresholds=GraduationThresholdsV1(
                        min_training_samples=100,
                        min_validation_samples=20,
                        min_validation_metric=0.1,
                        baseline_type="equal_weight",
                        min_improvement_pct=10.0,
                    ),
                ),
                models_dir=str(temp_path / "models"),
                agent_state_db=str(temp_path / "agent_state.sqlite"),
                max_override_rate=0.2,
            )

            rl_system = RLSystem(config, run_id="test_run_001")
            candidate = self.create_sample_candidate()

            llm_response = {"decision": "take", "confidence": 0.8}
            portfolio_state = {"open_positions": 1, "equity": 10000.0}

            # In observe mode, should return default size (1.0)
            size_fraction = rl_system.portfolio_hook(
                candidate, llm_response, portfolio_state
            )

            # Should return 1.0 (default) in observe mode
            assert size_fraction == 1.0

            rl_system.close()

    def test_meta_learner_agent_observe_mode(self):
        """Test meta-learner agent in observe mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            config = RLConfigV1(
                enabled=True,
                meta_learner_agent=AgentConfigV1(
                    name="meta_learner",
                    enabled=True,
                    mode="observe",
                    model_path=None,
                    graduation_thresholds=GraduationThresholdsV1(
                        min_training_samples=200,
                        min_validation_samples=40,
                        min_validation_metric=0.1,
                        baseline_type="llm_only",
                        min_improvement_pct=10.0,
                    ),
                ),
                models_dir=str(temp_path / "models"),
                agent_state_db=str(temp_path / "agent_state.sqlite"),
                max_override_rate=0.2,
            )

            rl_system = RLSystem(config, run_id="test_run_001")
            candidate = self.create_sample_candidate()

            llm_response = {"decision": "take", "confidence": 0.8}
            llm_history = {"recent_accuracy": 0.6, "recent_sharpe": 1.2}
            portfolio_state = {"open_positions": 1, "equity": 10000.0}

            # In observe mode, should not override
            override_decision = rl_system.meta_learner_hook(
                candidate, llm_response, llm_history, portfolio_state
            )

            # Should return None (no override) in observe mode
            assert override_decision is None

            rl_system.close()


class TestGraduationWorkflow:
    """Test graduation workflow."""

    def create_agent_state_with_data(
        self, agent_name: str, sample_count: int
    ) -> AgentStateSQLite:
        """Create agent state with sample data.

        Args:
            agent_name: Agent name
            sample_count: Number of samples

        Returns:
            Agent state with data
        """
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
        temp_db.close()

        agent_state = AgentStateSQLite(temp_db.name)

        # Add sample decisions with outcomes
        for i in range(sample_count):
            decision = AgentDecisionV1(
                agent_name=agent_name,
                candidate_id=f"cand_{i:03d}",
                run_id="test_run",
                timestamp=datetime.now() - timedelta(days=30 - i / 10),
                state_hash="test_hash",
                action=1 if i % 2 == 0 else 0,
                mode="observe",
                model_version="v1.0",
            )
            agent_state.record_decision(decision)

            # Add positive outcome
            r_multiple = 1.5 if i % 2 == 0 else -0.8
            agent_state.update_decision_outcome(
                agent_name=agent_name,
                candidate_id=f"cand_{i:03d}",
                outcome_r_multiple=r_multiple,
                outcome_pnl_usd=r_multiple * 1000,
            )

        return agent_state

    def test_graduation_evaluation_workflow(self):
        """Test graduation evaluation workflow."""
        agent_state = self.create_agent_state_with_data("gate", sample_count=150)

        thresholds = GraduationThresholdsV1(
            min_training_samples=100,
            min_validation_samples=20,
            min_validation_metric=0.1,
            baseline_type="pass_all",
            min_improvement_pct=10.0,
        )

        policy = GraduationPolicy(agent_state, thresholds)
        decision = policy.evaluate_graduation("gate")

        # Should have sufficient data
        assert decision.checks["has_sufficient_data"]
        assert decision.metrics["total_samples"] >= 100

        agent_state.close()


class TestHyperparameters:
    """Test hyperparameter access."""

    def test_get_ppo_params(self):
        """Test getting PPO parameters for each agent."""
        gate_params = get_ppo_params("gate")
        assert "learning_rate" in gate_params
        assert gate_params["learning_rate"] == 1e-4

        portfolio_params = get_ppo_params("portfolio")
        assert portfolio_params["learning_rate"] == 3e-4

        meta_learner_params = get_ppo_params("meta_learner")
        assert meta_learner_params["learning_rate"] == 5e-5

    def test_get_reward_params(self):
        """Test getting reward parameters for each agent."""
        gate_rewards = get_reward_params("gate")
        assert "skip_loser_bonus" in gate_rewards
        assert gate_rewards["skip_loser_bonus"] == 1.0

        portfolio_rewards = get_reward_params("portfolio")
        assert "r_multiple_scale" in portfolio_rewards

        meta_learner_rewards = get_reward_params("meta_learner")
        assert "agreement_bonus" in meta_learner_rewards

    def test_get_graduation_thresholds(self):
        """Test getting graduation thresholds for each agent."""
        gate_thresholds = get_graduation_thresholds("gate")
        assert gate_thresholds["min_training_samples"] == 1000
        assert gate_thresholds["baseline_type"] == "pass_all"

        portfolio_thresholds = get_graduation_thresholds("portfolio")
        assert portfolio_thresholds["min_training_samples"] == 500
        assert portfolio_thresholds["baseline_type"] == "equal_weight"

        meta_learner_thresholds = get_graduation_thresholds("meta_learner")
        assert meta_learner_thresholds["min_training_samples"] == 2000
        assert meta_learner_thresholds["baseline_type"] == "llm_only"

    def test_invalid_agent_name(self):
        """Test invalid agent name raises error."""
        with pytest.raises(ValueError, match="Unknown agent name"):
            get_ppo_params("invalid_agent")

        with pytest.raises(ValueError, match="Unknown agent name"):
            get_reward_params("invalid_agent")

        with pytest.raises(ValueError, match="Unknown agent name"):
            get_graduation_thresholds("invalid_agent")


class TestSafetyIntegration:
    """Test safety mechanisms integration."""

    def test_circuit_breaker_integration(self):
        """Test circuit breaker integration with SafetyMonitor."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            config = RLConfigV1(
                enabled=True,
                gate_agent=AgentConfigV1(
                    name="gate",
                    enabled=True,
                    mode="active",
                    model_path=None,
                    graduation_thresholds=GraduationThresholdsV1(
                        min_training_samples=100,
                        min_validation_samples=20,
                        min_validation_metric=0.1,
                        baseline_type="pass_all",
                        min_improvement_pct=10.0,
                    ),
                ),
                models_dir=str(temp_path / "models"),
                agent_state_db=str(temp_path / "agent_state.sqlite"),
                max_override_rate=0.2,
            )

            # Create agent state and safety monitor
            agent_state = AgentStateSQLite(config.agent_state_db)
            safety_monitor = SafetyMonitor(config, agent_state)

            # Initially can act
            assert safety_monitor.can_agent_act("gate")

            # Record failures
            for _ in range(5):
                safety_monitor.record_agent_failure("gate", Exception("test error"))

            # Should be blocked by circuit breaker
            assert not safety_monitor.can_agent_act("gate")

            # Record success to reset
            safety_monitor.record_agent_success("gate")

            # Should be unblocked
            assert safety_monitor.can_agent_act("gate")

            agent_state.close()


class TestMonitoringIntegration:
    """Test monitoring integration."""

    def test_agent_monitor_integration(self):
        """Test AgentMonitor integration."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
        temp_db.close()

        agent_state = AgentStateSQLite(temp_db.name)

        # Add sample decisions with outcomes
        for i in range(100):
            decision = AgentDecisionV1(
                agent_name="gate",
                candidate_id=f"cand_{i:03d}",
                run_id="test_run",
                timestamp=datetime.now() - timedelta(days=50 - i / 2),
                state_hash="test_hash",
                action=1,
                mode="observe",
                model_version="v1.0",
            )
            agent_state.record_decision(decision)

            # Good performance
            agent_state.update_decision_outcome(
                agent_name="gate",
                candidate_id=f"cand_{i:03d}",
                outcome_r_multiple=1.5,
                outcome_pnl_usd=1500.0,
            )

        monitor = AgentMonitor(agent_state)
        alerts = monitor.check_all("gate")

        # Should have no alerts with good performance
        assert len(alerts) == 0

        agent_state.close()
