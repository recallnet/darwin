"""Unit tests for RL foundation (Phase 1).

Tests:
- RL configuration schemas
- Agent state storage (SQLite)
- Model store (versioning)
- State encoders
"""

import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from darwin.rl.schemas.agent_state import (
    AgentDecisionV1,
    AgentPerformanceSnapshotV1,
    GraduationRecordV1,
)
from darwin.rl.schemas.rl_config import AgentConfigV1, GraduationThresholdsV1, RLConfigV1
from darwin.rl.schemas.training_episode import (
    TrainingBatchV1,
    TrainingEpisodeV1,
    TrainingRunV1,
)
from darwin.rl.storage.agent_state import AgentStateSQLite
from darwin.rl.storage.model_store import ModelStore
from darwin.rl.utils.state_encoding import (
    GateStateEncoder,
    MetaLearnerStateEncoder,
    PortfolioStateEncoder,
)
from darwin.schemas.candidate import CandidateRecordV1, ExitSpecV1, PlaybookType


class TestRLConfigSchemas:
    """Test RL configuration schemas."""

    def test_graduation_thresholds_valid(self):
        """Test valid graduation thresholds."""
        thresholds = GraduationThresholdsV1(
            min_training_samples=1000,
            min_validation_samples=200,
            min_validation_metric=0.1,
            baseline_type="pass_all",
            min_improvement_pct=20.0,
        )

        assert thresholds.min_training_samples == 1000
        assert thresholds.min_validation_samples == 200
        assert thresholds.min_validation_metric == 0.1
        assert thresholds.baseline_type == "pass_all"
        assert thresholds.min_improvement_pct == 20.0

    def test_agent_config_valid(self):
        """Test valid agent configuration."""
        thresholds = GraduationThresholdsV1(
            min_training_samples=1000,
            min_validation_samples=200,
            min_validation_metric=0.1,
            baseline_type="pass_all",
            min_improvement_pct=20.0,
        )

        config = AgentConfigV1(
            name="gate",
            enabled=True,
            mode="observe",
            model_path="/path/to/model.zip",
            graduation_thresholds=thresholds,
        )

        assert config.name == "gate"
        assert config.enabled is True
        assert config.mode == "observe"
        assert config.current_status == "training"

    def test_rl_config_valid(self):
        """Test valid top-level RL configuration."""
        thresholds = GraduationThresholdsV1(
            min_training_samples=1000,
            min_validation_samples=200,
            min_validation_metric=0.1,
            baseline_type="pass_all",
            min_improvement_pct=20.0,
        )

        gate_agent = AgentConfigV1(
            name="gate",
            enabled=True,
            mode="observe",
            graduation_thresholds=thresholds,
        )

        portfolio_agent = AgentConfigV1(
            name="portfolio",
            enabled=False,
            mode="observe",
            graduation_thresholds=thresholds,
        )

        meta_learner_agent = AgentConfigV1(
            name="meta_learner",
            enabled=False,
            mode="observe",
            graduation_thresholds=thresholds,
        )

        rl_config = RLConfigV1(
            enabled=True,
            gate_agent=gate_agent,
            portfolio_agent=portfolio_agent,
            meta_learner_agent=meta_learner_agent,
        )

        assert rl_config.enabled is True
        assert rl_config.gate_agent.name == "gate"
        assert rl_config.max_override_rate == 0.2


class TestAgentStateSQLite:
    """Test agent state storage."""

    def test_create_database(self):
        """Test database creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "agent_state.sqlite"
            db = AgentStateSQLite(db_path)

            assert db_path.exists()
            db.close()

    def test_record_decision(self):
        """Test recording agent decision."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "agent_state.sqlite"
            db = AgentStateSQLite(db_path)

            decision = AgentDecisionV1(
                agent_name="gate",
                candidate_id="cand_001",
                run_id="run_001",
                timestamp=datetime.now(),
                state_hash="abc123",
                action=1.0,
                mode="observe",
                model_version="v1.0.0",
            )

            db.record_decision(decision)

            # Retrieve decision
            decisions = db.get_decisions("gate")
            assert len(decisions) == 1
            assert decisions[0].candidate_id == "cand_001"
            assert decisions[0].action == 1.0

            db.close()

    def test_update_decision_outcome(self):
        """Test updating decision with outcome."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "agent_state.sqlite"
            db = AgentStateSQLite(db_path)

            # Record decision
            decision = AgentDecisionV1(
                agent_name="gate",
                candidate_id="cand_001",
                run_id="run_001",
                timestamp=datetime.now(),
                state_hash="abc123",
                action=1.0,
                mode="observe",
                model_version="v1.0.0",
            )
            db.record_decision(decision)

            # Update with outcome
            db.update_decision_outcome(
                agent_name="gate",
                candidate_id="cand_001",
                outcome_r_multiple=1.5,
                outcome_pnl_usd=150.0,
            )

            # Verify outcome
            decisions = db.get_decisions("gate")
            assert decisions[0].outcome_r_multiple == 1.5
            assert decisions[0].outcome_pnl_usd == 150.0

            db.close()

    def test_save_performance_snapshot(self):
        """Test saving performance snapshot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "agent_state.sqlite"
            db = AgentStateSQLite(db_path)

            snapshot = AgentPerformanceSnapshotV1(
                agent_name="gate",
                snapshot_date=datetime.now(),
                window_size=100,
                mean_r_multiple=0.8,
                win_rate=0.55,
                sharpe_ratio=1.2,
                pass_rate=0.75,
            )

            db.save_performance_snapshot(snapshot)

            # Retrieve snapshot
            history = db.get_performance_history("gate")
            assert len(history) == 1
            assert history[0].mean_r_multiple == 0.8
            assert history[0].win_rate == 0.55

            db.close()

    def test_save_graduation_record(self):
        """Test saving graduation record."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "agent_state.sqlite"
            db = AgentStateSQLite(db_path)

            record = GraduationRecordV1(
                agent_name="gate",
                evaluation_date=datetime.now(),
                passed=True,
                reason="All criteria met",
                metrics={"sharpe": 1.5, "win_rate": 0.6},
                promoted=True,
            )

            db.save_graduation_record(record)

            # Retrieve record
            history = db.get_graduation_history("gate")
            assert len(history) == 1
            assert history[0].passed is True
            assert history[0].promoted is True

            db.close()

    def test_hash_state(self):
        """Test state hashing."""
        state1 = np.array([1.0, 2.0, 3.0])
        state2 = np.array([1.0, 2.0, 3.0])
        state3 = np.array([1.0, 2.0, 4.0])

        hash1 = AgentStateSQLite.hash_state(state1)
        hash2 = AgentStateSQLite.hash_state(state2)
        hash3 = AgentStateSQLite.hash_state(state3)

        # Same state should have same hash
        assert hash1 == hash2
        # Different state should have different hash
        assert hash1 != hash3


class TestModelStore:
    """Test model store."""

    def test_create_model_store(self):
        """Test model store creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir) / "models"
            store = ModelStore(models_dir)

            assert models_dir.exists()

    def test_get_current_version_no_model(self):
        """Test getting current version when no model exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir) / "models"
            store = ModelStore(models_dir)

            version = store.get_current_version("gate")
            assert version is None

    def test_list_versions_empty(self):
        """Test listing versions when none exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir) / "models"
            store = ModelStore(models_dir)

            versions = store.list_versions("gate")
            assert versions == []


class TestStateEncoders:
    """Test state encoders."""

    def create_sample_candidate(self) -> CandidateRecordV1:
        """Create sample candidate for testing."""
        return CandidateRecordV1(
            candidate_id="cand_001",
            run_id="run_001",
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
                trailing_activation_price=45500.0,
                trailing_distance_atr=1.2,
            ),
            features={
                "close": 45000.0,
                "ret_1": 0.001,
                "ret_4": 0.005,
                "ret_16": 0.02,
                "ret_96": 0.1,
                "ema20_slope_bps": 5.0,
                "ema50_slope_bps": 3.0,
                "trend_dir": 1.0,
                "trend_strength": 0.7,
                "adx14": 25.0,
                "atr_bps": 100.0,
                "atr_z_96": 0.5,
                "realized_vol_96": 0.02,
                "bb_width_bps": 200.0,
                "bb_pos": 0.8,
                "vol_regime": 1.0,
                "rsi14": 65.0,
                "macd_hist": 50.0,
                "di_plus_14": 30.0,
                "di_minus_14": 15.0,
                "momentum_z": 1.5,
                "volume_ratio_96": 1.2,
                "vol_z_96": 0.8,
                "adv_usd": 1000000.0,
                "turnover_usd": 500000.0,
                "breakout_dist_atr": 0.5,
                "pullback_dist_ema20_atr": 0.0,
                "pullback_dist_ema50_atr": 0.0,
                "spread_bps": 10.0,
            },
            was_taken=False,
        )

    def test_gate_state_encoder_dimensions(self):
        """Test gate state encoder produces correct dimensions."""
        encoder = GateStateEncoder()
        assert encoder.get_state_dim() == 34

    def test_gate_state_encoder_encode(self):
        """Test gate state encoding."""
        encoder = GateStateEncoder()
        candidate = self.create_sample_candidate()
        portfolio_state = {
            "open_positions": 2,
            "exposure_frac": 0.5,
            "dd_24h_bps": -50.0,
            "halt_flag": 0,
        }

        state = encoder.encode(candidate, portfolio_state)

        assert state.shape == (34,)
        assert np.all(np.isfinite(state))
        # Check some specific values
        assert state[0] == 45000.0  # close
        assert state[25] == 0.0  # playbook_type (breakout=0)
        assert state[29] == 1.0  # direction (long=1)
        assert state[30] == 2.0  # open_positions

    def test_portfolio_state_encoder_dimensions(self):
        """Test portfolio state encoder produces correct dimensions."""
        encoder = PortfolioStateEncoder()
        assert encoder.get_state_dim() == 30

    def test_portfolio_state_encoder_encode(self):
        """Test portfolio state encoding."""
        encoder = PortfolioStateEncoder()
        candidate = self.create_sample_candidate()
        llm_response = {
            "decision": "take",
            "confidence": 0.9,
            "setup_quality": "A+",
            "risk_flags": ["high_volatility"],
        }
        portfolio_state = {
            "current_equity_usd": 10000.0,
            "open_positions": 1,
            "max_positions": 3,
            "exposure_frac": 0.3,
            "max_exposure_frac": 0.8,
            "dd_24h_bps": -30.0,
            "halt_flag": 0,
            "available_capacity": 0.5,
        }

        state = encoder.encode(candidate, llm_response, portfolio_state)

        assert state.shape == (30,)
        assert np.all(np.isfinite(state))
        # Check LLM encoding
        assert state[15] == 0.9  # llm_confidence
        assert state[16] == 3.0  # llm_setup_quality (A+=3)
        assert state[17] == 1.0  # llm_has_risk_flags

    def test_meta_learner_state_encoder_dimensions(self):
        """Test meta-learner state encoder produces correct dimensions."""
        encoder = MetaLearnerStateEncoder()
        assert encoder.get_state_dim() == 38

    def test_meta_learner_state_encoder_encode(self):
        """Test meta-learner state encoding."""
        encoder = MetaLearnerStateEncoder()
        candidate = self.create_sample_candidate()
        llm_response = {
            "decision": "take",
            "confidence": 0.85,
            "setup_quality": "A",
            "risk_flags": ["vol_spike", "low_liquidity"],
            "response_time_ms": 1500.0,
            "notes": "Strong breakout setup",
        }
        llm_history = {
            "llm_recent_accuracy": 0.75,
            "llm_recent_sharpe": 1.5,
            "playbook_llm_accuracy": 0.8,
            "symbol_llm_accuracy": 0.7,
            "market_regime": 1.0,
            "llm_streak": 3.0,
        }
        portfolio_state = {
            "open_positions": 2,
            "exposure_frac": 0.6,
            "dd_24h_bps": -40.0,
            "halt_flag": 0,
        }

        state = encoder.encode(candidate, llm_response, llm_history, portfolio_state)

        assert state.shape == (38,)
        assert np.all(np.isfinite(state))
        # Check LLM decision encoding
        assert state[20] == 1.0  # llm_decision (take=1)
        assert state[21] == 0.85  # llm_confidence
        assert state[22] == 2.0  # llm_setup_quality (A=2)
        assert state[23] == 2.0  # llm_risk_flags_count
        assert state[25] == 1.0  # llm_has_notes

    def test_state_encoder_handles_nan(self):
        """Test that encoders handle NaN values."""
        encoder = GateStateEncoder()
        candidate = self.create_sample_candidate()

        # Add NaN value to features
        candidate.features["close"] = float("nan")

        state = encoder.encode(candidate, {})

        # Should convert NaN to 0.0
        assert np.all(np.isfinite(state))
        assert state[0] == 0.0


class TestTrainingSchemas:
    """Test training episode schemas."""

    def test_training_episode_valid(self):
        """Test valid training episode."""
        episode = TrainingEpisodeV1(
            episode_id="ep_001",
            agent_name="gate",
            candidate_id="cand_001",
            state=[1.0, 2.0, 3.0],
            action=1.0,
            reward=0.5,
            next_state=[1.1, 2.1, 3.1],
            done=False,
            created_at=datetime.now(),
        )

        assert episode.episode_id == "ep_001"
        assert len(episode.state) == 3
        assert episode.done is False

        # Test conversion to numpy
        state_array = episode.get_state_array()
        assert isinstance(state_array, np.ndarray)
        assert state_array.shape == (3,)

    def test_training_batch_valid(self):
        """Test valid training batch."""
        batch = TrainingBatchV1(
            batch_id="batch_001",
            agent_name="gate",
            num_episodes=100,
            created_at=datetime.now(),
            run_ids_used=["run_001", "run_002"],
            train_split=0.8,
            validation_split=0.2,
            mean_reward=0.5,
            min_reward=-0.5,
            max_reward=2.0,
            std_reward=0.3,
        )

        assert batch.num_episodes == 100
        assert len(batch.run_ids_used) == 2

    def test_training_run_valid(self):
        """Test valid training run."""
        run = TrainingRunV1(
            training_run_id="train_001",
            agent_name="gate",
            started_at=datetime.now(),
            hyperparameters={"learning_rate": 3e-4, "gamma": 0.99},
            num_epochs=10,
            total_timesteps=10000,
        )

        assert run.training_run_id == "train_001"
        assert run.hyperparameters["learning_rate"] == 3e-4
        assert run.graduation_attempted is False
