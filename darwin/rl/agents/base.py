"""Base class for RL agents."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

import numpy as np

logger = logging.getLogger(__name__)


class RLAgent(ABC):
    """Base class for RL agents.

    All agents (Gate, Portfolio, Meta-Learner) inherit from this class.
    """

    def __init__(self, agent_name: str, model_path: str | None = None):
        """Initialize RL agent.

        Args:
            agent_name: Name of agent ("gate", "portfolio", "meta_learner")
            model_path: Path to trained model (optional)
        """
        self.agent_name = agent_name
        self.model_path = model_path
        self.model: Any | None = None

    @abstractmethod
    def predict(self, *args: Any, **kwargs: Any) -> Any:
        """Make prediction given inputs.

        Returns:
            Action or decision
        """
        raise NotImplementedError

    @abstractmethod
    def get_state_dim(self) -> int:
        """Get state dimension.

        Returns:
            State dimension
        """
        raise NotImplementedError

    @abstractmethod
    def get_action_space(self) -> str:
        """Get action space description.

        Returns:
            Action space description
        """
        raise NotImplementedError

    def load_model(self, model_path: str) -> None:
        """Load trained model from path.

        Args:
            model_path: Path to model file
        """
        from stable_baselines3 import PPO

        try:
            self.model = PPO.load(model_path)
            self.model_path = model_path
            logger.info(f"Loaded {self.agent_name} model from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load model from {model_path}: {e}")
            raise

    def is_loaded(self) -> bool:
        """Check if model is loaded.

        Returns:
            True if model is loaded
        """
        return self.model is not None
