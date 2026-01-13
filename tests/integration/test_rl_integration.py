"""Integration tests for RL system integration with runner."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from darwin.rl.integration.runner_hooks import RLSystem
from darwin.rl.schemas.rl_config import AgentConfigV1, GraduationThresholdsV1, RLConfigV1
from darwin.schemas.candidate import CandidateRecordV1, ExitSpecV1, PlaybookType


class TestRLSystemInitialization:
    """Test RL system initialization."""

    def test_rl_system_initialization_without_agents(self):
        """Test RL system initialization with no agents enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_state_db = str(Path(tmpdir) / "agent_state.sqlite")

            config = RLConfigV1(
                enabled=True,
                agent_state_db=agent_state_db,
            )

            rl_system = RLSystem(config=config, run_id="test_run_001")

            # No agents should be active
            assert not rl_system.gate_agent_active()
            assert not rl_system.portfolio_agent_active()
            assert not rl_system.meta_learner_agent_active()

            rl_system.close()

    def test_rl_system_initialization_with_gate_agent_observe_mode(self):
        """Test RL system initialization with gate agent in observe mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_state_db = str(Path(tmpdir) / "agent_state.sqlite")

            config = RLConfigV1(
                enabled=True,
                agent_state_db=agent_state_db,
                gate_agent=AgentConfigV1(
                    name="gate",
                    enabled=True,
                    mode="observe",
                    model_path=None,  # No model loaded
                    graduation_thresholds=GraduationThresholdsV1(
                        min_training_samples=1000,
                        min_validation_samples=200,
                        min_validation_metric=0.1,
                        baseline_type="pass_all",
                        min_improvement_pct=20.0,
                    ),
                ),
            )

            rl_system = RLSystem(config=config, run_id="test_run_001")

            # Gate agent should not be active (observe mode)
            assert not rl_system.gate_agent_active()
            assert rl_system.gate_agent is not None

            rl_system.close()

    def test_rl_system_initialization_with_gate_agent_active_mode_no_model(self):
        """Test RL system initialization with gate agent in active mode but no model."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_state_db = str(Path(tmpdir) / "agent_state.sqlite")

            config = RLConfigV1(
                enabled=True,
                agent_state_db=agent_state_db,
                gate_agent=AgentConfigV1(
                    name="gate",
                    enabled=True,
                    mode="active",
                    model_path=None,  # No model loaded
                    graduation_thresholds=GraduationThresholdsV1(
                        min_training_samples=1000,
                        min_validation_samples=200,
                        min_validation_metric=0.1,
                        baseline_type="pass_all",
                        min_improvement_pct=20.0,
                    ),
                ),
            )

            rl_system = RLSystem(config=config, run_id="test_run_001")

            # Gate agent should not be active (no model loaded)
            assert not rl_system.gate_agent_active()

            rl_system.close()


class TestGateAgentHooks:
    """Test gate agent hook behavior."""

    def test_gate_hook_without_rl_system(self):
        """Test gate hook returns None when gate agent is not configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_state_db = str(Path(tmpdir) / "agent_state.sqlite")

            config = RLConfigV1(
                enabled=True,
                agent_state_db=agent_state_db,
            )

            rl_system = RLSystem(config=config, run_id="test_run_001")

            candidate = CandidateRecordV1(
                candidate_id="cand_001",
                run_id="test_run_001",
                timestamp=datetime.now(),
                symbol="BTC-USD",
                timeframe="15m",
                bar_index=100,
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
                features={"close": 45000.0},
                was_taken=False,
            )

            portfolio_state = {"open_positions": 0, "exposure_frac": 0.0}

            # Gate hook should return None (pass)
            result = rl_system.gate_hook(candidate, portfolio_state)
            assert result is None

            rl_system.close()

    def test_gate_hook_observe_mode(self):
        """Test gate hook in observe mode doesn't affect decisions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_state_db = str(Path(tmpdir) / "agent_state.sqlite")

            config = RLConfigV1(
                enabled=True,
                agent_state_db=agent_state_db,
                gate_agent=AgentConfigV1(
                    name="gate",
                    enabled=True,
                    mode="observe",
                    model_path=None,
                    graduation_thresholds=GraduationThresholdsV1(
                        min_training_samples=1000,
                        min_validation_samples=200,
                        min_validation_metric=0.1,
                        baseline_type="pass_all",
                        min_improvement_pct=20.0,
                    ),
                ),
            )

            rl_system = RLSystem(config=config, run_id="test_run_001")

            candidate = CandidateRecordV1(
                candidate_id="cand_001",
                run_id="test_run_001",
                timestamp=datetime.now(),
                symbol="BTC-USD",
                timeframe="15m",
                bar_index=100,
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
                features={"close": 45000.0},
                was_taken=False,
            )

            portfolio_state = {"open_positions": 0, "exposure_frac": 0.0}

            # Gate hook should return None (observe mode doesn't affect decisions)
            result = rl_system.gate_hook(candidate, portfolio_state)
            assert result is None

            rl_system.close()


class TestDecisionOutcomeTracking:
    """Test decision outcome tracking."""

    def test_update_decision_outcome(self):
        """Test updating decision outcomes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_state_db = str(Path(tmpdir) / "agent_state.sqlite")

            config = RLConfigV1(
                enabled=True,
                agent_state_db=agent_state_db,
            )

            rl_system = RLSystem(config=config, run_id="test_run_001")

            # Update outcome (should not crash even without recorded decision)
            rl_system.update_decision_outcome(
                candidate_id="cand_001", r_multiple=1.5, pnl_usd=750.0
            )

            rl_system.close()


class TestRunConfigRLIntegration:
    """Test RunConfigV1 with RL configuration."""

    def test_run_config_without_rl(self):
        """Test run config without RL configuration."""
        from darwin.schemas.run_config import (
            FeesConfigV1,
            LLMConfigV1,
            MarketScopeV1,
            PlaybookConfigV1,
            PortfolioConfigV1,
            RunConfigV1,
        )

        config = RunConfigV1(
            run_id="test_run_001",
            description="Test run without RL",
            market_scope=MarketScopeV1(
                symbols=["BTC-USD"],
                timeframes=["15m"],
                start_date="2024-01-01",
                end_date="2024-01-31",
            ),
            fees=FeesConfigV1(),
            portfolio=PortfolioConfigV1(),
            llm=LLMConfigV1(),
            playbooks=[
                PlaybookConfigV1(
                    name="breakout",
                    stop_loss_atr=1.0,
                    take_profit_atr=2.0,
                    time_stop_bars=32,
                    trailing_activation_atr=1.0,
                    trailing_distance_atr=0.5,
                )
            ],
        )

        # RL should be None
        assert config.rl is None

    def test_run_config_with_rl(self):
        """Test run config with RL configuration."""
        from darwin.schemas.run_config import (
            FeesConfigV1,
            LLMConfigV1,
            MarketScopeV1,
            PlaybookConfigV1,
            PortfolioConfigV1,
            RunConfigV1,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            agent_state_db = str(Path(tmpdir) / "agent_state.sqlite")

            config = RunConfigV1(
                run_id="test_run_001",
                description="Test run with RL",
                market_scope=MarketScopeV1(
                    symbols=["BTC-USD"],
                    timeframes=["15m"],
                    start_date="2024-01-01",
                    end_date="2024-01-31",
                ),
                fees=FeesConfigV1(),
                portfolio=PortfolioConfigV1(),
                llm=LLMConfigV1(),
                rl=RLConfigV1(
                    enabled=True,
                    agent_state_db=agent_state_db,
                    gate_agent=AgentConfigV1(
                        name="gate",
                        enabled=True,
                        mode="observe",
                        graduation_thresholds=GraduationThresholdsV1(
                            min_training_samples=1000,
                            min_validation_samples=200,
                            min_validation_metric=0.1,
                            baseline_type="pass_all",
                            min_improvement_pct=20.0,
                        ),
                    ),
                ),
                playbooks=[
                    PlaybookConfigV1(
                        name="breakout",
                        stop_loss_atr=1.0,
                        take_profit_atr=2.0,
                        time_stop_bars=32,
                        trailing_activation_atr=1.0,
                        trailing_distance_atr=0.5,
                    )
                ],
            )

            # RL should be configured
            assert config.rl is not None
            assert config.rl.enabled is True
            assert config.rl.gate_agent is not None
            assert config.rl.gate_agent.enabled is True
            assert config.rl.gate_agent.mode == "observe"
