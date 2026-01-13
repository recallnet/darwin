"""Checkpointing for experiment runs.

Supports saving and restoring runner state to enable resumption after failures.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Checkpoint:
    """
    Checkpoint state for resuming runs.

    Includes:
    - Current bar index per symbol/timeframe
    - Feature pipeline state (if stateful)
    - Open positions
    - Equity state
    """

    run_id: str
    checkpoint_time: datetime
    bar_indices: Dict[str, int] = field(default_factory=dict)  # symbol -> bar_index
    feature_pipeline_state: Dict[str, Any] = field(default_factory=dict)
    open_position_ids: List[str] = field(default_factory=list)
    equity_usd: float = 0.0
    bars_processed: int = 0
    candidates_generated: int = 0
    trades_taken: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "checkpoint_time": self.checkpoint_time.isoformat(),
            "bar_indices": self.bar_indices,
            "feature_pipeline_state": self.feature_pipeline_state,
            "open_position_ids": self.open_position_ids,
            "equity_usd": self.equity_usd,
            "bars_processed": self.bars_processed,
            "candidates_generated": self.candidates_generated,
            "trades_taken": self.trades_taken,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        """Create from dictionary."""
        return cls(
            run_id=data["run_id"],
            checkpoint_time=datetime.fromisoformat(data["checkpoint_time"]),
            bar_indices=data.get("bar_indices", {}),
            feature_pipeline_state=data.get("feature_pipeline_state", {}),
            open_position_ids=data.get("open_position_ids", []),
            equity_usd=data.get("equity_usd", 0.0),
            bars_processed=data.get("bars_processed", 0),
            candidates_generated=data.get("candidates_generated", 0),
            trades_taken=data.get("trades_taken", 0),
        )


def save_checkpoint(checkpoint: Checkpoint, checkpoint_path: Path) -> None:
    """
    Save checkpoint to disk.

    Args:
        checkpoint: Checkpoint to save
        checkpoint_path: Path to checkpoint file (e.g., runs/run_001/checkpoint.json)

    Example:
        >>> checkpoint = Checkpoint(run_id="run_001", checkpoint_time=datetime.now())
        >>> save_checkpoint(checkpoint, Path("artifacts/runs/run_001/checkpoint.json"))
    """
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temporary file first, then atomic rename
    temp_path = checkpoint_path.with_suffix(".tmp")
    try:
        with open(temp_path, "w") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)
        temp_path.replace(checkpoint_path)
        logger.info(f"Checkpoint saved: {checkpoint_path}")
    except Exception as e:
        logger.error(f"Failed to save checkpoint: {e}")
        if temp_path.exists():
            temp_path.unlink()
        raise


def load_checkpoint(checkpoint_path: Path) -> Optional[Checkpoint]:
    """
    Load checkpoint from disk.

    Args:
        checkpoint_path: Path to checkpoint file

    Returns:
        Checkpoint if file exists and is valid, else None

    Example:
        >>> checkpoint = load_checkpoint(Path("artifacts/runs/run_001/checkpoint.json"))
        >>> if checkpoint:
        ...     print(f"Resuming from bar {checkpoint.bars_processed}")
    """
    if not checkpoint_path.exists():
        logger.debug(f"Checkpoint file does not exist: {checkpoint_path}")
        return None

    try:
        with open(checkpoint_path, "r") as f:
            data = json.load(f)
        checkpoint = Checkpoint.from_dict(data)
        logger.info(f"Checkpoint loaded: {checkpoint_path}")
        logger.info(f"  Run ID: {checkpoint.run_id}")
        logger.info(f"  Bars processed: {checkpoint.bars_processed}")
        logger.info(f"  Trades taken: {checkpoint.trades_taken}")
        logger.info(f"  Checkpoint time: {checkpoint.checkpoint_time}")
        return checkpoint
    except Exception as e:
        logger.error(f"Failed to load checkpoint: {e}")
        return None


def checkpoint_exists(checkpoint_path: Path) -> bool:
    """
    Check if checkpoint file exists.

    Args:
        checkpoint_path: Path to checkpoint file

    Returns:
        True if checkpoint exists
    """
    return checkpoint_path.exists()


def delete_checkpoint(checkpoint_path: Path) -> None:
    """
    Delete checkpoint file.

    Args:
        checkpoint_path: Path to checkpoint file
    """
    if checkpoint_path.exists():
        checkpoint_path.unlink()
        logger.info(f"Checkpoint deleted: {checkpoint_path}")
