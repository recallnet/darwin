"""SQLite storage for agent state and decision tracking."""

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np

from darwin.rl.schemas.agent_state import (
    AgentDecisionV1,
    AgentPerformanceSnapshotV1,
    GraduationRecordV1,
)


class AgentStateSQLite:
    """SQLite backend for agent state tracking.

    Tracks:
    - Agent decisions (state, action, outcome)
    - Performance snapshots (rolling metrics)
    - Graduation records (evaluation history)
    """

    def __init__(self, db_path: str | Path):
        """Initialize agent state database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        """Create tables if they don't exist."""
        # Agent decisions table
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_decisions (
                agent_name TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                state_hash TEXT NOT NULL,
                action REAL NOT NULL,
                mode TEXT NOT NULL,
                model_version TEXT NOT NULL,
                outcome_r_multiple REAL,
                outcome_pnl_usd REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (agent_name, candidate_id)
            )
            """
        )

        # Performance snapshots table
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS performance_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                window_size INTEGER NOT NULL,
                mean_r_multiple REAL NOT NULL,
                win_rate REAL NOT NULL,
                sharpe_ratio REAL,
                max_drawdown REAL,
                pass_rate REAL,
                override_rate REAL,
                agreement_rate REAL,
                cost_savings_pct REAL,
                llm_calls_avoided INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Graduation records table
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS graduation_records (
                graduation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                evaluation_date TEXT NOT NULL,
                passed INTEGER NOT NULL,
                reason TEXT NOT NULL,
                metrics TEXT NOT NULL,
                baseline_comparison TEXT,
                promoted INTEGER NOT NULL,
                demoted INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Create indexes
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_decisions_agent ON agent_decisions(agent_name)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_decisions_run ON agent_decisions(run_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_agent ON performance_snapshots(agent_name)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_graduation_agent ON graduation_records(agent_name)"
        )

        self.conn.commit()

    def record_decision(self, decision: AgentDecisionV1) -> None:
        """Record a single agent decision.

        Args:
            decision: Agent decision record
        """
        self.conn.execute(
            """
            INSERT OR REPLACE INTO agent_decisions (
                agent_name, candidate_id, run_id, timestamp,
                state_hash, action, mode, model_version,
                outcome_r_multiple, outcome_pnl_usd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision.agent_name,
                decision.candidate_id,
                decision.run_id,
                decision.timestamp.isoformat(),
                decision.state_hash,
                decision.action,
                decision.mode,
                decision.model_version,
                decision.outcome_r_multiple,
                decision.outcome_pnl_usd,
            ),
        )
        self.conn.commit()

    def update_decision_outcome(
        self,
        agent_name: str,
        candidate_id: str,
        outcome_r_multiple: float,
        outcome_pnl_usd: float,
    ) -> None:
        """Update outcome for a previous decision.

        Args:
            agent_name: Name of the agent
            candidate_id: Candidate identifier
            outcome_r_multiple: Realized R-multiple
            outcome_pnl_usd: Realized PnL in USD
        """
        self.conn.execute(
            """
            UPDATE agent_decisions
            SET outcome_r_multiple = ?, outcome_pnl_usd = ?
            WHERE agent_name = ? AND candidate_id = ?
            """,
            (outcome_r_multiple, outcome_pnl_usd, agent_name, candidate_id),
        )
        self.conn.commit()

    def get_decisions(
        self,
        agent_name: str,
        run_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[AgentDecisionV1]:
        """Retrieve agent decisions.

        Args:
            agent_name: Name of the agent
            run_id: Optional run ID filter
            limit: Optional limit on number of records

        Returns:
            List of agent decisions
        """
        query = "SELECT * FROM agent_decisions WHERE agent_name = ?"
        params: List[str | int] = [agent_name]

        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)

        query += " ORDER BY timestamp DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()

        return [self._row_to_decision(row) for row in rows]

    def _row_to_decision(self, row: sqlite3.Row) -> AgentDecisionV1:
        """Convert database row to AgentDecisionV1."""
        return AgentDecisionV1(
            agent_name=row["agent_name"],
            candidate_id=row["candidate_id"],
            run_id=row["run_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            state_hash=row["state_hash"],
            action=row["action"],
            mode=row["mode"],
            model_version=row["model_version"],
            outcome_r_multiple=row["outcome_r_multiple"],
            outcome_pnl_usd=row["outcome_pnl_usd"],
        )

    def save_performance_snapshot(self, snapshot: AgentPerformanceSnapshotV1) -> None:
        """Save performance snapshot.

        Args:
            snapshot: Performance snapshot
        """
        self.conn.execute(
            """
            INSERT INTO performance_snapshots (
                agent_name, snapshot_date, window_size,
                mean_r_multiple, win_rate, sharpe_ratio, max_drawdown,
                pass_rate, override_rate, agreement_rate,
                cost_savings_pct, llm_calls_avoided
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.agent_name,
                snapshot.snapshot_date.isoformat(),
                snapshot.window_size,
                snapshot.mean_r_multiple,
                snapshot.win_rate,
                snapshot.sharpe_ratio,
                snapshot.max_drawdown,
                snapshot.pass_rate,
                snapshot.override_rate,
                snapshot.agreement_rate,
                snapshot.cost_savings_pct,
                snapshot.llm_calls_avoided,
            ),
        )
        self.conn.commit()

    def get_performance_history(
        self,
        agent_name: str,
        limit: Optional[int] = None,
    ) -> List[AgentPerformanceSnapshotV1]:
        """Retrieve performance history.

        Args:
            agent_name: Name of the agent
            limit: Optional limit on number of records

        Returns:
            List of performance snapshots
        """
        query = "SELECT * FROM performance_snapshots WHERE agent_name = ? ORDER BY snapshot_date DESC"
        params: List[str | int] = [agent_name]

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()

        return [self._row_to_snapshot(row) for row in rows]

    def _row_to_snapshot(self, row: sqlite3.Row) -> AgentPerformanceSnapshotV1:
        """Convert database row to AgentPerformanceSnapshotV1."""
        return AgentPerformanceSnapshotV1(
            agent_name=row["agent_name"],
            snapshot_date=datetime.fromisoformat(row["snapshot_date"]),
            window_size=row["window_size"],
            mean_r_multiple=row["mean_r_multiple"],
            win_rate=row["win_rate"],
            sharpe_ratio=row["sharpe_ratio"],
            max_drawdown=row["max_drawdown"],
            pass_rate=row["pass_rate"],
            override_rate=row["override_rate"],
            agreement_rate=row["agreement_rate"],
            cost_savings_pct=row["cost_savings_pct"],
            llm_calls_avoided=row["llm_calls_avoided"],
        )

    def save_graduation_record(self, record: GraduationRecordV1) -> None:
        """Save graduation evaluation record.

        Args:
            record: Graduation record
        """
        self.conn.execute(
            """
            INSERT INTO graduation_records (
                agent_name, evaluation_date, passed, reason,
                metrics, baseline_comparison, promoted, demoted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.agent_name,
                record.evaluation_date.isoformat(),
                1 if record.passed else 0,
                record.reason,
                json.dumps(record.metrics),
                json.dumps(record.baseline_comparison) if record.baseline_comparison else None,
                1 if record.promoted else 0,
                1 if record.demoted else 0,
            ),
        )
        self.conn.commit()

    def get_graduation_history(
        self,
        agent_name: str,
        limit: Optional[int] = None,
    ) -> List[GraduationRecordV1]:
        """Retrieve graduation history.

        Args:
            agent_name: Name of the agent
            limit: Optional limit on number of records

        Returns:
            List of graduation records
        """
        query = "SELECT * FROM graduation_records WHERE agent_name = ? ORDER BY evaluation_date DESC"
        params: List[str | int] = [agent_name]

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()

        return [self._row_to_graduation(row) for row in rows]

    def _row_to_graduation(self, row: sqlite3.Row) -> GraduationRecordV1:
        """Convert database row to GraduationRecordV1."""
        return GraduationRecordV1(
            agent_name=row["agent_name"],
            evaluation_date=datetime.fromisoformat(row["evaluation_date"]),
            passed=bool(row["passed"]),
            reason=row["reason"],
            metrics=json.loads(row["metrics"]),
            baseline_comparison=(
                json.loads(row["baseline_comparison"]) if row["baseline_comparison"] else None
            ),
            promoted=bool(row["promoted"]),
            demoted=bool(row["demoted"]),
        )

    def get_decision_count(
        self,
        agent_name: str,
        since: Optional[datetime] = None,
    ) -> int:
        """Get count of decisions for an agent.

        Args:
            agent_name: Name of the agent
            since: Optional start date filter

        Returns:
            Count of decisions
        """
        query = "SELECT COUNT(*) as count FROM agent_decisions WHERE agent_name = ?"
        params: List[str] = [agent_name]

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        cursor = self.conn.execute(query, params)
        row = cursor.fetchone()
        return row["count"] if row else 0

    def get_decisions_with_outcomes(
        self,
        agent_name: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[dict]:
        """Get decisions with outcomes for an agent.

        Args:
            agent_name: Name of the agent
            since: Optional start date filter
            until: Optional end date filter

        Returns:
            List of decision dictionaries with outcomes
        """
        query = """
            SELECT agent_name, candidate_id, run_id, timestamp,
                   state_hash, action, mode, model_version,
                   outcome_r_multiple, outcome_pnl_usd
            FROM agent_decisions
            WHERE agent_name = ? AND outcome_r_multiple IS NOT NULL
        """
        params: List[str] = [agent_name]

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        if until:
            query += " AND timestamp <= ?"
            params.append(until.isoformat())

        query += " ORDER BY timestamp DESC"

        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    @staticmethod
    def hash_state(state: np.ndarray) -> str:
        """Compute hash of state vector for deduplication.

        Args:
            state: State numpy array

        Returns:
            Hex hash string
        """
        state_bytes = state.tobytes()
        return hashlib.sha256(state_bytes).hexdigest()[:16]

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()
