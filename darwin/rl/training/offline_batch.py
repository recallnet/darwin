"""Offline batch training for RL agents from historical data."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv

from darwin.rl.envs.gate_env import ReplayGateEnv
from darwin.rl.schemas.training_episode import TrainingBatchV1, TrainingRunV1
from darwin.schemas.candidate import CandidateRecordV1
from darwin.schemas.outcome_label import OutcomeLabelV1
from darwin.storage.candidate_cache import CandidateCacheSQLite
from darwin.storage.outcome_labels import OutcomeLabelsSQLite

logger = logging.getLogger(__name__)


class OfflineBatchTrainer:
    """Train RL agents from historical candidate cache using offline batch learning."""

    def __init__(
        self,
        agent_name: str,
        env_class: type,
        candidate_cache: CandidateCacheSQLite,
        outcome_labels: OutcomeLabelsSQLite,
        hyperparameters: Optional[Dict[str, Any]] = None,
    ):
        """Initialize offline batch trainer.

        Args:
            agent_name: Name of agent ("gate", "portfolio", "meta_learner")
            env_class: Environment class (e.g., ReplayGateEnv)
            candidate_cache: Candidate cache instance
            outcome_labels: Outcome labels instance
            hyperparameters: PPO hyperparameters (optional)
        """
        self.agent_name = agent_name
        self.env_class = env_class
        self.candidate_cache = candidate_cache
        self.outcome_labels = outcome_labels

        # Default PPO hyperparameters
        self.hyperparameters = hyperparameters or {
            "learning_rate": 3e-4,
            "n_steps": 2048,
            "batch_size": 64,
            "n_epochs": 10,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "clip_range": 0.2,
            "ent_coef": 0.01,
            "vf_coef": 0.5,
            "max_grad_norm": 0.5,
        }

        logger.info(
            f"Initialized offline batch trainer for {agent_name} agent "
            f"with hyperparameters: {self.hyperparameters}"
        )

    def prepare_episodes(
        self,
        run_ids: List[str],
        train_split: float = 0.8,
        min_samples: int = 100,
    ) -> Tuple[List[Dict], List[Dict]]:
        """Load and prepare episodes from historical data.

        Args:
            run_ids: List of run IDs to load data from
            train_split: Fraction of data for training (default: 0.8)
            min_samples: Minimum samples required (default: 100)

        Returns:
            Tuple of (train_episodes, val_episodes)

        Raises:
            ValueError: If insufficient samples
        """
        logger.info(f"Loading candidates from {len(run_ids)} runs...")

        # Load candidates with outcome labels
        episodes = []
        for run_id in run_ids:
            candidates = self.candidate_cache.query(run_id=run_id)

            for candidate in candidates:
                # Get outcome label
                label = self.outcome_labels.get_label(candidate.candidate_id)

                if label is None:
                    # Skip candidates without outcome labels
                    continue

                # Create episode
                episode = {
                    "candidate": candidate,
                    "outcome": label,
                    "portfolio_state": self._extract_portfolio_state(candidate),
                }
                episodes.append(episode)

        logger.info(f"Loaded {len(episodes)} episodes with outcome labels")

        # Check minimum samples
        if len(episodes) < min_samples:
            raise ValueError(
                f"Insufficient samples: {len(episodes)} < {min_samples}. "
                f"Run more experiments to collect training data."
            )

        # Split train/val
        split_idx = int(len(episodes) * train_split)
        train_episodes = episodes[:split_idx]
        val_episodes = episodes[split_idx:]

        logger.info(
            f"Split data: {len(train_episodes)} training, "
            f"{len(val_episodes)} validation"
        )

        return train_episodes, val_episodes

    def _extract_portfolio_state(self, candidate: CandidateRecordV1) -> Dict[str, Any]:
        """Extract portfolio state from candidate features.

        Args:
            candidate: Candidate record

        Returns:
            Portfolio state dictionary
        """
        features = candidate.features
        return {
            "open_positions": features.get("open_positions", 0),
            "exposure_frac": features.get("exposure_frac", 0.0),
            "dd_24h_bps": features.get("dd_24h_bps", 0.0),
            "halt_flag": features.get("halt_flag", 0),
        }

    def train(
        self,
        train_episodes: List[Dict],
        val_episodes: List[Dict],
        total_timesteps: int = 10000,
        tensorboard_log: Optional[str] = None,
        verbose: int = 1,
    ) -> PPO:
        """Train PPO agent on offline data.

        Args:
            train_episodes: Training episodes
            val_episodes: Validation episodes
            total_timesteps: Total training timesteps (default: 10000)
            tensorboard_log: Tensorboard log directory (optional)
            verbose: Verbosity level (default: 1)

        Returns:
            Trained PPO model
        """
        logger.info(f"Starting training for {self.agent_name} agent...")
        logger.info(f"Training episodes: {len(train_episodes)}")
        logger.info(f"Validation episodes: {len(val_episodes)}")
        logger.info(f"Total timesteps: {total_timesteps}")

        # Create vectorized environment
        def make_env():
            env = self.env_class(episodes=train_episodes)
            return env

        env = DummyVecEnv([make_env])

        # Initialize PPO
        model = PPO(
            policy="MlpPolicy",
            env=env,
            learning_rate=self.hyperparameters["learning_rate"],
            n_steps=self.hyperparameters["n_steps"],
            batch_size=self.hyperparameters["batch_size"],
            n_epochs=self.hyperparameters["n_epochs"],
            gamma=self.hyperparameters["gamma"],
            gae_lambda=self.hyperparameters["gae_lambda"],
            clip_range=self.hyperparameters["clip_range"],
            ent_coef=self.hyperparameters["ent_coef"],
            vf_coef=self.hyperparameters["vf_coef"],
            max_grad_norm=self.hyperparameters["max_grad_norm"],
            verbose=verbose,
            tensorboard_log=tensorboard_log,
        )

        logger.info("Training PPO model...")
        model.learn(total_timesteps=total_timesteps)

        # Evaluate on validation set
        logger.info("Evaluating on validation set...")
        val_metrics = self.evaluate(model, val_episodes)

        logger.info(f"Validation metrics: {val_metrics}")
        logger.info("Training complete!")

        return model

    def evaluate(
        self,
        model: PPO,
        episodes: List[Dict],
        n_eval_episodes: Optional[int] = None,
    ) -> Dict[str, float]:
        """Evaluate model on episodes.

        Args:
            model: Trained PPO model
            episodes: Episodes to evaluate on
            n_eval_episodes: Number of episodes to evaluate (default: all)

        Returns:
            Dictionary of evaluation metrics
        """
        if n_eval_episodes is None:
            n_eval_episodes = len(episodes)
        else:
            n_eval_episodes = min(n_eval_episodes, len(episodes))

        # Create evaluation environment
        eval_env = self.env_class(episodes=episodes[:n_eval_episodes])

        # Collect episode rewards
        rewards = []
        for _ in range(n_eval_episodes):
            obs, _ = eval_env.reset()
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, done, truncated, info = eval_env.step(action)
            rewards.append(reward)

        # Compute metrics
        metrics = {
            "mean_reward": float(np.mean(rewards)),
            "std_reward": float(np.std(rewards)),
            "min_reward": float(np.min(rewards)),
            "max_reward": float(np.max(rewards)),
            "n_episodes": n_eval_episodes,
        }

        return metrics

    def create_training_batch_record(
        self,
        run_ids: List[str],
        num_train: int,
        num_val: int,
        train_split: float,
        mean_reward: float,
        min_reward: float,
        max_reward: float,
        std_reward: float,
    ) -> TrainingBatchV1:
        """Create training batch record.

        Args:
            run_ids: Run IDs used for training
            num_train: Number of training episodes
            num_val: Number of validation episodes
            train_split: Train/val split ratio
            mean_reward: Mean reward
            min_reward: Min reward
            max_reward: Max reward
            std_reward: Std reward

        Returns:
            TrainingBatchV1 record
        """
        return TrainingBatchV1(
            batch_id=f"batch_{self.agent_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            agent_name=self.agent_name,
            num_episodes=num_train + num_val,
            created_at=datetime.now(),
            run_ids_used=run_ids,
            train_split=train_split,
            validation_split=1.0 - train_split,
            mean_reward=mean_reward,
            min_reward=min_reward,
            max_reward=max_reward,
            std_reward=std_reward,
        )

    def create_training_run_record(
        self,
        started_at: datetime,
        completed_at: datetime,
        num_epochs: int,
        total_timesteps: int,
        model_path: str,
        val_metrics: Dict[str, float],
    ) -> TrainingRunV1:
        """Create training run record.

        Args:
            started_at: Training start time
            completed_at: Training completion time
            num_epochs: Number of epochs
            total_timesteps: Total timesteps
            model_path: Path to saved model
            val_metrics: Validation metrics

        Returns:
            TrainingRunV1 record
        """
        return TrainingRunV1(
            training_run_id=f"train_{self.agent_name}_{started_at.strftime('%Y%m%d_%H%M%S')}",
            agent_name=self.agent_name,
            started_at=started_at,
            completed_at=completed_at,
            hyperparameters=self.hyperparameters,
            num_epochs=num_epochs,
            total_timesteps=total_timesteps,
            final_model_path=model_path,
            final_val_reward=val_metrics.get("mean_reward"),
            val_metrics=val_metrics,
        )


def train_gate_agent(
    run_ids: List[str],
    candidate_cache_path: str,
    outcome_labels_path: str,
    output_model_path: str,
    total_timesteps: int = 10000,
    tensorboard_log: Optional[str] = None,
) -> Tuple[PPO, Dict[str, float]]:
    """Convenience function to train gate agent.

    Args:
        run_ids: List of run IDs to train on
        candidate_cache_path: Path to candidate cache SQLite DB
        outcome_labels_path: Path to outcome labels SQLite DB
        output_model_path: Path to save trained model
        total_timesteps: Total training timesteps (default: 10000)
        tensorboard_log: Tensorboard log directory (optional)

    Returns:
        Tuple of (trained_model, validation_metrics)
    """
    # Initialize storage
    candidate_cache = CandidateCacheSQLite(candidate_cache_path)
    outcome_labels = OutcomeLabelsSQLite(outcome_labels_path)

    # Initialize trainer
    trainer = OfflineBatchTrainer(
        agent_name="gate",
        env_class=ReplayGateEnv,
        candidate_cache=candidate_cache,
        outcome_labels=outcome_labels,
    )

    # Prepare data
    train_episodes, val_episodes = trainer.prepare_episodes(run_ids)

    # Train
    model = trainer.train(
        train_episodes=train_episodes,
        val_episodes=val_episodes,
        total_timesteps=total_timesteps,
        tensorboard_log=tensorboard_log,
    )

    # Evaluate
    val_metrics = trainer.evaluate(model, val_episodes)

    # Save model
    model.save(output_model_path)
    logger.info(f"Saved trained model to {output_model_path}")

    # Close storage
    candidate_cache.close()
    outcome_labels.close()

    return model, val_metrics
