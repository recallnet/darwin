"""RL training algorithms using PPO.

Implements PPO training for the three agent types using stable-baselines3.
"""

import logging
from pathlib import Path
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)

try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback, EvalCallback
    from stable_baselines3.common.monitor import Monitor

    from darwin.rl.training.environments import create_environment

    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False
    logger.warning(
        "stable-baselines3 not available. Install with: pip install 'darwin[rl]'"
    )


class ProgressCallback(BaseCallback):
    """Callback to log training progress."""

    def __init__(self, log_freq: int = 1000, verbose: int = 0):
        """Initialize progress callback.

        Args:
            log_freq: Log every N timesteps
            verbose: Verbosity level
        """
        super().__init__(verbose)
        self.log_freq = log_freq

    def _on_step(self) -> bool:
        """Called after each environment step.

        Returns:
            True to continue training
        """
        if self.n_calls % self.log_freq == 0:
            # Log progress
            if self.model.ep_info_buffer:
                try:
                    mean_reward = np.mean([ep["r"] for ep in self.model.ep_info_buffer if "r" in ep])
                except (KeyError, TypeError):
                    mean_reward = 0.0
            else:
                mean_reward = 0.0

            logger.info(f"  Step {self.n_calls}: mean_reward={mean_reward:.2f}")

        return True


class AgentTrainer:
    """PPO trainer for RL agents."""

    def __init__(
        self,
        agent_name: str,
        learning_rate: float = 3e-4,
        n_steps: int = 2048,
        batch_size: int = 64,
        n_epochs: int = 10,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_range: float = 0.2,
        ent_coef: float = 0.0,
        vf_coef: float = 0.5,
        max_grad_norm: float = 0.5,
        device: str = "cpu",
    ):
        """Initialize PPO trainer.

        Args:
            agent_name: Agent name ("gate", "portfolio", "meta_learner")
            learning_rate: Learning rate
            n_steps: Number of steps per rollout
            batch_size: Batch size for training
            n_epochs: Number of epochs per update
            gamma: Discount factor
            gae_lambda: GAE lambda
            clip_range: PPO clip range
            ent_coef: Entropy coefficient
            vf_coef: Value function coefficient
            max_grad_norm: Max gradient norm
            device: Device to use ("cpu" or "cuda")
        """
        if not SB3_AVAILABLE:
            raise RuntimeError(
                "stable-baselines3 not available. Install with: pip install 'darwin[rl]'"
            )

        self.agent_name = agent_name
        self.learning_rate = learning_rate
        self.n_steps = n_steps
        self.batch_size = batch_size
        self.n_epochs = n_epochs
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_range = clip_range
        self.ent_coef = ent_coef
        self.vf_coef = vf_coef
        self.max_grad_norm = max_grad_norm
        self.device = device

        logger.info(f"Initialized PPO trainer for {agent_name} agent")

    def train(
        self, decisions: List[Dict], total_timesteps: int = 100000,
        tensorboard_log: str = None
    ) -> Dict[str, float]:
        """Train agent using PPO.

        Args:
            decisions: List of historical decisions with outcomes
            total_timesteps: Total training timesteps
            tensorboard_log: Path to tensorboard log directory (optional)

        Returns:
            Training metrics
        """
        logger.info(f"Training {self.agent_name} agent with PPO...")
        logger.info(f"  Training samples: {len(decisions)}")
        logger.info(f"  Total timesteps: {total_timesteps}")
        if tensorboard_log:
            logger.info(f"  Tensorboard logs: {tensorboard_log}")

        # Create environment
        env = create_environment(self.agent_name, decisions)
        env = Monitor(env)  # Wrap for monitoring

        # Create PPO model
        model = PPO(
            policy="MlpPolicy",
            env=env,
            learning_rate=self.learning_rate,
            n_steps=self.n_steps,
            batch_size=self.batch_size,
            n_epochs=self.n_epochs,
            gamma=self.gamma,
            gae_lambda=self.gae_lambda,
            clip_range=self.clip_range,
            ent_coef=self.ent_coef,
            vf_coef=self.vf_coef,
            max_grad_norm=self.max_grad_norm,
            device=self.device,
            verbose=1,
            tensorboard_log=tensorboard_log,  # Enable Tensorboard logging
        )

        # Create callback for progress logging
        callback = ProgressCallback(log_freq=self.n_steps)

        # Train model
        logger.info("Starting PPO training...")
        model.learn(total_timesteps=total_timesteps, callback=callback, progress_bar=False)

        logger.info("PPO training completed!")

        # Calculate metrics
        metrics = self._calculate_metrics(model, env, decisions)

        return model, metrics

    def _calculate_metrics(
        self, model: PPO, env, decisions: List[Dict]
    ) -> Dict[str, float]:
        """Calculate training metrics.

        Args:
            model: Trained PPO model
            env: Training environment
            decisions: Training data

        Returns:
            Metrics dict
        """
        logger.info("Calculating training metrics...")

        # Evaluate on training data
        total_reward = 0.0
        correct_actions = 0
        total_actions = 0

        obs, _ = env.reset()
        for _ in range(min(len(decisions), 1000)):  # Evaluate on subset
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, _ = env.step(action)

            total_reward += reward
            total_actions += 1

            # Check if action was correct (reward > 0)
            if reward > 0:
                correct_actions += 1

            if terminated or truncated:
                obs, _ = env.reset()

        # Calculate metrics
        mean_reward = total_reward / total_actions if total_actions > 0 else 0.0
        accuracy = correct_actions / total_actions if total_actions > 0 else 0.0

        metrics = {
            "mean_reward": mean_reward,
            "accuracy": accuracy,
            "total_timesteps": total_actions,
        }

        logger.info(f"  Mean reward: {mean_reward:.4f}")
        logger.info(f"  Accuracy: {accuracy:.2%}")

        return metrics


def train_gate_agent(
    decisions: List[Dict], total_timesteps: int = 100000, tensorboard_log: str = None
) -> tuple[PPO, Dict[str, float]]:
    """Train gate agent with PPO.

    Args:
        decisions: Historical decisions
        total_timesteps: Training timesteps
        tensorboard_log: Tensorboard log directory

    Returns:
        Tuple of (trained_model, metrics)
    """
    trainer = AgentTrainer(
        agent_name="gate",
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        ent_coef=0.01,  # Small entropy for exploration
    )

    return trainer.train(decisions, total_timesteps, tensorboard_log)


def train_portfolio_agent(
    decisions: List[Dict], total_timesteps: int = 100000, tensorboard_log: str = None
) -> tuple[PPO, Dict[str, float]]:
    """Train portfolio agent with PPO.

    Args:
        decisions: Historical decisions
        total_timesteps: Training timesteps
        tensorboard_log: Tensorboard log directory

    Returns:
        Tuple of (trained_model, metrics)
    """
    trainer = AgentTrainer(
        agent_name="portfolio",
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        ent_coef=0.0,  # No entropy for continuous actions
    )

    return trainer.train(decisions, total_timesteps, tensorboard_log)


def train_meta_learner_agent(
    decisions: List[Dict], total_timesteps: int = 100000, tensorboard_log: str = None
) -> tuple[PPO, Dict[str, float]]:
    """Train meta-learner agent with PPO.

    Args:
        decisions: Historical decisions
        total_timesteps: Training timesteps
        tensorboard_log: Tensorboard log directory

    Returns:
        Tuple of (trained_model, metrics)
    """
    trainer = AgentTrainer(
        agent_name="meta_learner",
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        ent_coef=0.01,  # Small entropy for exploration
    )

    return trainer.train(decisions, total_timesteps, tensorboard_log)
