"""Unit tests for Meta-Learner Agent (Phase 5).

Tests:
- MetaLearnerEnv (Gymnasium environment)
- MetaLearnerAgent (wrapper)
- Episode preparation
"""

import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from darwin.rl.agents.meta_learner_agent import (
    AGREE,
    OVERRIDE_TO_SKIP,
    OVERRIDE_TO_TAKE,
    MetaLearnerAgent,
)
from darwin.rl.envs.meta_learner_env import MetaLearnerEnv, ReplayMetaLearnerEnv
from darwin.schemas.candidate import CandidateRecordV1, ExitSpecV1, PlaybookType
from darwin.schemas.outcome_label import OutcomeLabelV1


class TestMetaLearnerEnv:
    """Test Meta-Learner Environment."""

    def create_sample_episode(
        self, llm_decision: str = "take", actual_r: float = 1.5
    ) -> dict:
        """Create sample episode for testing.

        Args:
            llm_decision: LLM decision ("skip" or "take")
            actual_r: Actual R-multiple outcome

        Returns:
            Episode dictionary
        """
        candidate = CandidateRecordV1(
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
            ),
            features={
                "close": 45000.0,
                "atr_bps": 100.0,
                "rsi14": 65.0,
                "adx14": 25.0,
            },
            was_taken=True,
            llm_decision=llm_decision,
        )

        llm_response = {
            "decision": llm_decision,
            "confidence": 0.75,
            "setup_quality": "high",
        }

        outcome = OutcomeLabelV1(
            label_id="label_001",
            candidate_id="cand_001",
            created_at=datetime.now(),
            was_taken=(llm_decision == "take"),
            actual_r_multiple=actual_r,
        )

        llm_history = {
            "rolling_accuracy": 0.65,
            "rolling_sharpe": 1.2,
            "recent_trades": 50,
            "win_rate": 0.55,
        }

        portfolio_state = {
            "open_positions": 1,
            "exposure_frac": 0.3,
            "dd_24h_bps": -20.0,
            "halt_flag": 0,
        }

        return {
            "candidate": candidate,
            "llm_response": llm_response,
            "outcome": outcome,
            "llm_history": llm_history,
            "portfolio_state": portfolio_state,
        }

    def test_meta_learner_env_initialization(self):
        """Test meta-learner environment initialization."""
        env = MetaLearnerEnv()

        assert env.action_space.n == 3
        assert env.observation_space.shape == (38,)
        assert env.state_dim == 38

    def test_meta_learner_env_reset(self):
        """Test environment reset."""
        episode = self.create_sample_episode()
        env = MetaLearnerEnv(episodes=[episode])

        obs, info = env.reset()

        assert obs.shape == (38,)
        assert np.all(np.isfinite(obs))
        assert "candidate_id" in info
        assert info["candidate_id"] == "cand_001"
        assert info["llm_decision"] == "take"

    def test_meta_learner_env_step_agree_with_winner(self):
        """Test environment step: agree with LLM on winning trade."""
        episode = self.create_sample_episode(llm_decision="take", actual_r=1.5)
        env = MetaLearnerEnv(episodes=[episode])

        obs, info = env.reset()
        # Action: AGREE
        obs, reward, terminated, truncated, info = env.step(AGREE)

        # Should get positive reward for agreeing with profitable decision
        assert reward > 0
        assert terminated is True
        assert truncated is False
        assert info["action"] == AGREE
        assert info["llm_decision"] == "take"
        assert info["final_decision"] == "take"
        assert info["actual_r_multiple"] == 1.5

    def test_meta_learner_env_step_agree_with_loser(self):
        """Test environment step: agree with LLM on losing trade."""
        episode = self.create_sample_episode(llm_decision="take", actual_r=-1.0)
        env = MetaLearnerEnv(episodes=[episode])

        obs, info = env.reset()
        # Action: AGREE
        obs, reward, terminated, truncated, info = env.step(AGREE)

        # Should get negative reward for agreeing with losing decision
        assert reward < 0
        assert terminated is True
        assert info["final_decision"] == "take"

    def test_meta_learner_env_step_override_to_skip_loser(self):
        """Test environment step: override LLM 'take' to 'skip' on loser."""
        episode = self.create_sample_episode(llm_decision="take", actual_r=-1.0)
        env = MetaLearnerEnv(episodes=[episode])

        obs, info = env.reset()
        # Action: OVERRIDE_TO_SKIP
        obs, reward, terminated, truncated, info = env.step(OVERRIDE_TO_SKIP)

        # Should get positive reward for correctly overriding loser
        assert reward > 0
        assert info["action"] == OVERRIDE_TO_SKIP
        assert info["llm_decision"] == "take"
        assert info["final_decision"] == "skip"

    def test_meta_learner_env_step_override_to_skip_winner(self):
        """Test environment step: override LLM 'take' to 'skip' on winner."""
        episode = self.create_sample_episode(llm_decision="take", actual_r=1.5)
        env = MetaLearnerEnv(episodes=[episode])

        obs, info = env.reset()
        # Action: OVERRIDE_TO_SKIP
        obs, reward, terminated, truncated, info = env.step(OVERRIDE_TO_SKIP)

        # Should get penalty for incorrectly overriding winner
        assert reward < 0
        assert info["final_decision"] == "skip"

    def test_meta_learner_env_step_override_to_take_winner(self):
        """Test environment step: override LLM 'skip' to 'take' on winner."""
        episode = self.create_sample_episode(llm_decision="skip", actual_r=1.5)
        env = MetaLearnerEnv(episodes=[episode])

        obs, info = env.reset()
        # Action: OVERRIDE_TO_TAKE
        obs, reward, terminated, truncated, info = env.step(OVERRIDE_TO_TAKE)

        # Should get positive reward for correctly overriding to take winner
        assert reward > 0
        assert info["action"] == OVERRIDE_TO_TAKE
        assert info["llm_decision"] == "skip"
        assert info["final_decision"] == "take"

    def test_meta_learner_env_step_override_to_take_loser(self):
        """Test environment step: override LLM 'skip' to 'take' on loser."""
        episode = self.create_sample_episode(llm_decision="skip", actual_r=-1.0)
        env = MetaLearnerEnv(episodes=[episode])

        obs, info = env.reset()
        # Action: OVERRIDE_TO_TAKE
        obs, reward, terminated, truncated, info = env.step(OVERRIDE_TO_TAKE)

        # Should get penalty for incorrectly overriding to take loser
        assert reward < 0
        assert info["final_decision"] == "take"

    def test_meta_learner_env_set_episodes(self):
        """Test setting episodes."""
        env = MetaLearnerEnv()
        episodes = [self.create_sample_episode() for _ in range(5)]

        env.set_episodes(episodes)

        assert env.get_episode_count() == 5

    def test_replay_meta_learner_env_cycles(self):
        """Test replay environment cycles through episodes."""
        episodes = [
            self.create_sample_episode(llm_decision="take", actual_r=1.5),
            self.create_sample_episode(llm_decision="skip", actual_r=-1.0),
            self.create_sample_episode(llm_decision="take", actual_r=2.0),
        ]

        # Modify candidate_ids to distinguish them
        for i, ep in enumerate(episodes):
            ep["candidate"].candidate_id = f"cand_{i:03d}"
            ep["outcome"].candidate_id = f"cand_{i:03d}"

        env = ReplayMetaLearnerEnv(episodes=episodes)

        # Reset multiple times and verify cycling
        seen_ids = []
        for _ in range(6):  # 2 full cycles
            obs, info = env.reset()
            seen_ids.append(info["candidate_id"])

        # Should cycle through candidates
        assert seen_ids[0] == "cand_000"
        assert seen_ids[1] == "cand_001"
        assert seen_ids[2] == "cand_002"
        assert seen_ids[3] == "cand_000"  # Cycle back


class TestMetaLearnerAgent:
    """Test Meta-Learner Agent wrapper."""

    def test_meta_learner_agent_initialization(self):
        """Test meta-learner agent initialization."""
        agent = MetaLearnerAgent()

        assert agent.agent_name == "meta_learner"
        assert not agent.is_loaded()
        assert agent.get_state_dim() == 38
        assert "Discrete" in agent.get_action_space()

    def test_meta_learner_agent_predict_without_model(self):
        """Test prediction fails without loaded model."""
        agent = MetaLearnerAgent()

        candidate = CandidateRecordV1(
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
            ),
            features={"close": 45000.0},
            was_taken=True,
        )

        llm_response = {"decision": "take", "confidence": 0.75}

        with pytest.raises(ValueError, match="Model not loaded"):
            agent.predict(candidate, llm_response)

    def test_meta_learner_agent_should_override_without_model(self):
        """Test should_override fails without loaded model."""
        agent = MetaLearnerAgent()

        candidate = CandidateRecordV1(
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
            ),
            features={"close": 45000.0},
            was_taken=True,
        )

        llm_response = {"decision": "take", "confidence": 0.75}

        with pytest.raises(ValueError, match="Model not loaded"):
            agent.should_override(candidate, llm_response)

    def test_meta_learner_agent_explain_decision_without_model(self):
        """Test explain decision fails without loaded model."""
        agent = MetaLearnerAgent()

        candidate = CandidateRecordV1(
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
            ),
            features={"close": 45000.0},
            was_taken=True,
        )

        llm_response = {"decision": "take", "confidence": 0.75}

        with pytest.raises(ValueError, match="Model not loaded"):
            agent.explain_decision(candidate, llm_response)


class TestMetaLearnerEpisodePreparation:
    """Test meta-learner episode structure."""

    def test_episode_structure(self):
        """Test episode structure is correct."""
        episode = {
            "candidate": CandidateRecordV1(
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
                ),
                features={"close": 45000.0},
                was_taken=True,
            ),
            "llm_response": {
                "decision": "take",
                "confidence": 0.75,
            },
            "outcome": OutcomeLabelV1(
                label_id="label_001",
                candidate_id="cand_001",
                created_at=datetime.now(),
                was_taken=True,
                actual_r_multiple=1.5,
            ),
            "llm_history": {
                "rolling_accuracy": 0.65,
                "rolling_sharpe": 1.2,
            },
        }

        # Verify structure
        assert "candidate" in episode
        assert "llm_response" in episode
        assert "outcome" in episode
        assert "llm_history" in episode
        assert isinstance(episode["candidate"], CandidateRecordV1)
        assert isinstance(episode["outcome"], OutcomeLabelV1)
