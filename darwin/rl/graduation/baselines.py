"""Baseline strategies for agent performance comparison."""

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from darwin.schemas.candidate import CandidateRecordV1

logger = logging.getLogger(__name__)


class BaselineStrategy:
    """Base class for baseline strategies."""

    def __init__(self, name: str):
        """Initialize baseline strategy.

        Args:
            name: Strategy name
        """
        self.name = name

    def compute_baseline_performance(
        self, episodes: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Compute baseline performance on episodes.

        Args:
            episodes: List of episodes with candidates and outcomes

        Returns:
            Dictionary with performance metrics
        """
        raise NotImplementedError


class PassAllBaseline(BaselineStrategy):
    """Pass all candidates to LLM (for gate agent baseline)."""

    def __init__(self):
        """Initialize pass-all baseline."""
        super().__init__("pass_all")

    def compute_baseline_performance(
        self, episodes: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Compute performance if we pass all candidates.

        Args:
            episodes: List of episodes with outcomes

        Returns:
            Baseline metrics (no filtering, all decisions are "pass")
        """
        if not episodes:
            return {
                "mean_r_multiple": 0.0,
                "sharpe_ratio": 0.0,
                "win_rate": 0.0,
                "total_trades": 0,
                "cost_per_trade": 1.0,  # Each LLM call costs 1 unit
            }

        # Baseline passes everything, so we get all outcomes
        r_multiples = []
        for ep in episodes:
            outcome = ep.get("outcome")
            if outcome and outcome.actual_r_multiple is not None:
                r_multiples.append(outcome.actual_r_multiple)

        if not r_multiples:
            return {
                "mean_r_multiple": 0.0,
                "sharpe_ratio": 0.0,
                "win_rate": 0.0,
                "total_trades": 0,
                "cost_per_trade": 1.0,
            }

        mean_r = float(np.mean(r_multiples))
        std_r = float(np.std(r_multiples))
        sharpe = mean_r / std_r if std_r > 0 else 0.0
        win_rate = float(np.mean([r > 0 for r in r_multiples]))

        return {
            "mean_r_multiple": mean_r,
            "sharpe_ratio": sharpe,
            "win_rate": win_rate,
            "total_trades": len(r_multiples),
            "cost_per_trade": 1.0,  # All candidates call LLM
        }


class EqualWeightBaseline(BaselineStrategy):
    """Equal weight position sizing (for portfolio agent baseline)."""

    def __init__(self, equal_weight: float = 1.0):
        """Initialize equal-weight baseline.

        Args:
            equal_weight: Fixed position size fraction (default: 1.0 = full size)
        """
        super().__init__("equal_weight")
        self.equal_weight = equal_weight

    def compute_baseline_performance(
        self, episodes: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Compute performance with equal-weight position sizing.

        Args:
            episodes: List of episodes with outcomes

        Returns:
            Baseline metrics (fixed position sizing)
        """
        if not episodes:
            return {
                "mean_r_multiple": 0.0,
                "sharpe_ratio": 0.0,
                "win_rate": 0.0,
                "total_trades": 0,
            }

        # Baseline uses equal weight for all trades
        r_multiples = []
        for ep in episodes:
            outcome = ep.get("outcome")
            if outcome and outcome.actual_r_multiple is not None:
                # Scale by equal weight
                scaled_r = outcome.actual_r_multiple * self.equal_weight
                r_multiples.append(scaled_r)

        if not r_multiples:
            return {
                "mean_r_multiple": 0.0,
                "sharpe_ratio": 0.0,
                "win_rate": 0.0,
                "total_trades": 0,
            }

        mean_r = float(np.mean(r_multiples))
        std_r = float(np.std(r_multiples))
        sharpe = mean_r / std_r if std_r > 0 else 0.0
        win_rate = float(np.mean([r > 0 for r in r_multiples]))

        return {
            "mean_r_multiple": mean_r,
            "sharpe_ratio": sharpe,
            "win_rate": win_rate,
            "total_trades": len(r_multiples),
        }


class LLMOnlyBaseline(BaselineStrategy):
    """LLM-only decisions (for meta-learner agent baseline)."""

    def __init__(self):
        """Initialize LLM-only baseline."""
        super().__init__("llm_only")

    def compute_baseline_performance(
        self, episodes: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Compute performance if we always follow LLM.

        Args:
            episodes: List of episodes with LLM decisions and outcomes

        Returns:
            Baseline metrics (no meta-learner override)
        """
        if not episodes:
            return {
                "mean_r_multiple": 0.0,
                "sharpe_ratio": 0.0,
                "win_rate": 0.0,
                "total_trades": 0,
                "agreement_rate": 1.0,  # 100% agreement (no overrides)
            }

        # Baseline follows LLM exactly
        r_multiples = []
        for ep in episodes:
            outcome = ep.get("outcome")
            llm_response = ep.get("llm_response", {})
            llm_decision = llm_response.get("decision", "skip")

            if outcome and outcome.actual_r_multiple is not None:
                # Only count if LLM said "take"
                if llm_decision == "take":
                    r_multiples.append(outcome.actual_r_multiple)

        if not r_multiples:
            return {
                "mean_r_multiple": 0.0,
                "sharpe_ratio": 0.0,
                "win_rate": 0.0,
                "total_trades": 0,
                "agreement_rate": 1.0,
            }

        mean_r = float(np.mean(r_multiples))
        std_r = float(np.std(r_multiples))
        sharpe = mean_r / std_r if std_r > 0 else 0.0
        win_rate = float(np.mean([r > 0 for r in r_multiples]))

        return {
            "mean_r_multiple": mean_r,
            "sharpe_ratio": sharpe,
            "win_rate": win_rate,
            "total_trades": len(r_multiples),
            "agreement_rate": 1.0,  # No overrides
        }


def get_baseline_strategy(baseline_type: str) -> BaselineStrategy:
    """Get baseline strategy by type.

    Args:
        baseline_type: Baseline type ("pass_all", "equal_weight", "llm_only")

    Returns:
        Baseline strategy instance

    Raises:
        ValueError: If baseline type is unknown
    """
    strategies = {
        "pass_all": PassAllBaseline(),
        "equal_weight": EqualWeightBaseline(),
        "llm_only": LLMOnlyBaseline(),
    }

    if baseline_type not in strategies:
        raise ValueError(
            f"Unknown baseline type: {baseline_type}. "
            f"Valid types: {list(strategies.keys())}"
        )

    return strategies[baseline_type]
