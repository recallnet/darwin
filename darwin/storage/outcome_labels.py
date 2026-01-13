"""SQLite implementation of outcome labels store."""

import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from darwin.schemas.outcome_label import OutcomeLabelV1
from darwin.storage.interface import OutcomeLabelsInterface


class OutcomeLabelsSQLite(OutcomeLabelsInterface):
    """
    SQLite backend for outcome labels.

    Stores post-hoc labels attached to candidates for learning.
    """

    def __init__(self, db_path: str | Path):
        """
        Initialize outcome labels store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        """Create outcome labels tables if they don't exist."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS outcome_labels (
                label_id TEXT PRIMARY KEY,
                candidate_id TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                was_taken INTEGER NOT NULL,
                position_id TEXT,
                actual_pnl_usd REAL,
                actual_r_multiple REAL,
                actual_exit_reason TEXT,
                counterfactual_pnl_usd REAL,
                counterfactual_r_multiple REAL,
                counterfactual_exit_reason TEXT,
                policy_labels TEXT,
                feature_snapshot TEXT
            )
            """
        )

        # Create index for querying by candidate_id
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_labels_candidate_id ON outcome_labels(candidate_id)"
        )
        self.conn.commit()

    def upsert_label(self, label: OutcomeLabelV1) -> None:
        """Insert or update an outcome label."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO outcome_labels (
                label_id, candidate_id, created_at, was_taken, position_id,
                actual_pnl_usd, actual_r_multiple, actual_exit_reason,
                counterfactual_pnl_usd, counterfactual_r_multiple, counterfactual_exit_reason,
                policy_labels, feature_snapshot
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                label.label_id,
                label.candidate_id,
                label.created_at.isoformat(),
                1 if label.was_taken else 0,
                label.position_id,
                label.actual_pnl_usd,
                label.actual_r_multiple,
                label.actual_exit_reason,
                label.counterfactual_pnl_usd,
                label.counterfactual_r_multiple,
                label.counterfactual_exit_reason,
                json.dumps(label.policy_labels) if label.policy_labels else None,
                json.dumps(label.feature_snapshot) if label.feature_snapshot else None,
            ),
        )
        self.conn.commit()

    def get_label(self, candidate_id: str) -> Optional[OutcomeLabelV1]:
        """Retrieve label for a candidate."""
        cursor = self.conn.execute(
            "SELECT * FROM outcome_labels WHERE candidate_id = ?", (candidate_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_label(row)

    def get_labels_for_run(self, run_id: str) -> List[OutcomeLabelV1]:
        """
        Retrieve all labels for a run.

        Note: This requires joining with candidates table to filter by run_id.
        For now, we'll return all labels and filter in memory.
        In production, you might want to add run_id to labels table.
        """
        cursor = self.conn.execute("SELECT * FROM outcome_labels ORDER BY created_at")
        return [self._row_to_label(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close the storage connection."""
        self.conn.close()

    def _row_to_label(self, row: sqlite3.Row) -> OutcomeLabelV1:
        """Convert a database row to OutcomeLabelV1."""
        return OutcomeLabelV1(
            label_id=row["label_id"],
            candidate_id=row["candidate_id"],
            created_at=row["created_at"],
            was_taken=bool(row["was_taken"]),
            position_id=row["position_id"],
            actual_pnl_usd=row["actual_pnl_usd"],
            actual_r_multiple=row["actual_r_multiple"],
            actual_exit_reason=row["actual_exit_reason"],
            counterfactual_pnl_usd=row["counterfactual_pnl_usd"],
            counterfactual_r_multiple=row["counterfactual_r_multiple"],
            counterfactual_exit_reason=row["counterfactual_exit_reason"],
            policy_labels=json.loads(row["policy_labels"]) if row["policy_labels"] else {},
            feature_snapshot=json.loads(row["feature_snapshot"]) if row["feature_snapshot"] else None,
        )
