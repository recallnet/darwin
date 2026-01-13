"""Unit tests for Portfolio Agent (Phase 4).

Tests:
- PortfolioEnv (Gymnasium environment)
- PortfolioAgent (wrapper)
- Episode preparation
"""

import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from darwin.rl.agents.portfolio_agent import PortfolioAgent
from darwin.rl.envs.portfolio_env import PortfolioEnv, ReplayPortfolioEnv
from darwin.schemas.candidate import CandidateRecordV1, ExitSpecV1, PlaybookType
from darwin.schemas.outcome_label import OutcomeLabelV1


class TestPortfolioEnv:
    """Test Portfolio Environment."""

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
            was_taken=True,
            llm_decision="take",
        )

        llm_response = {
            "decision": "take",
            "confidence": 0.75,
            "setup_quality": "high",
        }

        outcome = OutcomeLabelV1(
            label_id="label_001",
            candidate_id="cand_001",
            created_at=datetime.now(),
            was_taken=True,
            actual_r_multiple=1.5,  # Profitable trade
        )

        return {
            "candidate": candidate,
            "llm_response": llm_response,
            "outcome": outcome,
            "portfolio_state": {
                "open_positions": 1,
                "exposure_frac": 0.3,
                "dd_24h_bps": -20.0,
                "halt_flag": 0,
                "max_exposure_frac": 0.8,
            },
        }

    def test_portfolio_env_initialization(self):
        """Test portfolio environment initialization."""
        env = PortfolioEnv()

        assert env.action_space.shape == (1,)
        assert env.observation_space.shape == (30,)
        assert env.state_dim == 30

    def test_portfolio_env_reset(self):
        """Test environment reset."""
        episode = self.create_sample_episode()
        env = PortfolioEnv(episodes=[episode])

        obs, info = env.reset()

        assert obs.shape == (30,)
        assert np.all(np.isfinite(obs))
        assert "candidate_id" in info
        assert info["candidate_id"] == "cand_001"

    def test_portfolio_env_step_full_size(self):
        """Test environment step with full position size."""
        episode = self.create_sample_episode()
        env = PortfolioEnv(episodes=[episode])

        obs, info = env.reset()
        # Action: full size (1.0)
        action = np.array([1.0], dtype=np.float32)
        obs, reward, terminated, truncated, info = env.step(action)

        # Should get positive reward for profitable trade
        assert reward > 0
        assert terminated is True
        assert truncated is False
        assert info["position_size_fraction"] == 1.0
        assert info["actual_r_multiple"] == 1.5

    def test_portfolio_env_step_half_size(self):
        """Test environment step with half position size."""
        episode = self.create_sample_episode()
        env = PortfolioEnv(episodes=[episode])

        obs, info = env.reset()
        # Action: half size (0.5)
        action = np.array([0.5], dtype=np.float32)
        obs, reward, terminated, truncated, info = env.step(action)

        # Should get positive reward but less than full size
        assert reward > 0
        assert terminated is True
        assert info["position_size_fraction"] == 0.5

    def test_portfolio_env_step_zero_size(self):
        """Test environment step with zero position size."""
        episode = self.create_sample_episode()
        env = PortfolioEnv(episodes=[episode])

        obs, info = env.reset()
        # Action: zero size (0.0)
        action = np.array([0.0], dtype=np.float32)
        obs, reward, terminated, truncated, info = env.step(action)

        # Should get zero reward (no position)
        assert reward == 0.0
        assert info["position_size_fraction"] == 0.0

    def test_portfolio_env_action_clipping(self):
        """Test action clipping to valid range."""
        episode = self.create_sample_episode()
        env = PortfolioEnv(episodes=[episode])

        obs, info = env.reset()

        # Test clipping above 1.0
        action = np.array([1.5], dtype=np.float32)
        obs, reward, terminated, truncated, info = env.step(action)
        assert info["position_size_fraction"] == 1.0

        # Reset for next test
        obs, info = env.reset()

        # Test clipping below 0.0
        action = np.array([-0.5], dtype=np.float32)
        obs, reward, terminated, truncated, info = env.step(action)
        assert info["position_size_fraction"] == 0.0

    def test_portfolio_env_set_episodes(self):
        """Test setting episodes."""
        env = PortfolioEnv()
        episodes = [self.create_sample_episode() for _ in range(5)]

        env.set_episodes(episodes)

        assert env.get_episode_count() == 5

    def test_replay_portfolio_env_cycles(self):
        """Test replay environment cycles through episodes."""
        episodes = [self.create_sample_episode() for _ in range(3)]

        # Modify candidate_ids to distinguish them
        for i, ep in enumerate(episodes):
            ep["candidate"].candidate_id = f"cand_{i:03d}"
            ep["outcome"].candidate_id = f"cand_{i:03d}"

        env = ReplayPortfolioEnv(episodes=episodes)

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


class TestPortfolioAgent:
    """Test Portfolio Agent wrapper."""

    def test_portfolio_agent_initialization(self):
        """Test portfolio agent initialization."""
        agent = PortfolioAgent()

        assert agent.agent_name == "portfolio"
        assert not agent.is_loaded()
        assert agent.get_state_dim() == 30
        assert "Box" in agent.get_action_space()

    def test_portfolio_agent_predict_without_model(self):
        """Test prediction fails without loaded model."""
        agent = PortfolioAgent()

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

    def test_portfolio_agent_explain_decision_without_model(self):
        """Test explain decision fails without loaded model."""
        agent = PortfolioAgent()

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


class TestPortfolioEpisodePreparation:
    """Test portfolio episode structure."""

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
            "portfolio_state": {
                "open_positions": 1,
                "exposure_frac": 0.3,
            },
        }

        # Verify structure
        assert "candidate" in episode
        assert "llm_response" in episode
        assert "outcome" in episode
        assert "portfolio_state" in episode
        assert isinstance(episode["candidate"], CandidateRecordV1)
        assert isinstance(episode["outcome"], OutcomeLabelV1)
