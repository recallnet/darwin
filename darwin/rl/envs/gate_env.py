"""Gymnasium environment for Gate Agent.

The gate agent learns to filter candidates before sending to LLM.
- State: 34 features from candidate + portfolio context
- Action: Discrete(2) - 0=skip, 1=pass to LLM
- Reward: Based on counterfactual outcomes
"""

import logging
from typing import Any, Dict, Optional, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from darwin.rl.utils.reward_shaping import compute_gate_reward, normalize_reward
from darwin.rl.utils.state_encoding import GateStateEncoder
from darwin.schemas.candidate import CandidateRecordV1
from darwin.schemas.outcome_label import OutcomeLabelV1

logger = logging.getLogger(__name__)


class GateEnv(gym.Env):
    """Gymnasium environment for gate agent.

    The gate agent decides whether to pass a candidate to the LLM or skip it.

    State space: 34 features (from GateStateEncoder)
    Action space: Discrete(2) - 0=skip, 1=pass
    Reward: Based on counterfactual outcomes and cost savings
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        episodes: Optional[list] = None,
        cost_savings_bonus: float = 0.01,
        clip_rewards: bool = True,
        clip_range: float = 5.0,
    ):
        """Initialize gate environment.

        Args:
            episodes: List of (candidate, outcome_label, portfolio_state) tuples
            cost_savings_bonus: Bonus for skipping (default: 0.01)
            clip_rewards: Whether to clip rewards (default: True)
            clip_range: Clip range (default: 5.0)
        """
        super().__init__()

        # State encoder
        self.encoder = GateStateEncoder()
        self.state_dim = self.encoder.get_state_dim()

        # Action and observation spaces
        self.action_space = spaces.Discrete(2)  # 0=skip, 1=pass
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.state_dim,),
            dtype=np.float32,
        )

        # Episodes
        self.episodes = episodes or []
        self.current_episode_idx = 0

        # Reward configuration
        self.cost_savings_bonus = cost_savings_bonus
        self.clip_rewards = clip_rewards
        self.clip_range = clip_range

        # Current state
        self.current_candidate: Optional[CandidateRecordV1] = None
        self.current_outcome: Optional[OutcomeLabelV1] = None
        self.current_portfolio_state: Optional[Dict[str, Any]] = None

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reset environment to initial state.

        Args:
            seed: Random seed
            options: Additional options

        Returns:
            Tuple of (initial_observation, info)
        """
        super().reset(seed=seed)

        if not self.episodes:
            raise ValueError("No episodes loaded. Call set_episodes() first.")

        # Reset to first episode (or random if seed set)
        if seed is not None:
            self.current_episode_idx = self.np_random.integers(0, len(self.episodes))
        else:
            self.current_episode_idx = 0

        # Load episode
        episode = self.episodes[self.current_episode_idx]
        self.current_candidate = episode["candidate"]
        self.current_outcome = episode["outcome"]
        self.current_portfolio_state = episode.get("portfolio_state", {})

        # Encode state
        observation = self.encoder.encode(
            self.current_candidate,
            self.current_portfolio_state,
        )

        info = {
            "candidate_id": self.current_candidate.candidate_id,
            "episode_idx": self.current_episode_idx,
        }

        return observation, info

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """Execute one step in the environment.

        Args:
            action: Action to take (0=skip, 1=pass)

        Returns:
            Tuple of (observation, reward, terminated, truncated, info)
        """
        if self.current_candidate is None or self.current_outcome is None:
            raise ValueError("Environment not reset. Call reset() first.")

        # Compute reward based on action and outcome
        reward = self._compute_reward(action)

        # Gate environment is single-step per episode
        terminated = True
        truncated = False

        # Next observation (doesn't matter since terminated=True)
        observation = self.encoder.encode(
            self.current_candidate,
            self.current_portfolio_state or {},
        )

        # Info
        info = {
            "candidate_id": self.current_candidate.candidate_id,
            "action": "skip" if action == 0 else "pass",
            "reward": reward,
            "counterfactual_r_multiple": self.current_outcome.counterfactual_r_multiple,
            "was_taken": self.current_outcome.was_taken,
        }

        return observation, reward, terminated, truncated, info

    def _compute_reward(self, action: int) -> float:
        """Compute reward for action.

        Args:
            action: Action taken (0=skip, 1=pass)

        Returns:
            Reward value
        """
        # Get counterfactual outcome
        counterfactual_r = self.current_outcome.counterfactual_r_multiple
        was_taken = self.current_outcome.was_taken
        llm_decision = self.current_candidate.llm_decision

        # Compute reward
        if action == 0:  # SKIP
            # Use counterfactual R-multiple
            reward = compute_gate_reward(
                action=0,
                counterfactual_r_multiple=counterfactual_r,
                cost_savings_bonus=self.cost_savings_bonus,
            )
        else:  # PASS
            # If candidate was actually taken, use actual outcome
            if was_taken and self.current_outcome.actual_r_multiple is not None:
                reward = self.current_outcome.actual_r_multiple
            else:
                # LLM decided to skip
                reward = compute_gate_reward(
                    action=1,
                    llm_decision=llm_decision or "skip",
                )

        # Normalize/clip reward
        if self.clip_rewards:
            reward = normalize_reward(reward, clip=True, clip_range=self.clip_range)

        return float(reward)

    def set_episodes(self, episodes: list) -> None:
        """Set episodes for training.

        Args:
            episodes: List of episode dictionaries with keys:
                - candidate: CandidateRecordV1
                - outcome: OutcomeLabelV1
                - portfolio_state: Dict (optional)
        """
        self.episodes = episodes
        self.current_episode_idx = 0
        logger.info(f"Loaded {len(episodes)} episodes for gate environment")

    def get_episode_count(self) -> int:
        """Get number of episodes loaded."""
        return len(self.episodes)

    def render(self) -> None:
        """Render environment (not implemented)."""
        pass

    def close(self) -> None:
        """Close environment."""
        pass


class ReplayGateEnv(GateEnv):
    """Replay environment that cycles through episodes for offline training.

    This environment automatically cycles through all episodes in sequence,
    making it suitable for offline batch training.
    """

    def __init__(self, episodes: list, **kwargs):
        """Initialize replay environment.

        Args:
            episodes: List of episode dictionaries
            **kwargs: Additional arguments passed to GateEnv
        """
        super().__init__(episodes=episodes, **kwargs)
        self.episode_count = 0
        self.max_episodes = len(episodes)

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reset to next episode in sequence.

        Args:
            seed: Random seed (ignored for replay)
            options: Additional options

        Returns:
            Tuple of (initial_observation, info)
        """
        if not self.episodes:
            raise ValueError("No episodes loaded")

        # Cycle through episodes
        self.current_episode_idx = self.episode_count % self.max_episodes
        self.episode_count += 1

        # Load episode
        episode = self.episodes[self.current_episode_idx]
        self.current_candidate = episode["candidate"]
        self.current_outcome = episode["outcome"]
        self.current_portfolio_state = episode.get("portfolio_state", {})

        # Encode state
        observation = self.encoder.encode(
            self.current_candidate,
            self.current_portfolio_state,
        )

        info = {
            "candidate_id": self.current_candidate.candidate_id,
            "episode_idx": self.current_episode_idx,
            "total_episodes": self.max_episodes,
        }

        return observation, info
