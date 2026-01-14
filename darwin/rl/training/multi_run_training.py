"""Multi-run training for RL agents.

Combines data from multiple backtest runs to train agents on larger, more diverse datasets.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from darwin.rl.storage.agent_state import AgentStateSQLite
from darwin.rl.training.algorithms import (
    train_gate_agent,
    train_portfolio_agent,
    train_meta_learner_agent,
)

logger = logging.getLogger(__name__)


class MultiRunTrainer:
    """Train RL agents on data from multiple runs."""

    def __init__(self, agent_state_db_paths: List[str]):
        """Initialize multi-run trainer.

        Args:
            agent_state_db_paths: List of paths to agent_state.sqlite databases
        """
        self.db_paths = agent_state_db_paths
        self.databases = []

        # Validate and open all databases
        for db_path in agent_state_db_paths:
            if not Path(db_path).exists():
                logger.warning(f"Database not found: {db_path}")
                continue

            try:
                db = AgentStateSQLite(db_path)
                self.databases.append(db)
                logger.info(f"Loaded database: {db_path}")
            except Exception as e:
                logger.error(f"Failed to load database {db_path}: {e}")

        if not self.databases:
            raise ValueError("No valid databases found")

        logger.info(f"Initialized multi-run trainer with {len(self.databases)} databases")

    def get_combined_decisions(self, agent_name: str) -> List[Dict]:
        """Get all decisions with outcomes from all runs.

        Args:
            agent_name: Agent name

        Returns:
            Combined list of decisions
        """
        logger.info(f"Combining decisions for agent: {agent_name}")

        all_decisions = []
        for i, db in enumerate(self.databases):
            decisions = db.get_decisions_with_outcomes(agent_name)
            logger.info(f"  Run {i+1}: {len(decisions)} decisions with outcomes")
            all_decisions.extend(decisions)

        logger.info(f"Total combined decisions: {len(all_decisions)}")
        return all_decisions

    def get_combined_decision_count(self, agent_name: str) -> int:
        """Get total decision count across all runs.

        Args:
            agent_name: Agent name

        Returns:
            Total decision count
        """
        total = 0
        for db in self.databases:
            total += db.get_decision_count(agent_name)
        return total

    def get_run_statistics(self, agent_name: str) -> Dict:
        """Get statistics about data from each run.

        Args:
            agent_name: Agent name

        Returns:
            Statistics dictionary
        """
        stats = {
            "total_runs": len(self.databases),
            "total_decisions": self.get_combined_decision_count(agent_name),
            "total_with_outcomes": len(self.get_combined_decisions(agent_name)),
            "runs": [],
        }

        for i, db in enumerate(self.databases):
            run_stat = {
                "run_index": i + 1,
                "db_path": self.db_paths[i],
                "total_decisions": db.get_decision_count(agent_name),
                "decisions_with_outcomes": len(db.get_decisions_with_outcomes(agent_name)),
            }
            stats["runs"].append(run_stat)

        return stats

    def train_agent(
        self,
        agent_name: str,
        total_timesteps: int = 100000,
        tensorboard_log: Optional[str] = None,
    ) -> tuple:
        """Train agent on combined multi-run data.

        Args:
            agent_name: Agent to train ("gate", "portfolio", or "meta_learner")
            total_timesteps: Training timesteps
            tensorboard_log: Tensorboard log directory (optional)

        Returns:
            Tuple of (trained_model, metrics)
        """
        logger.info("=" * 80)
        logger.info(f"MULTI-RUN TRAINING: {agent_name}")
        logger.info("=" * 80)

        # Get statistics
        stats = self.get_run_statistics(agent_name)
        logger.info(f"\nData Summary:")
        logger.info(f"  Total runs: {stats['total_runs']}")
        logger.info(f"  Total decisions: {stats['total_decisions']}")
        logger.info(f"  Decisions with outcomes: {stats['total_with_outcomes']}")
        logger.info(f"\nPer-run breakdown:")
        for run_stat in stats["runs"]:
            logger.info(
                f"  Run {run_stat['run_index']}: "
                f"{run_stat['decisions_with_outcomes']}/{run_stat['total_decisions']} with outcomes"
            )

        # Get combined training data
        decisions = self.get_combined_decisions(agent_name)

        if not decisions:
            logger.error("No training data found")
            return None, {}

        logger.info(f"\nTraining on {len(decisions)} combined samples...")

        # Select training function
        if agent_name == "gate":
            train_fn = train_gate_agent
        elif agent_name == "portfolio":
            train_fn = train_portfolio_agent
        elif agent_name == "meta_learner":
            train_fn = train_meta_learner_agent
        else:
            logger.error(f"Unknown agent: {agent_name}")
            return None, {}

        # Train with combined data
        model, metrics = train_fn(decisions, total_timesteps, tensorboard_log)

        logger.info("\n" + "=" * 80)
        logger.info("MULTI-RUN TRAINING COMPLETED")
        logger.info("=" * 80)

        return model, metrics

    def close(self):
        """Close all database connections."""
        for db in self.databases:
            db.close()


def train_agent_multi_run(
    agent_state_db_paths: List[str],
    agent_name: str,
    output_model_path: str,
    total_timesteps: int = 100000,
    tensorboard_log: Optional[str] = None,
) -> bool:
    """Train agent on data from multiple runs.

    Args:
        agent_state_db_paths: List of paths to agent_state.sqlite files
        agent_name: Agent to train
        output_model_path: Where to save trained model
        total_timesteps: Training timesteps
        tensorboard_log: Tensorboard log directory

    Returns:
        True if training succeeded
    """
    try:
        # Create trainer
        trainer = MultiRunTrainer(agent_state_db_paths)

        # Train agent
        model, metrics = trainer.train_agent(agent_name, total_timesteps, tensorboard_log)

        if model is None:
            logger.error("Training failed")
            return False

        # Save model
        output_path = Path(output_model_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        model.save(str(output_path))
        logger.info(f"\nModel saved to: {output_path}")

        # Close databases
        trainer.close()

        return True

    except Exception as e:
        logger.error(f"Multi-run training failed: {e}", exc_info=True)
        return False
