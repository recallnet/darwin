"""Training episode schemas for RL agents."""

from datetime import datetime
from typing import Any, Dict

import numpy as np
from pydantic import BaseModel


class TrainingEpisodeV1(BaseModel):
    """Single training episode (state, action, reward, next_state, done)."""

    episode_id: str
    agent_name: str
    candidate_id: str

    # Episode data
    state: list[float]  # Flattened state vector
    action: float  # int for discrete, float for continuous
    reward: float
    next_state: list[float] | None  # None for terminal states
    done: bool

    # Metadata
    created_at: datetime

    class Config:
        """Pydantic config."""

        # Allow numpy arrays to be converted
        arbitrary_types_allowed = True

    def get_state_array(self) -> np.ndarray:
        """Convert state list to numpy array."""
        return np.array(self.state, dtype=np.float32)

    def get_next_state_array(self) -> np.ndarray | None:
        """Convert next_state list to numpy array."""
        if self.next_state is None:
            return None
        return np.array(self.next_state, dtype=np.float32)


class TrainingBatchV1(BaseModel):
    """Batch of training episodes."""

    batch_id: str
    agent_name: str
    num_episodes: int
    created_at: datetime

    # Training metadata
    run_ids_used: list[str]
    train_split: float
    validation_split: float

    # Performance metrics
    mean_reward: float
    min_reward: float
    max_reward: float
    std_reward: float


class TrainingRunV1(BaseModel):
    """Complete training run with hyperparameters and results."""

    training_run_id: str
    agent_name: str
    started_at: datetime
    completed_at: datetime | None = None

    # Hyperparameters
    hyperparameters: Dict[str, Any]

    # Training progress
    num_epochs: int
    total_timesteps: int
    final_model_path: str | None = None

    # Performance metrics
    final_train_reward: float | None = None
    final_val_reward: float | None = None
    val_metrics: Dict[str, float] | None = None

    # Graduation attempt
    graduation_attempted: bool = False
    graduation_passed: bool = False
