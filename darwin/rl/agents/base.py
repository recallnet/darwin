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
        """Load trained PPO model from path.

        Args:
            model_path: Path to model file (.zip)
        """
        try:
            from pathlib import Path
            from stable_baselines3 import PPO

            model_file = Path(model_path)
            if not model_file.exists():
                raise FileNotFoundError(f"Model file not found: {model_path}")

            # Load PPO model
            self.model = PPO.load(str(model_file))
            self.model_path = model_path

            logger.info(f"Loaded {self.agent_name} PPO model from {model_path}")

        except ImportError as e:
            logger.error(f"stable-baselines3 not available: {e}")
            logger.error("Install with: pip install 'darwin[rl]'")
            raise
        except Exception as e:
            logger.error(f"Failed to load model from {model_path}: {e}")
            raise

    def is_loaded(self) -> bool:
        """Check if model is loaded.

        Returns:
            True if model is loaded
        """
        return self.model is not None
