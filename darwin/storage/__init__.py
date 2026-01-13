"""Storage layer with abstract interfaces and SQLite implementations."""

from darwin.storage.candidate_cache import CandidateCacheSQLite
from darwin.storage.interface import (
    CandidateCacheInterface,
    OutcomeLabelsInterface,
    PositionLedgerInterface,
)
from darwin.storage.outcome_labels import OutcomeLabelsSQLite
from darwin.storage.position_ledger import PositionLedgerSQLite

__all__ = [
    # Interfaces
    "CandidateCacheInterface",
    "PositionLedgerInterface",
    "OutcomeLabelsInterface",
    # SQLite implementations
    "CandidateCacheSQLite",
    "PositionLedgerSQLite",
    "OutcomeLabelsSQLite",
]
