"""Gymnasium environments for PPO training.

These environments replay historical decisions for offline RL training.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

logger = logging.getLogger(__name__)


class ReplayEnvironment(gym.Env):
    """Base environment that replays historical decisions for offline RL.

    This environment doesn't simulate a real environment - instead it replays
    historical data (state, action, reward) tuples from past backtests.
    PPO learns from this data by treating each historical decision as a step.
    """

    def __init__(
        self,
        decisions: List[Dict[str, Any]],
        observation_space: spaces.Space,
        action_space: spaces.Space,
        agent_name: str,
    ):
        """Initialize replay environment.

        Args:
            decisions: List of historical decisions with outcomes
            observation_space: Gym observation space
            action_space: Gym action space
            agent_name: Name of agent ("gate", "portfolio", "meta_learner")
        """
        super().__init__()

        self.agent_name = agent_name
        self.decisions = decisions
        self.observation_space = observation_space
        self.action_space = action_space

        # Current episode state
        self.current_idx = 0
        self.episode_decisions: List[Dict[str, Any]] = []
        self.max_episode_length = 100  # Max decisions per episode

        logger.info(
            f"Initialized {agent_name} replay environment with {len(decisions)} decisions"
        )

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reset environment for new episode.

        Returns:
            observation: Initial state
            info: Additional info dict
        """
        super().reset(seed=seed)

        # Shuffle decisions at start of new episode
        if self.current_idx >= len(self.decisions):
            self.current_idx = 0
            np.random.shuffle(self.decisions)

        # Get first observation
        decision = self.decisions[self.current_idx]
        observation = np.array(decision["state"], dtype=np.float32)

        info = {"decision_id": decision.get("candidate_id", "unknown")}

        return observation, info

    def step(
        self, action: Any
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """Execute one step in the environment.

        Args:
            action: Action taken by agent

        Returns:
            observation: Next state
            reward: Reward for this step
            terminated: Whether episode ended naturally
            truncated: Whether episode was cut off
            info: Additional info
        """
        if self.current_idx >= len(self.decisions):
            # Episode finished
            terminated = True
            truncated = False
            reward = 0.0
            observation = self.observation_space.sample()  # Dummy obs
            info = {"episode_end": True}
            return observation, reward, terminated, truncated, info

        # Get current decision
        decision = self.decisions[self.current_idx]

        # Calculate reward based on outcome
        reward = self._calculate_reward(decision, action)

        # Move to next decision
        self.current_idx += 1

        # Check if episode should end
        episode_length = len(self.episode_decisions)
        terminated = (
            self.current_idx >= len(self.decisions)
            or episode_length >= self.max_episode_length
        )
        truncated = False

        # Get next observation
        if not terminated and self.current_idx < len(self.decisions):
            next_decision = self.decisions[self.current_idx]
            observation = np.array(next_decision["state"], dtype=np.float32)
        else:
            observation = self.observation_space.sample()  # Dummy for terminal state

        info = {
            "r_multiple": decision.get("r_multiple"),
            "action_taken": action,
        }

        return observation, reward, terminated, truncated, info

    def _calculate_reward(self, decision: Dict[str, Any], action: Any) -> float:
        """Calculate reward for a decision.

        Override in subclasses for agent-specific reward functions.

        Args:
            decision: Historical decision with outcome
            action: Action taken by agent

        Returns:
            Reward value
        """
        raise NotImplementedError


class GateAgentEnvironment(ReplayEnvironment):
    """Environment for training Gate Agent (binary classification)."""

    def __init__(self, decisions: List[Dict[str, Any]]):
        """Initialize gate agent environment.

        Args:
            decisions: Historical decisions with outcomes
        """
        # Gate agent: 34-dim state, binary action (skip=0, pass=1)
        observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(34,), dtype=np.float32
        )
        action_space = spaces.Discrete(2)

        super().__init__(
            decisions=decisions,
            observation_space=observation_space,
            action_space=action_space,
            agent_name="gate",
        )

    def _calculate_reward(self, decision: Dict[str, Any], action: int) -> float:
        """Calculate reward for gate decision.

        Reward structure:
        - Pass (action=1) on profitable candidate: +R (actual return)
        - Pass (action=1) on losing candidate: -|R| (actual loss)
        - Skip (action=0) on profitable candidate: -0.5 (missed opportunity)
        - Skip (action=0) on losing candidate: +0.1 (avoided loss)

        Args:
            decision: Historical decision
            action: Action taken (0=skip, 1=pass)

        Returns:
            Reward
        """
        r_multiple = decision.get("r_multiple", 0.0)

        if action == 1:  # PASS
            # Reward is the actual outcome (positive for wins, negative for losses)
            reward = float(r_multiple)
        else:  # SKIP (action == 0)
            if r_multiple > 0:
                # Skipped a winner - penalize (missed opportunity)
                reward = -0.5
            else:
                # Skipped a loser - small reward (saved from loss)
                reward = 0.1

        return reward


class PortfolioAgentEnvironment(ReplayEnvironment):
    """Environment for training Portfolio Agent (continuous position sizing)."""

    def __init__(self, decisions: List[Dict[str, Any]]):
        """Initialize portfolio agent environment.

        Args:
            decisions: Historical decisions with outcomes
        """
        # Portfolio agent: 30-dim state, continuous action [0, 1]
        observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(30,), dtype=np.float32
        )
        action_space = spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32)

        super().__init__(
            decisions=decisions,
            observation_space=observation_space,
            action_space=action_space,
            agent_name="portfolio",
        )

    def _calculate_reward(self, decision: Dict[str, Any], action: np.ndarray) -> float:
        """Calculate reward for position sizing decision.

        Reward structure:
        - Reward = position_size * R_multiple
        - Encourages larger sizes on winners, smaller sizes on losers
        - Penalizes over-sizing losers and under-sizing winners

        Args:
            decision: Historical decision
            action: Position size fraction [0, 1]

        Returns:
            Reward
        """
        r_multiple = decision.get("r_multiple", 0.0)
        position_size = float(action[0])  # Extract from array

        # Clip to valid range
        position_size = np.clip(position_size, 0.0, 1.0)

        # Reward is scaled by position size
        # Large size on winner = good, large size on loser = bad
        reward = position_size * r_multiple

        # Add small penalty for extreme sizes to encourage diversification
        if position_size > 0.9:
            reward -= 0.1  # Penalize over-concentration

        return float(reward)


class MetaLearnerAgentEnvironment(ReplayEnvironment):
    """Environment for training Meta-Learner Agent (LLM override decisions)."""

    def __init__(self, decisions: List[Dict[str, Any]]):
        """Initialize meta-learner agent environment.

        Args:
            decisions: Historical decisions with outcomes
        """
        # Meta-learner: 38-dim state, 3 discrete actions
        observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(38,), dtype=np.float32
        )
        action_space = spaces.Discrete(3)  # 0=agree, 1=override_skip, 2=override_take

        super().__init__(
            decisions=decisions,
            observation_space=observation_space,
            action_space=action_space,
            agent_name="meta_learner",
        )

    def _calculate_reward(self, decision: Dict[str, Any], action: int) -> float:
        """Calculate reward for meta-learner decision.

        Reward structure:
        - Agree (0) with LLM: Small penalty (-0.1) to encourage learning overrides
        - Override to skip (1): +0.5 if outcome was loss, -R if outcome was win
        - Override to take (2): +R if outcome was win, -0.5 if outcome was loss

        Args:
            decision: Historical decision
            action: Action taken (0=agree, 1=override_skip, 2=override_take)

        Returns:
            Reward
        """
        r_multiple = decision.get("r_multiple", 0.0)

        if action == 0:  # AGREE with LLM
            # Small penalty to encourage agent to learn when to override
            # But not too negative or it will always override
            reward = -0.1

        elif action == 1:  # OVERRIDE_TO_SKIP
            if r_multiple < 0:
                # Correctly skipped a loser
                reward = 0.5
            else:
                # Incorrectly skipped a winner
                reward = -abs(r_multiple)

        else:  # action == 2, OVERRIDE_TO_TAKE
            if r_multiple > 0:
                # Correctly took a winner
                reward = r_multiple
            else:
                # Incorrectly took a loser
                reward = -0.5

        return reward


def create_environment(
    agent_name: str, decisions: List[Dict[str, Any]]
) -> ReplayEnvironment:
    """Factory function to create environment for agent.

    Args:
        agent_name: Agent name ("gate", "portfolio", "meta_learner")
        decisions: Historical decisions with outcomes

    Returns:
        Replay environment

    Raises:
        ValueError: If agent_name is unknown
    """
    if agent_name == "gate":
        return GateAgentEnvironment(decisions)
    elif agent_name == "portfolio":
        return PortfolioAgentEnvironment(decisions)
    elif agent_name == "meta_learner":
        return MetaLearnerAgentEnvironment(decisions)
    else:
        raise ValueError(f"Unknown agent name: {agent_name}")
