"""Always-signal playbook for testing LLM integration."""

from typing import Dict, Optional

from darwin.playbooks.base import CandidateInfo, PlaybookBase
from darwin.schemas import ExitSpecV1


class AlwaysSignalPlaybook(PlaybookBase):
    """
    Test playbook that always signals entries (for testing LLM integration).

    This generates a candidate on every bar after warmup, allowing us to test:
    1. LLM is being called
    2. LLM is making decisions (take/skip)
    3. Candidates are being cached
    4. Trades are being executed when LLM says TAKE
    """

    def __init__(
        self,
        stop_loss_atr: float = 1.2,
        take_profit_atr: float = 2.4,
        time_stop_bars: int = 32,
        trailing_activation_atr: float = 1.2,
        trailing_distance_atr: float = 1.2,
    ):
        """Initialize with exit parameters."""
        self.stop_loss_atr = stop_loss_atr
        self.take_profit_atr = take_profit_atr
        self.time_stop_bars = time_stop_bars
        self.trailing_activation_atr = trailing_activation_atr
        self.trailing_distance_atr = trailing_distance_atr

    def evaluate(
        self,
        features: Dict[str, float],
        bar_data: Dict[str, float],
    ) -> Optional[CandidateInfo]:
        """Always return a candidate (for testing)."""
        close = features.get("close", 0.0)
        atr = features.get("atr", 0.0)

        if close <= 0 or atr <= 0:
            return None

        # Generate exit spec
        exit_spec = self.get_exit_spec(close, atr, "long")

        return CandidateInfo(
            entry_price=close,
            atr_at_entry=atr,
            exit_spec=exit_spec,
            quality_flags={"test_signal": True},
            notes="Test signal - always fires",
        )

    def get_exit_spec(
        self,
        entry_price: float,
        atr: float,
        direction: str = "long"
    ) -> ExitSpecV1:
        """Generate exit specification."""
        stop_loss = entry_price - (self.stop_loss_atr * atr)
        take_profit = entry_price + (self.take_profit_atr * atr)
        trailing_activation = entry_price + (self.trailing_activation_atr * atr)

        return ExitSpecV1(
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            time_stop_bars=self.time_stop_bars,
            trailing_enabled=True,
            trailing_activation_price=trailing_activation,
            trailing_distance_atr=self.trailing_distance_atr,
        )
