"""Base playbook class and data structures."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional

from darwin.schemas import ExitSpecV1


@dataclass
class CandidateInfo:
    """
    Information about a candidate setup.

    This is returned by playbook evaluate() methods when entry conditions are met.
    Contains all necessary information to create a candidate record.
    """

    # Entry details
    entry_price: float
    atr_at_entry: float

    # Exit specification
    exit_spec: ExitSpecV1

    # Quality indicators (playbook-specific)
    quality_flags: Dict[str, bool]

    # Additional context
    notes: str = ""


class PlaybookBase(ABC):
    """
    Abstract base class for all trading playbooks.

    A playbook defines:
    1. Entry conditions (when to generate a candidate)
    2. Exit specifications (stop loss, take profit, trailing, time stop)
    3. Quality indicators (flags that describe setup quality)

    Playbooks are stateless and deterministic - they only evaluate a single bar
    given features and bar data.
    """

    @abstractmethod
    def evaluate(
        self,
        features: Dict[str, float],
        bar_data: Dict[str, float],
    ) -> Optional[CandidateInfo]:
        """
        Evaluate whether entry conditions are met for this playbook.

        Args:
            features: Feature dictionary computed by feature pipeline.
                Must include all required features for this playbook.
            bar_data: Raw OHLCV data for current bar.
                Keys: 'open', 'high', 'low', 'close', 'volume'

        Returns:
            CandidateInfo if entry conditions are met, None otherwise.

        Notes:
            - This method should be pure/stateless
            - All entry logic should be deterministic
            - Return None if any required condition is not met
            - Only evaluate LONG setups (shorts can be added later)
        """
        pass

    @abstractmethod
    def get_exit_spec(
        self,
        entry_price: float,
        atr: float,
        direction: str = "long"
    ) -> ExitSpecV1:
        """
        Generate exit specification for this playbook.

        Args:
            entry_price: Proposed entry price
            atr: ATR(14) value at entry
            direction: Trade direction ('long' or 'short')

        Returns:
            ExitSpecV1 with stop loss, take profit, trailing, and time stop.

        Notes:
            - Stop loss and take profit are in price units (not R)
            - Trailing activation price is in price units
            - Trailing distance is in ATR units (multiplier)
            - Time stop is in bars
        """
        pass

    def _safe_get(
        self,
        data: Dict[str, float],
        key: str,
        default: float = 0.0
    ) -> float:
        """
        Safely get a value from a dictionary with a default.

        Args:
            data: Dictionary to get value from
            key: Key to look up
            default: Default value if key is missing

        Returns:
            Value from dictionary or default if missing
        """
        return data.get(key, default)
