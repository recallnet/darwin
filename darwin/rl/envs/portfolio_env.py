"""Portfolio agent Gymnasium environment."""

import logging
from typing import Any, Dict, Optional, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from darwin.rl.utils.reward_shaping import compute_portfolio_reward
from darwin.rl.utils.state_encoding import PortfolioStateEncoder
from darwin.schemas.candidate import CandidateRecordV1

logger = logging.getLogger(__name__)


class PortfolioEnv(gym.Env):
    """Portfolio agent environment for position sizing decisions.

    State: 30 features (candidate + LLM context + portfolio state)
    Action: Continuous[0,1] - position size fraction
    Reward: R-multiple with portfolio adjustments
    """

    def __init__(self, episodes: Optional[list] = None):
        """Initialize portfolio environment.

        Args:
            episodes: List of episodes to cycle through. Each episode contains:
                - candidate: CandidateRecordV1
                - llm_response: LLM decision context
                - outcome: OutcomeLabelV1 with actual R-multiple
                - portfolio_state: Current portfolio state dict
        """
        super().__init__()

        self.encoder = PortfolioStateEncoder()

        # Action space: Continuous[0, 1] for position size fraction
        self.action_space = spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32)

        # Observation space: 30 features
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(self.encoder.state_dim,), dtype=np.float32
        )

        # Episodes
        self.episodes = episodes or []
        self.current_episode_idx = 0
        self.current_episode: Optional[Dict[str, Any]] = None

    @property
    def state_dim(self) -> int:
        """Get state dimension."""
        return self.encoder.state_dim

    def set_episodes(self, episodes: list) -> None:
        """Set episodes for the environment.

        Args:
            episodes: List of episodes
        """
        self.episodes = episodes
        self.current_episode_idx = 0

    def get_episode_count(self) -> int:
        """Get number of episodes.

        Returns:
            Number of episodes
        """
        return len(self.episodes)

    def reset(
        self, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reset environment to start of an episode.

        Args:
            seed: Random seed
            options: Optional reset options

        Returns:
            Tuple of (observation, info)
        """
        super().reset(seed=seed)

        if not self.episodes:
            raise ValueError("No episodes available. Call set_episodes() first.")

        # Get current episode
        self.current_episode = self.episodes[self.current_episode_idx]

        # Extract components
        candidate = self.current_episode["candidate"]
        llm_response = self.current_episode.get("llm_response", {})
        portfolio_state = self.current_episode.get("portfolio_state", {})

        # Encode state
        obs = self.encoder.encode(candidate, llm_response, portfolio_state)

        info = {
            "candidate_id": candidate.candidate_id,
            "run_id": candidate.run_id,
            "episode_idx": self.current_episode_idx,
        }

        return obs, info

    def step(
        self, action: np.ndarray
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """Execute one step in the environment.

        Args:
            action: Position size fraction [0, 1]

        Returns:
            Tuple of (observation, reward, terminated, truncated, info)
        """
        if self.current_episode is None:
            raise ValueError("Must call reset() before step()")

        # Extract action (clip to valid range)
        position_size_fraction = float(np.clip(action[0], 0.0, 1.0))

        # Get outcome
        outcome = self.current_episode["outcome"]
        portfolio_state = self.current_episode.get("portfolio_state", {})

        # Compute reward
        reward = self._compute_reward(position_size_fraction, outcome, portfolio_state)

        # Episode terminates after one decision
        terminated = True
        truncated = False

        # Return same observation (episode ends)
        candidate = self.current_episode["candidate"]
        llm_response = self.current_episode.get("llm_response", {})
        obs = self.encoder.encode(candidate, llm_response, portfolio_state)

        info = {
            "candidate_id": candidate.candidate_id,
            "position_size_fraction": position_size_fraction,
            "actual_r_multiple": outcome.actual_r_multiple,
            "reward": reward,
        }

        return obs, reward, terminated, truncated, info

    def _compute_reward(
        self,
        position_size_fraction: float,
        outcome: Any,
        portfolio_state: Dict[str, Any],
    ) -> float:
        """Compute reward for position sizing decision.

        Args:
            position_size_fraction: Position size chosen [0, 1]
            outcome: Outcome label with actual R-multiple
            portfolio_state: Current portfolio state

        Returns:
            Reward value
        """
        # Get actual R-multiple
        actual_r_multiple = outcome.actual_r_multiple
        if actual_r_multiple is None:
            # No outcome yet, return 0
            return 0.0

        # Check for drawdown
        dd_24h_bps = portfolio_state.get("dd_24h_bps", 0.0)
        caused_drawdown = dd_24h_bps < -500  # 5% drawdown threshold

        # Compute portfolio reward
        reward = compute_portfolio_reward(
            actual_r_multiple=actual_r_multiple,
            position_size_fraction=position_size_fraction,
            portfolio_state=portfolio_state,
            caused_drawdown=caused_drawdown,
        )

        return reward


class ReplayPortfolioEnv(PortfolioEnv):
    """Portfolio environment that cycles through episodes for offline training."""

    def reset(
        self, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reset and cycle to next episode.

        Args:
            seed: Random seed
            options: Optional reset options

        Returns:
            Tuple of (observation, info)
        """
        # Reset with current episode
        obs, info = super().reset(seed=seed, options=options)

        # Cycle to next episode for next reset
        if self.episodes:
            self.current_episode_idx = (self.current_episode_idx + 1) % len(self.episodes)

        return obs, info
