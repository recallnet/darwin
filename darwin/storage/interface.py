"""Abstract storage interfaces for Darwin stores."""

from abc import ABC, abstractmethod
from typing import List, Optional

from darwin.schemas.candidate import CandidateRecordV1
from darwin.schemas.outcome_label import OutcomeLabelV1
from darwin.schemas.position import PositionRowV1


class CandidateCacheInterface(ABC):
    """
    Abstract interface for candidate cache storage.

    Stores all candidates (taken and skipped) with features and decision info.
    This is the learning substrate for future RL/supervised learning.
    """

    @abstractmethod
    def put(self, candidate: CandidateRecordV1) -> None:
        """Store a candidate record."""
        pass

    @abstractmethod
    def get(self, candidate_id: str) -> Optional[CandidateRecordV1]:
        """Retrieve a candidate by ID."""
        pass

    @abstractmethod
    def query(
        self,
        run_id: Optional[str] = None,
        symbol: Optional[str] = None,
        playbook: Optional[str] = None,
        was_taken: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> List[CandidateRecordV1]:
        """Query candidates with filters."""
        pass

    @abstractmethod
    def count(
        self,
        run_id: Optional[str] = None,
        symbol: Optional[str] = None,
        playbook: Optional[str] = None,
        was_taken: Optional[bool] = None,
    ) -> int:
        """Count candidates matching filters."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the storage connection."""
        pass


class PositionLedgerInterface(ABC):
    """
    Abstract interface for position ledger storage.

    The position ledger is the single source of truth for all PnL calculations.
    """

    @abstractmethod
    def open_position(self, position: PositionRowV1) -> None:
        """Record a position opening."""
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def update_position_trailing(
        self,
        position_id: str,
        trailing_activated: bool,
        highest_price: Optional[float] = None,
        lowest_price: Optional[float] = None,
    ) -> None:
        """Update trailing stop state for a position."""
        pass

    @abstractmethod
    def get_position(self, position_id: str) -> Optional[PositionRowV1]:
        """Retrieve a position by ID."""
        pass

    @abstractmethod
    def list_positions(
        self,
        run_id: Optional[str] = None,
        symbol: Optional[str] = None,
        is_open: Optional[bool] = None,
    ) -> List[PositionRowV1]:
        """List positions with filters."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the storage connection."""
        pass


class OutcomeLabelsInterface(ABC):
    """
    Abstract interface for outcome labels storage.

    Stores post-hoc labels attached to candidates for learning.
    """

    @abstractmethod
    def upsert_label(self, label: OutcomeLabelV1) -> None:
        """Insert or update an outcome label."""
        pass

    @abstractmethod
    def get_label(self, candidate_id: str) -> Optional[OutcomeLabelV1]:
        """Retrieve label for a candidate."""
        pass

    @abstractmethod
    def get_labels_for_run(self, run_id: str) -> List[OutcomeLabelV1]:
        """Retrieve all labels for a run."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the storage connection."""
        pass
