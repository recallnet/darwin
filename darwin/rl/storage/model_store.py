"""Model versioning and persistence for RL agents."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ModelStore:
    """Version and persist RL models with metadata.

    Directory structure:
        models_dir/
        ├── gate/
        │   ├── v1.0.0_2024-01-15.zip
        │   ├── v1.0.0_2024-01-15.json (metadata)
        │   ├── v1.1.0_2024-02-01.zip
        │   └── current -> v1.1.0_2024-02-01.zip
        ├── portfolio/
        │   └── ...
        └── meta_learner/
            └── ...
    """

    def __init__(self, models_dir: str | Path):
        """Initialize model store.

        Args:
            models_dir: Root directory for model storage
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def save_model(
        self,
        model: Any,  # PPO model from stable-baselines3
        agent_name: str,
        version: str,
        metadata: Dict[str, Any],
    ) -> str:
        """Save model with version and metadata.

        Args:
            model: PPO model to save
            agent_name: Name of agent ("gate", "portfolio", "meta_learner")
            version: Version string (e.g., "v1.0.0")
            metadata: Metadata dictionary with training info

        Returns:
            Path to saved model
        """
        # Create agent directory
        agent_dir = self.models_dir / agent_name
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d")
        filename = f"{version}_{timestamp}"
        model_path = agent_dir / f"{filename}.zip"
        metadata_path = agent_dir / f"{filename}.json"

        # Save model
        model.save(str(model_path))
        logger.info(f"Saved {agent_name} model to {model_path}")

        # Save metadata
        full_metadata = {
            "version": version,
            "agent_name": agent_name,
            "saved_at": datetime.now().isoformat(),
            "model_path": str(model_path),
            **metadata,
        }
        with open(metadata_path, "w") as f:
            json.dump(full_metadata, f, indent=2)
        logger.info(f"Saved metadata to {metadata_path}")

        # Update symlink to current
        self._update_current_link(agent_dir, f"{filename}.zip")

        return str(model_path)

    def _update_current_link(self, agent_dir: Path, target_filename: str) -> None:
        """Update 'current' symlink to point to latest model.

        Args:
            agent_dir: Agent directory
            target_filename: Filename to link to (e.g., "v1.0.0_2024-01-15.zip")
        """
        current_link = agent_dir / "current"

        # Remove existing symlink if it exists
        if current_link.exists() or current_link.is_symlink():
            current_link.unlink()

        # Create new symlink
        current_link.symlink_to(target_filename)
        logger.info(f"Updated current link to {target_filename}")

    def load_model(
        self,
        agent_name: str,
        version: Optional[str] = None,
    ) -> tuple[Any, Dict[str, Any]]:
        """Load model by version or current.

        Args:
            agent_name: Name of agent
            version: Optional version string. If None, loads "current"

        Returns:
            Tuple of (model, metadata)

        Raises:
            FileNotFoundError: If model doesn't exist
        """
        from stable_baselines3 import PPO

        agent_dir = self.models_dir / agent_name

        if version is None:
            # Load current model
            current_link = agent_dir / "current"
            if not current_link.exists():
                raise FileNotFoundError(
                    f"No current model found for {agent_name}. "
                    f"Train a model first or specify a version."
                )
            model_path = current_link.resolve()
        else:
            # Find model with this version
            model_files = list(agent_dir.glob(f"{version}_*.zip"))
            if not model_files:
                raise FileNotFoundError(
                    f"No model found for {agent_name} version {version}"
                )
            # Use most recent if multiple matches
            model_path = max(model_files, key=lambda p: p.stat().st_mtime)

        # Load model
        model = PPO.load(str(model_path))
        logger.info(f"Loaded {agent_name} model from {model_path}")

        # Load metadata
        metadata_path = model_path.with_suffix(".json")
        if metadata_path.exists():
            with open(metadata_path) as f:
                metadata = json.load(f)
        else:
            metadata = {}
            logger.warning(f"No metadata found for {model_path}")

        return model, metadata

    def list_versions(self, agent_name: str) -> list[Dict[str, Any]]:
        """List all versions for an agent.

        Args:
            agent_name: Name of agent

        Returns:
            List of version metadata dictionaries
        """
        agent_dir = self.models_dir / agent_name
        if not agent_dir.exists():
            return []

        versions = []
        for metadata_path in sorted(agent_dir.glob("*.json")):
            with open(metadata_path) as f:
                metadata = json.load(f)
                versions.append(metadata)

        return versions

    def rollback_model(self, agent_name: str, version: str) -> None:
        """Rollback to a previous model version.

        Args:
            agent_name: Name of agent
            version: Version string to rollback to

        Raises:
            FileNotFoundError: If version doesn't exist
        """
        agent_dir = self.models_dir / agent_name

        # Find model with this version
        model_files = list(agent_dir.glob(f"{version}_*.zip"))
        if not model_files:
            raise FileNotFoundError(
                f"No model found for {agent_name} version {version}"
            )

        # Use most recent if multiple matches
        model_path = max(model_files, key=lambda p: p.stat().st_mtime)

        # Update current link
        self._update_current_link(agent_dir, model_path.name)
        logger.info(f"Rolled back {agent_name} to version {version}")

    def delete_version(self, agent_name: str, version: str) -> None:
        """Delete a specific model version.

        Args:
            agent_name: Name of agent
            version: Version string to delete

        Raises:
            FileNotFoundError: If version doesn't exist
            ValueError: If trying to delete current version
        """
        agent_dir = self.models_dir / agent_name

        # Check if this is the current version
        current_link = agent_dir / "current"
        if current_link.exists():
            current_target = current_link.resolve()
            if version in current_target.name:
                raise ValueError(
                    f"Cannot delete current version {version}. "
                    f"Rollback to another version first."
                )

        # Find and delete model files
        model_files = list(agent_dir.glob(f"{version}_*"))
        if not model_files:
            raise FileNotFoundError(
                f"No files found for {agent_name} version {version}"
            )

        for file_path in model_files:
            file_path.unlink()
            logger.info(f"Deleted {file_path}")

        logger.info(f"Deleted {agent_name} version {version}")

    def get_current_version(self, agent_name: str) -> Optional[str]:
        """Get the current version string for an agent.

        Args:
            agent_name: Name of agent

        Returns:
            Version string or None if no current model
        """
        agent_dir = self.models_dir / agent_name
        current_link = agent_dir / "current"

        if not current_link.exists():
            return None

        # Extract version from filename
        filename = current_link.resolve().name
        # Format: v1.0.0_2024-01-15.zip
        version = filename.split("_")[0]
        return version
