"""Unit tests for Gate Agent (Phase 2).

Tests:
- Reward shaping functions
- GateEnv (Gymnasium environment)
- GateAgent (wrapper)
- Episode preparation
"""

import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from darwin.rl.agents.gate_agent import GateAgent
from darwin.rl.envs.gate_env import GateEnv, ReplayGateEnv
from darwin.rl.utils.reward_shaping import (
    compute_gate_reward,
    compute_meta_learner_reward,
    compute_portfolio_reward,
    normalize_reward,
)
from darwin.schemas.candidate import CandidateRecordV1, ExitSpecV1, PlaybookType
from darwin.schemas.outcome_label import OutcomeLabelV1


class TestRewardShaping:
    """Test reward shaping functions."""

    def test_gate_reward_skip_loser(self):
        """Test gate reward for correctly skipping a loser."""
        reward = compute_gate_reward(
            action=0,  # SKIP
            counterfactual_r_multiple=-0.5,  # Would have lost
        )
        # Should get +0.1 for correct skip + 0.01 cost savings
        assert reward == pytest.approx(0.11, abs=0.01)

    def test_gate_reward_skip_winner(self):
        """Test gate reward for incorrectly skipping a winner."""
        reward = compute_gate_reward(
            action=0,  # SKIP
            counterfactual_r_multiple=1.5,  # Would have won
        )
        # Should get penalty of -1.5 + 0.01 cost savings
        assert reward == pytest.approx(-1.49, abs=0.01)

    def test_gate_reward_pass_llm_skip(self):
        """Test gate reward for passing but LLM skips."""
        reward = compute_gate_reward(
            action=1,  # PASS
            llm_decision="skip",
        )
        # Wasted LLM call
        assert reward == pytest.approx(-0.02, abs=0.01)

    def test_gate_reward_pass_llm_take(self):
        """Test gate reward for passing and LLM takes."""
        reward = compute_gate_reward(
            action=1,  # PASS
            llm_decision="take",
        )
        # Placeholder (actual outcome filled later)
        assert reward == 0.0

    def test_portfolio_reward_positive(self):
        """Test portfolio reward for profitable trade."""
        reward = compute_portfolio_reward(
            actual_r_multiple=1.5,
            position_size_fraction=0.5,
            portfolio_state={"exposure_frac": 0.3, "max_exposure_frac": 0.8},
        )
        # Should get base (1.5 * 0.5 = 0.75) + diversification bonus (0.05)
        assert reward > 0.7
        assert reward < 1.0

    def test_portfolio_reward_with_drawdown(self):
        """Test portfolio reward with drawdown penalty."""
        reward = compute_portfolio_reward(
            actual_r_multiple=0.5,
            position_size_fraction=1.0,
            portfolio_state={"exposure_frac": 0.9, "max_exposure_frac": 0.8},
            caused_drawdown=True,
        )
        # Should have drawdown penalty
        assert reward < 0.5

    def test_meta_learner_reward_agree_take(self):
        """Test meta-learner reward for agreeing with LLM take."""
        reward = compute_meta_learner_reward(
            action=0,  # AGREE
            llm_decision="take",
            actual_r_multiple=1.2,
        )
        assert reward == pytest.approx(1.2, abs=0.01)

    def test_meta_learner_reward_override_to_skip(self):
        """Test meta-learner reward for overriding take to skip."""
        reward = compute_meta_learner_reward(
            action=1,  # OVERRIDE_TO_SKIP
            llm_decision="take",
            counterfactual_r_multiple=-0.5,  # Saved from loss
        )
        # Should get +0.5 (saved) - 0.05 (override penalty)
        assert reward == pytest.approx(0.45, abs=0.01)

    def test_normalize_reward_clip(self):
        """Test reward normalization with clipping."""
        # Test clipping positive
        reward = normalize_reward(10.0, clip=True, clip_range=5.0)
        assert reward == 5.0

        # Test clipping negative
        reward = normalize_reward(-10.0, clip=True, clip_range=5.0)
        assert reward == -5.0

        # Test no clipping
        reward = normalize_reward(3.0, clip=True, clip_range=5.0)
        assert reward == 3.0


class TestGateEnv:
    """Test Gate Environment."""

    def create_sample_episode(self) -> dict:
        """Create sample episode for testing."""
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
            was_taken=False,
            llm_decision="skip",
        )

        outcome = OutcomeLabelV1(
            label_id="label_001",
            candidate_id="cand_001",
            created_at=datetime.now(),
            was_taken=False,
            counterfactual_r_multiple=-0.5,  # Would have lost
        )

        return {
            "candidate": candidate,
            "outcome": outcome,
            "portfolio_state": {
                "open_positions": 1,
                "exposure_frac": 0.3,
                "dd_24h_bps": -20.0,
                "halt_flag": 0,
            },
        }

    def test_gate_env_initialization(self):
        """Test gate environment initialization."""
        env = GateEnv()

        assert env.action_space.n == 2
        assert env.observation_space.shape == (34,)
        assert env.state_dim == 34

    def test_gate_env_reset(self):
        """Test environment reset."""
        episode = self.create_sample_episode()
        env = GateEnv(episodes=[episode])

        obs, info = env.reset()

        assert obs.shape == (34,)
        assert np.all(np.isfinite(obs))
        assert "candidate_id" in info
        assert info["candidate_id"] == "cand_001"

    def test_gate_env_step_skip_loser(self):
        """Test environment step with skip action on loser."""
        episode = self.create_sample_episode()
        env = GateEnv(episodes=[episode])

        obs, info = env.reset()
        obs, reward, terminated, truncated, info = env.step(action=0)  # SKIP

        # Should get positive reward for correctly skipping loser
        assert reward > 0
        assert terminated is True
        assert truncated is False
        assert info["action"] == "skip"

    def test_gate_env_step_pass(self):
        """Test environment step with pass action."""
        episode = self.create_sample_episode()
        env = GateEnv(episodes=[episode])

        obs, info = env.reset()
        obs, reward, terminated, truncated, info = env.step(action=1)  # PASS

        # LLM decided skip, so wasted call
        assert reward < 0
        assert terminated is True
        assert info["action"] == "pass"

    def test_gate_env_set_episodes(self):
        """Test setting episodes."""
        env = GateEnv()
        episodes = [self.create_sample_episode() for _ in range(5)]

        env.set_episodes(episodes)

        assert env.get_episode_count() == 5

    def test_replay_gate_env_cycles(self):
        """Test replay environment cycles through episodes."""
        episodes = [self.create_sample_episode() for _ in range(3)]

        # Modify candidate_ids to distinguish them
        for i, ep in enumerate(episodes):
            ep["candidate"].candidate_id = f"cand_{i:03d}"
            ep["outcome"].candidate_id = f"cand_{i:03d}"

        env = ReplayGateEnv(episodes=episodes)

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


class TestGateAgent:
    """Test Gate Agent wrapper."""

    def test_gate_agent_initialization(self):
        """Test gate agent initialization."""
        agent = GateAgent()

        assert agent.agent_name == "gate"
        assert not agent.is_loaded()
        assert agent.get_state_dim() == 34
        assert "Discrete(2)" in agent.get_action_space()

    def test_gate_agent_predict_without_model(self):
        """Test prediction fails without loaded model."""
        agent = GateAgent()

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
            was_taken=False,
        )

        with pytest.raises(ValueError, match="Model not loaded"):
            agent.predict(candidate)

    def test_gate_agent_explain_decision_without_model(self):
        """Test explain decision fails without loaded model."""
        agent = GateAgent()

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
            was_taken=False,
        )

        with pytest.raises(ValueError, match="Model not loaded"):
            agent.explain_decision(candidate)


class TestOfflineTrainingPreparation:
    """Test offline training data preparation."""

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
                was_taken=False,
            ),
            "outcome": OutcomeLabelV1(
                label_id="label_001",
                candidate_id="cand_001",
                created_at=datetime.now(),
                was_taken=False,
                counterfactual_r_multiple=-0.5,
            ),
            "portfolio_state": {
                "open_positions": 1,
                "exposure_frac": 0.3,
            },
        }

        # Verify structure
        assert "candidate" in episode
        assert "outcome" in episode
        assert "portfolio_state" in episode
        assert isinstance(episode["candidate"], CandidateRecordV1)
        assert isinstance(episode["outcome"], OutcomeLabelV1)
