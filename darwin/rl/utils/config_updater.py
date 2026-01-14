"""Utility to update RL config files after training."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class ConfigUpdater:
    """Updates RL configuration in YAML/JSON files."""

    @staticmethod
    def update_agent_config(
        config_path: str,
        agent_name: str,
        updates: Dict[str, Any],
        backup: bool = True,
    ) -> bool:
        """Update agent configuration in config file.

        Args:
            config_path: Path to config file (YAML or JSON)
            agent_name: Agent name ("gate", "portfolio", "meta_learner")
            updates: Dictionary of fields to update
            backup: Whether to create backup before updating

        Returns:
            True if successful

        Example:
            update_agent_config(
                "config.yaml",
                "gate",
                {
                    "mode": "active",
                    "model_path": "artifacts/run/models/gate/model.zip",
                    "current_status": "graduated",
                }
            )
        """
        config_file = Path(config_path)
        if not config_file.exists():
            logger.error(f"Config file not found: {config_path}")
            return False

        try:
            # Determine file format
            is_yaml = config_file.suffix.lower() in [".yaml", ".yml"]

            # Read config
            with open(config_file, "r") as f:
                if is_yaml:
                    config = yaml.safe_load(f)
                else:
                    config = json.load(f)

            # Backup if requested
            if backup:
                backup_path = config_file.with_suffix(config_file.suffix + ".bak")
                with open(backup_path, "w") as f:
                    if is_yaml:
                        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                    else:
                        json.dump(config, f, indent=2)
                logger.info(f"Created backup: {backup_path}")

            # Navigate to agent config
            if "rl" not in config:
                logger.error("No 'rl' section in config")
                return False

            agent_key = f"{agent_name}_agent"
            if agent_key not in config["rl"]:
                logger.error(f"No '{agent_key}' in rl config")
                return False

            # Apply updates
            for key, value in updates.items():
                old_value = config["rl"][agent_key].get(key)
                config["rl"][agent_key][key] = value
                logger.info(
                    f"Updated rl.{agent_key}.{key}: {old_value} → {value}"
                )

            # Write updated config
            with open(config_file, "w") as f:
                if is_yaml:
                    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                else:
                    json.dump(config, f, indent=2)

            logger.info(f"Successfully updated config: {config_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to update config: {e}")
            return False

    @staticmethod
    def activate_agent(
        config_path: str,
        agent_name: str,
        model_path: str,
    ) -> bool:
        """Activate agent after graduation.

        Convenience method that sets mode=active, updates model_path,
        and sets status=graduated.

        Args:
            config_path: Path to config file
            agent_name: Agent name
            model_path: Path to trained model

        Returns:
            True if successful
        """
        return ConfigUpdater.update_agent_config(
            config_path,
            agent_name,
            {
                "mode": "active",
                "model_path": model_path,
                "current_status": "graduated",
            },
        )

    @staticmethod
    def deactivate_agent(
        config_path: str,
        agent_name: str,
        reason: str = "degraded",
    ) -> bool:
        """Deactivate agent (rollback to observe mode).

        Args:
            config_path: Path to config file
            agent_name: Agent name
            reason: Reason for deactivation

        Returns:
            True if successful
        """
        return ConfigUpdater.update_agent_config(
            config_path,
            agent_name,
            {
                "mode": "observe",
                "current_status": reason,  # "degraded", "retrain_needed", etc.
            },
        )

    @staticmethod
    def read_agent_config(
        config_path: str,
        agent_name: str,
    ) -> Optional[Dict[str, Any]]:
        """Read agent configuration from config file.

        Args:
            config_path: Path to config file
            agent_name: Agent name

        Returns:
            Agent config dict or None if not found
        """
        config_file = Path(config_path)
        if not config_file.exists():
            return None

        try:
            is_yaml = config_file.suffix.lower() in [".yaml", ".yml"]

            with open(config_file, "r") as f:
                if is_yaml:
                    config = yaml.safe_load(f)
                else:
                    config = json.load(f)

            agent_key = f"{agent_name}_agent"
            return config.get("rl", {}).get(agent_key)

        except Exception as e:
            logger.error(f"Failed to read config: {e}")
            return None
