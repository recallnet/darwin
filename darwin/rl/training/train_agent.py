"""Training job for RL agents.

Separate from the main runner - trains agents based on collected data
and evaluates graduation readiness.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from darwin.rl.graduation.evaluator import GraduationEvaluator
from darwin.rl.schemas.rl_config import AgentConfigV1, RLConfigV1
from darwin.rl.storage.agent_state import AgentStateSQLite

logger = logging.getLogger(__name__)


class AgentTrainer:
    """Train RL agents and evaluate graduation readiness.

    This is a separate process from the main trading runner.
    It reads collected data from agent_state.sqlite, trains models,
    and evaluates if agents are ready to graduate.
    """

    def __init__(self, rl_config: RLConfigV1, config_file_path: Optional[str] = None):
        """Initialize agent trainer.

        Args:
            rl_config: RL configuration
            config_file_path: Path to config file for auto-updates (optional)
        """
        self.config = rl_config
        self.config_file_path = config_file_path
        self.agent_state_db = AgentStateSQLite(rl_config.agent_state_db)
        self.evaluator = GraduationEvaluator(self.agent_state_db)

        logger.info("Initialized agent trainer")

    def train_and_evaluate(self, agent_name: str) -> bool:
        """Train agent and evaluate graduation.

        Args:
            agent_name: Agent to train ("gate", "portfolio", or "meta_learner")

        Returns:
            True if agent graduated, False otherwise
        """
        logger.info(f"================================================================================")
        logger.info(f"Training and evaluating agent: {agent_name}")
        logger.info(f"================================================================================")

        # Get agent config
        agent_config = self._get_agent_config(agent_name)
        if not agent_config:
            logger.error(f"Agent '{agent_name}' not found in config or not enabled")
            return False

        # Check minimum candidates requirement
        total_decisions = self.agent_state_db.get_decision_count(agent_name)
        min_candidates = agent_config.graduation_thresholds.min_candidates_seen

        logger.info(f"Total decisions recorded: {total_decisions}")
        logger.info(f"Minimum candidates required: {min_candidates}")

        if total_decisions < min_candidates:
            logger.info(
                f"❌ Agent has not seen enough candidates yet "
                f"({total_decisions} < {min_candidates})"
            )
            logger.info(f"   Need {min_candidates - total_decisions} more candidates")
            return False

        # Step 1: Check if we have enough data to train
        decisions_with_outcomes = self.agent_state_db.get_decisions_with_outcomes(agent_name)
        logger.info(f"Decisions with outcomes: {len(decisions_with_outcomes)}")

        min_training_samples = agent_config.graduation_thresholds.min_training_samples
        if len(decisions_with_outcomes) < min_training_samples:
            logger.info(
                f"❌ Not enough training samples yet "
                f"({len(decisions_with_outcomes)} < {min_training_samples})"
            )
            return False

        # Step 2: Train model (placeholder for now)
        logger.info("Training model...")
        model_trained = self._train_model(agent_name, decisions_with_outcomes)

        if not model_trained:
            logger.error("Model training failed")
            return False

        logger.info("✓ Model training completed")

        # Step 3: Calculate baseline metric
        baseline_metric = self._calculate_baseline(agent_name, agent_config)
        logger.info(f"Baseline metric: {baseline_metric:.4f}")

        # Step 4: Evaluate graduation
        is_ready, details = self.evaluator.evaluate_graduation(agent_config, baseline_metric)

        # Log detailed results
        logger.info("\n" + "="*80)
        logger.info("GRADUATION EVALUATION RESULTS")
        logger.info("="*80)

        logger.info("\n✅ Checks Passed:")
        for check in details["checks_passed"]:
            logger.info(f"   {check}")

        if details["checks_failed"]:
            logger.info("\n❌ Checks Failed:")
            for check in details["checks_failed"]:
                logger.info(f"   {check}")

        logger.info("\n📊 Metrics:")
        for key, value in details["metrics"].items():
            if key != "validation_windows":
                logger.info(f"   {key}: {value}")

        if "validation_windows" in details["metrics"]:
            logger.info("\n📈 Validation Windows:")
            for window in details["metrics"]["validation_windows"]:
                status = "✓" if window["passed"] else "✗"
                logger.info(
                    f"   Window {window['window']}: {status} "
                    f"metric={window['metric']:.4f}, "
                    f"improvement={window['improvement_pct']:.1f}%"
                )

        logger.info("="*80 + "\n")

        # Step 5: Update agent status if graduated
        if is_ready:
            logger.info(f"🎓 Agent '{agent_name}' is READY TO GRADUATE!")

            # Update model path to point to trained model
            model_path = Path(self.config.models_dir) / agent_name / "model.zip"
            self._update_agent_model_path(agent_name, str(model_path))

            # Update status to graduated
            self._update_agent_status(agent_name, "graduated")

            # Auto-update config file if path provided
            if self.config_file_path:
                logger.info(f"")
                logger.info(f"📝 Auto-updating config file...")
                success = self._auto_update_config(agent_name, str(model_path))
                if success:
                    logger.info(f"   ✅ Config file updated: {self.config_file_path}")
                    logger.info(f"   Agent is now ACTIVE (mode='active')")
                else:
                    logger.warning(f"   ⚠️  Config file update failed")
                    logger.info(f"   Please manually update config:")
                    logger.info(f"      rl.{agent_name}_agent.mode = 'active'")
                    logger.info(f"      rl.{agent_name}_agent.model_path = '{model_path}'")
            else:
                logger.info(f"")
                logger.info(f"✅ Next steps:")
                logger.info(f"   1. Model saved to: {model_path}")
                logger.info(f"   2. Agent status: graduated")
                logger.info(f"   3. Manually activate agent in config:")
                logger.info(f"      rl.{agent_name}_agent.mode = 'active'")
                logger.info(f"      rl.{agent_name}_agent.model_path = '{model_path}'")

            logger.info(f"")
            return True
        else:
            logger.info(f"📚 Agent '{agent_name}' needs more training")
            return False

    def _get_agent_config(self, agent_name: str) -> Optional[AgentConfigV1]:
        """Get agent configuration."""
        if agent_name == "gate":
            return self.config.gate_agent
        elif agent_name == "portfolio":
            return self.config.portfolio_agent
        elif agent_name == "meta_learner":
            return self.config.meta_learner_agent
        return None

    def _train_model(self, agent_name: str, training_data: list) -> bool:
        """Train agent model using PPO.

        Args:
            agent_name: Agent name
            training_data: List of training samples (decisions with outcomes)

        Returns:
            True if training succeeded
        """
        logger.info(f"Training {agent_name} agent with PPO...")
        logger.info(f"  Training samples: {len(training_data)}")

        try:
            from darwin.rl.training.algorithms import (
                train_gate_agent,
                train_portfolio_agent,
                train_meta_learner_agent,
            )
            from datetime import datetime

            # Select training function
            if agent_name == "gate":
                train_fn = train_gate_agent
            elif agent_name == "portfolio":
                train_fn = train_portfolio_agent
            elif agent_name == "meta_learner":
                train_fn = train_meta_learner_agent
            else:
                logger.error(f"Unknown agent: {agent_name}")
                return False

            # Create tensorboard log directory
            tensorboard_dir = Path(self.config.models_dir).parent / "tensorboard"
            tensorboard_dir.mkdir(parents=True, exist_ok=True)

            # Create timestamped run name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_name = f"{agent_name}_{timestamp}"

            # Train with PPO
            logger.info("Starting PPO training...")
            total_timesteps = min(len(training_data) * 100, 100000)  # Scale with data
            model, metrics = train_fn(
                training_data,
                total_timesteps=total_timesteps,
                tensorboard_log=str(tensorboard_dir)
            )

            logger.info("PPO training completed!")
            logger.info(f"  Metrics: {metrics}")
            logger.info(f"  Tensorboard logs: {tensorboard_dir}")
            logger.info(f"  View with: tensorboard --logdir {tensorboard_dir}")

            # Save model
            model_dir = Path(self.config.models_dir) / agent_name
            model_dir.mkdir(parents=True, exist_ok=True)
            model_path = model_dir / "model.zip"

            model.save(str(model_path))
            logger.info(f"Model saved to: {model_path}")

            return True

        except ImportError as e:
            logger.error(f"Training dependencies not available: {e}")
            logger.error("Install with: pip install 'darwin[rl]'")
            return False
        except Exception as e:
            logger.error(f"Training failed: {e}", exc_info=True)
            return False

    def _calculate_baseline(self, agent_name: str, agent_config: AgentConfigV1) -> float:
        """Calculate baseline metric for comparison.

        Args:
            agent_name: Agent name
            agent_config: Agent configuration

        Returns:
            Baseline metric value
        """
        baseline_type = agent_config.graduation_thresholds.baseline_type
        logger.info(f"Calculating baseline: {baseline_type}")

        # Get all decisions with outcomes
        decisions = self.agent_state_db.get_decisions_with_outcomes(agent_name)

        if not decisions:
            return 0.0

        # Agent-specific baselines
        if agent_name == "gate":
            # Baseline: pass everything (100% pass rate)
            if baseline_type == "pass_all":
                return 1.0
            else:
                return 0.5

        elif agent_name == "portfolio":
            # Baseline: equal weight sizing (Sharpe of equal-sized positions)
            if baseline_type == "equal_weight":
                # Calculate Sharpe from all decisions
                r_multiples = [d["r_multiple"] for d in decisions if d["r_multiple"] is not None]
                if len(r_multiples) < 10:
                    return 0.0

                import numpy as np
                mean_r = np.mean(r_multiples)
                std_r = np.std(r_multiples, ddof=1)
                return mean_r / std_r if std_r > 1e-9 else 0.0
            else:
                return 0.0

        elif agent_name == "meta_learner":
            # Baseline: LLM only (no overrides)
            if baseline_type == "llm_only":
                # Metric: LLM accuracy without any overrides
                # Assume LLM decisions were correct baseline
                return 0.5  # Neutral baseline
            else:
                return 0.5

        return 0.0

    def _update_agent_model_path(self, agent_name: str, model_path: str) -> None:
        """Update agent model path in config.

        Args:
            agent_name: Agent name
            model_path: Path to trained model file
        """
        agent_config = self._get_agent_config(agent_name)
        if agent_config:
            agent_config.model_path = model_path
            logger.info(f"Updated {agent_name} agent model_path to: {model_path}")

    def _update_agent_status(self, agent_name: str, status: str) -> None:
        """Update agent status in config.

        Args:
            agent_name: Agent name
            status: New status ("training", "graduated", "degraded")
        """
        agent_config = self._get_agent_config(agent_name)
        if agent_config:
            agent_config.current_status = status
            logger.info(f"Updated {agent_name} agent status to: {status}")

    def _auto_update_config(self, agent_name: str, model_path: str) -> bool:
        """Auto-update config file after graduation.

        Args:
            agent_name: Agent name
            model_path: Path to trained model

        Returns:
            True if successful
        """
        if not self.config_file_path:
            return False

        try:
            from darwin.rl.utils.config_updater import ConfigUpdater

            return ConfigUpdater.activate_agent(
                self.config_file_path,
                agent_name,
                model_path,
            )
        except Exception as e:
            logger.error(f"Failed to auto-update config: {e}")
            return False

    def close(self) -> None:
        """Close database connections."""
        self.agent_state_db.close()


def train_agent_from_config_file(config_path: str, agent_name: str, auto_activate: bool = True) -> bool:
    """Train agent from config file.

    Args:
        config_path: Path to run config file (YAML or JSON)
        agent_name: Agent to train
        auto_activate: If True, automatically activate agent after graduation

    Returns:
        True if agent graduated
    """
    config_file = Path(config_path)
    if not config_file.exists():
        logger.error(f"Config file not found: {config_path}")
        return False

    # Determine file format
    is_yaml = config_file.suffix.lower() in [".yaml", ".yml"]

    # Load config
    with open(config_file) as f:
        if is_yaml:
            import yaml
            config_data = yaml.safe_load(f)
        else:
            config_data = json.load(f)

    # Extract RL config
    rl_config_dict = config_data.get("rl")
    if not rl_config_dict:
        logger.error("No RL config found in config file")
        return False

    rl_config = RLConfigV1(**rl_config_dict)

    # Create trainer with config path for auto-updates
    trainer = AgentTrainer(
        rl_config,
        config_file_path=str(config_file) if auto_activate else None
    )

    # Train and evaluate
    try:
        graduated = trainer.train_and_evaluate(agent_name)
        return graduated
    finally:
        trainer.close()
