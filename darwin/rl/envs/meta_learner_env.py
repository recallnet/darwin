"""Meta-learner agent Gymnasium environment."""

import logging
from typing import Any, Dict, Optional, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from darwin.rl.utils.reward_shaping import compute_meta_learner_reward
from darwin.rl.utils.state_encoding import MetaLearnerStateEncoder
from darwin.schemas.candidate import CandidateRecordV1

logger = logging.getLogger(__name__)


class MetaLearnerEnv(gym.Env):
    """Meta-learner agent environment for LLM decision override.

    State: 38 features (candidate + LLM context + LLM history)
    Action: Discrete(3) - 0=agree, 1=override_to_skip, 2=override_to_take
    Reward: Actual R-multiple if override improves outcome, penalty for disagreement
    """

    def __init__(self, episodes: Optional[list] = None):
        """Initialize meta-learner environment.

        Args:
            episodes: List of episodes to cycle through. Each episode contains:
                - candidate: CandidateRecordV1
                - llm_response: LLM decision context
                - outcome: OutcomeLabelV1 with actual R-multiple
                - llm_history: Rolling LLM performance metrics
                - portfolio_state: Current portfolio state dict
        """
        super().__init__()

        self.encoder = MetaLearnerStateEncoder()

        # Action space: Discrete(3)
        # 0 = AGREE (follow LLM)
        # 1 = OVERRIDE_TO_SKIP (override LLM "take" to "skip")
        # 2 = OVERRIDE_TO_TAKE (override LLM "skip" to "take")
        self.action_space = spaces.Discrete(3)

        # Observation space: 38 features
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
        llm_history = self.current_episode.get("llm_history", {})
        portfolio_state = self.current_episode.get("portfolio_state", {})

        # Encode state
        obs = self.encoder.encode(candidate, llm_response, llm_history, portfolio_state)

        info = {
            "candidate_id": candidate.candidate_id,
            "run_id": candidate.run_id,
            "episode_idx": self.current_episode_idx,
            "llm_decision": llm_response.get("decision", "skip"),
        }

        return obs, info

    def step(
        self, action: int
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """Execute one step in the environment.

        Args:
            action: Meta-learner action (0=agree, 1=override_to_skip, 2=override_to_take)

        Returns:
            Tuple of (observation, reward, terminated, truncated, info)
        """
        if self.current_episode is None:
            raise ValueError("Must call reset() before step()")

        # Get episode data
        outcome = self.current_episode["outcome"]
        llm_response = self.current_episode.get("llm_response", {})
        llm_decision = llm_response.get("decision", "skip")

        # Compute reward
        reward = self._compute_reward(action, llm_decision, outcome)

        # Episode terminates after one decision
        terminated = True
        truncated = False

        # Return same observation (episode ends)
        candidate = self.current_episode["candidate"]
        llm_history = self.current_episode.get("llm_history", {})
        portfolio_state = self.current_episode.get("portfolio_state", {})
        obs = self.encoder.encode(candidate, llm_response, llm_history, portfolio_state)

        # Determine final decision after override
        if action == 0:  # AGREE
            final_decision = llm_decision
        elif action == 1:  # OVERRIDE_TO_SKIP
            final_decision = "skip"
        else:  # action == 2, OVERRIDE_TO_TAKE
            final_decision = "take"

        info = {
            "candidate_id": candidate.candidate_id,
            "action": action,
            "llm_decision": llm_decision,
            "final_decision": final_decision,
            "actual_r_multiple": outcome.actual_r_multiple,
            "reward": reward,
        }

        return obs, reward, terminated, truncated, info

    def _compute_reward(
        self,
        action: int,
        llm_decision: str,
        outcome: Any,
    ) -> float:
        """Compute reward for meta-learner decision.

        Args:
            action: Meta-learner action (0=agree, 1=override_to_skip, 2=override_to_take)
            llm_decision: LLM's decision ("skip" or "take")
            outcome: Outcome label with actual R-multiple

        Returns:
            Reward value
        """
        # Get actual R-multiple
        actual_r_multiple = outcome.actual_r_multiple
        if actual_r_multiple is None:
            # No outcome yet, return 0
            return 0.0

        # Compute counterfactual: what would have happened if we followed LLM?
        if llm_decision == "take":
            counterfactual_r_multiple = actual_r_multiple
        else:
            counterfactual_r_multiple = None  # LLM skipped, no trade

        # Compute meta-learner reward
        reward = compute_meta_learner_reward(
            action=action,
            llm_decision=llm_decision,
            actual_r_multiple=actual_r_multiple,
            counterfactual_r_multiple=counterfactual_r_multiple,
        )

        return reward


class ReplayMetaLearnerEnv(MetaLearnerEnv):
    """Meta-learner environment that cycles through episodes for offline training."""

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
