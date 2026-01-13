"""SQLite implementation of candidate cache."""

import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from darwin.schemas.candidate import CandidateRecordV1, ExitSpecV1, PlaybookType
from darwin.storage.interface import CandidateCacheInterface


class CandidateCacheSQLite(CandidateCacheInterface):
    """
    SQLite backend for candidate cache.

    Stores all candidates (taken and skipped) with features and decision info.
    """

    def __init__(self, db_path: str | Path):
        """
        Initialize candidate cache.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        """Create candidate cache tables if they don't exist."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                candidate_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                bar_index INTEGER NOT NULL,
                playbook TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                atr_at_entry REAL NOT NULL,
                exit_spec TEXT NOT NULL,
                features TEXT NOT NULL,
                llm_decision TEXT,
                llm_confidence REAL,
                llm_setup_quality TEXT,
                payload_ref TEXT,
                response_ref TEXT,
                was_taken INTEGER NOT NULL,
                rejection_reason TEXT,
                position_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Create indexes for common queries
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_candidates_run_id ON candidates(run_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_candidates_symbol ON candidates(symbol)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_candidates_playbook ON candidates(playbook)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_candidates_was_taken ON candidates(was_taken)"
        )
        self.conn.commit()

    def put(self, candidate: CandidateRecordV1) -> None:
        """Store a candidate record."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO candidates (
                candidate_id, run_id, timestamp, symbol, timeframe, bar_index,
                playbook, direction, entry_price, atr_at_entry, exit_spec, features,
                llm_decision, llm_confidence, llm_setup_quality, payload_ref, response_ref,
                was_taken, rejection_reason, position_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.candidate_id,
                candidate.run_id,
                candidate.timestamp.isoformat(),
                candidate.symbol,
                candidate.timeframe,
                candidate.bar_index,
                str(candidate.playbook),
                candidate.direction,
                candidate.entry_price,
                candidate.atr_at_entry,
                json.dumps(candidate.exit_spec.model_dump()),
                json.dumps(candidate.features),
                candidate.llm_decision,
                candidate.llm_confidence,
                candidate.llm_setup_quality,
                candidate.payload_ref,
                candidate.response_ref,
                1 if candidate.was_taken else 0,
                candidate.rejection_reason,
                candidate.position_id,
            ),
        )
        self.conn.commit()

    def get(self, candidate_id: str) -> Optional[CandidateRecordV1]:
        """Retrieve a candidate by ID."""
        cursor = self.conn.execute(
            "SELECT * FROM candidates WHERE candidate_id = ?", (candidate_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_candidate(row)

    def query(
        self,
        run_id: Optional[str] = None,
        symbol: Optional[str] = None,
        playbook: Optional[str] = None,
        was_taken: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> List[CandidateRecordV1]:
        """Query candidates with filters."""
        query = "SELECT * FROM candidates WHERE 1=1"
        params = []

        if run_id is not None:
            query += " AND run_id = ?"
            params.append(run_id)
        if symbol is not None:
            query += " AND symbol = ?"
            params.append(symbol)
        if playbook is not None:
            query += " AND playbook = ?"
            params.append(playbook)
        if was_taken is not None:
            query += " AND was_taken = ?"
            params.append(1 if was_taken else 0)

        query += " ORDER BY timestamp"

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.execute(query, params)
        return [self._row_to_candidate(row) for row in cursor.fetchall()]

    def count(
        self,
        run_id: Optional[str] = None,
        symbol: Optional[str] = None,
        playbook: Optional[str] = None,
        was_taken: Optional[bool] = None,
    ) -> int:
        """Count candidates matching filters."""
        query = "SELECT COUNT(*) FROM candidates WHERE 1=1"
        params = []

        if run_id is not None:
            query += " AND run_id = ?"
            params.append(run_id)
        if symbol is not None:
            query += " AND symbol = ?"
            params.append(symbol)
        if playbook is not None:
            query += " AND playbook = ?"
            params.append(playbook)
        if was_taken is not None:
            query += " AND was_taken = ?"
            params.append(1 if was_taken else 0)

        cursor = self.conn.execute(query, params)
        return cursor.fetchone()[0]

    def close(self) -> None:
        """Close the storage connection."""
        self.conn.close()

    def _row_to_candidate(self, row: sqlite3.Row) -> CandidateRecordV1:
        """Convert a database row to CandidateRecordV1."""
        return CandidateRecordV1(
            candidate_id=row["candidate_id"],
            run_id=row["run_id"],
            timestamp=row["timestamp"],
            symbol=row["symbol"],
            timeframe=row["timeframe"],
            bar_index=row["bar_index"],
            playbook=PlaybookType(row["playbook"]),
            direction=row["direction"],
            entry_price=row["entry_price"],
            atr_at_entry=row["atr_at_entry"],
            exit_spec=ExitSpecV1(**json.loads(row["exit_spec"])),
            features=json.loads(row["features"]),
            llm_decision=row["llm_decision"],
            llm_confidence=row["llm_confidence"],
            llm_setup_quality=row["llm_setup_quality"],
            payload_ref=row["payload_ref"],
            response_ref=row["response_ref"],
            was_taken=bool(row["was_taken"]),
            rejection_reason=row["rejection_reason"],
            position_id=row["position_id"],
        )
