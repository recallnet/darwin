"""SQLite implementation of position ledger."""

import sqlite3
from pathlib import Path
from typing import List, Optional

from darwin.schemas.position import ExitReason, PositionRowV1
from darwin.storage.interface import PositionLedgerInterface


class PositionLedgerSQLite(PositionLedgerInterface):
    """
    SQLite backend for position ledger.

    The position ledger is the single source of truth for all PnL calculations.
    """

    def __init__(self, db_path: str | Path):
        """
        Initialize position ledger.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        """Create position ledger tables if they don't exist."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                position_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_timestamp TEXT NOT NULL,
                entry_bar_index INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                entry_fees_usd REAL NOT NULL,
                size_usd REAL NOT NULL,
                size_units REAL NOT NULL,
                exit_timestamp TEXT,
                exit_bar_index INTEGER,
                exit_price REAL,
                exit_fees_usd REAL,
                exit_reason TEXT,
                pnl_usd REAL,
                pnl_pct REAL,
                r_multiple REAL,
                stop_loss_price REAL NOT NULL,
                take_profit_price REAL NOT NULL,
                time_stop_bars INTEGER NOT NULL,
                trailing_enabled INTEGER NOT NULL,
                trailing_activated INTEGER DEFAULT 0,
                highest_price REAL,
                lowest_price REAL,
                is_open INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Create indexes for common queries
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_positions_run_id ON positions(run_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_positions_is_open ON positions(is_open)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_positions_candidate_id ON positions(candidate_id)"
        )
        self.conn.commit()

    def open_position(self, position: PositionRowV1) -> None:
        """Record a position opening."""
        self.conn.execute(
            """
            INSERT INTO positions (
                position_id, run_id, candidate_id, symbol, direction,
                entry_timestamp, entry_bar_index, entry_price, entry_fees_usd,
                size_usd, size_units, stop_loss_price, take_profit_price,
                time_stop_bars, trailing_enabled, highest_price, lowest_price,
                is_open
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                position.position_id,
                position.run_id,
                position.candidate_id,
                position.symbol,
                position.direction,
                position.entry_timestamp.isoformat(),
                position.entry_bar_index,
                position.entry_price,
                position.entry_fees_usd,
                position.size_usd,
                position.size_units,
                position.stop_loss_price,
                position.take_profit_price,
                position.time_stop_bars,
                1 if position.trailing_enabled else 0,
                position.highest_price,
                position.lowest_price,
                1 if position.is_open else 0,
            ),
        )
        self.conn.commit()

    def close_position(
        self,
        position_id: str,
        exit_timestamp: str,
        exit_bar_index: int,
        exit_price: float,
        exit_fees_usd: float,
        exit_reason: str,
        pnl_usd: float,
        pnl_pct: float,
        r_multiple: float,
    ) -> None:
        """Record a position closing."""
        self.conn.execute(
            """
            UPDATE positions
            SET exit_timestamp = ?,
                exit_bar_index = ?,
                exit_price = ?,
                exit_fees_usd = ?,
                exit_reason = ?,
                pnl_usd = ?,
                pnl_pct = ?,
                r_multiple = ?,
                is_open = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE position_id = ?
            """,
            (
                exit_timestamp,
                exit_bar_index,
                exit_price,
                exit_fees_usd,
                exit_reason,
                pnl_usd,
                pnl_pct,
                r_multiple,
                position_id,
            ),
        )
        self.conn.commit()

    def update_position_trailing(
        self,
        position_id: str,
        trailing_activated: bool,
        highest_price: Optional[float] = None,
        lowest_price: Optional[float] = None,
    ) -> None:
        """Update trailing stop state for a position."""
        updates = ["trailing_activated = ?", "updated_at = CURRENT_TIMESTAMP"]
        params = [1 if trailing_activated else 0]

        if highest_price is not None:
            updates.append("highest_price = ?")
            params.append(highest_price)
        if lowest_price is not None:
            updates.append("lowest_price = ?")
            params.append(lowest_price)

        params.append(position_id)

        query = f"UPDATE positions SET {', '.join(updates)} WHERE position_id = ?"
        self.conn.execute(query, params)
        self.conn.commit()

    def get_position(self, position_id: str) -> Optional[PositionRowV1]:
        """Retrieve a position by ID."""
        cursor = self.conn.execute(
            "SELECT * FROM positions WHERE position_id = ?", (position_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_position(row)

    def list_positions(
        self,
        run_id: Optional[str] = None,
        symbol: Optional[str] = None,
        is_open: Optional[bool] = None,
    ) -> List[PositionRowV1]:
        """List positions with filters."""
        query = "SELECT * FROM positions WHERE 1=1"
        params = []

        if run_id is not None:
            query += " AND run_id = ?"
            params.append(run_id)
        if symbol is not None:
            query += " AND symbol = ?"
            params.append(symbol)
        if is_open is not None:
            query += " AND is_open = ?"
            params.append(1 if is_open else 0)

        query += " ORDER BY entry_timestamp"

        cursor = self.conn.execute(query, params)
        return [self._row_to_position(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close the storage connection."""
        self.conn.close()

    def _row_to_position(self, row: sqlite3.Row) -> PositionRowV1:
        """Convert a database row to PositionRowV1."""
        return PositionRowV1(
            position_id=row["position_id"],
            run_id=row["run_id"],
            candidate_id=row["candidate_id"],
            symbol=row["symbol"],
            direction=row["direction"],
            entry_timestamp=row["entry_timestamp"],
            entry_bar_index=row["entry_bar_index"],
            entry_price=row["entry_price"],
            entry_fees_usd=row["entry_fees_usd"],
            size_usd=row["size_usd"],
            size_units=row["size_units"],
            exit_timestamp=row["exit_timestamp"],
            exit_bar_index=row["exit_bar_index"],
            exit_price=row["exit_price"],
            exit_fees_usd=row["exit_fees_usd"],
            exit_reason=ExitReason(row["exit_reason"]) if row["exit_reason"] else None,
            pnl_usd=row["pnl_usd"],
            pnl_pct=row["pnl_pct"],
            r_multiple=row["r_multiple"],
            stop_loss_price=row["stop_loss_price"],
            take_profit_price=row["take_profit_price"],
            time_stop_bars=row["time_stop_bars"],
            trailing_enabled=bool(row["trailing_enabled"]),
            trailing_activated=bool(row["trailing_activated"]),
            highest_price=row["highest_price"],
            lowest_price=row["lowest_price"],
            is_open=bool(row["is_open"]),
        )
