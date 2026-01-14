"""LLM performance history tracker for meta-learning.

Tracks rolling LLM performance metrics to help the meta-learner agent
make better override decisions.
"""

import logging
from collections import deque
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class LLMHistoryTracker:
    """Track LLM performance history for meta-learning.

    Maintains rolling statistics about LLM performance to enable
    the meta-learner agent to make better override decisions.
    """

    def __init__(self, window_size: int = 100):
        """Initialize LLM history tracker.

        Args:
            window_size: Number of recent decisions to track (default: 100)
        """
        self.window_size = window_size

        # Rolling decision history (oldest to newest)
        self.decisions: deque = deque(maxlen=window_size)

        # Current win/loss streak
        self.current_streak = 0  # Positive = wins, negative = losses

        # Per-playbook tracking
        self.playbook_stats: Dict[str, Dict] = {}

        # Per-symbol tracking
        self.symbol_stats: Dict[str, Dict] = {}

        # Market regime estimation (simplified)
        self.recent_volatility: deque = deque(maxlen=20)

        logger.info(f"Initialized LLM history tracker with window_size={window_size}")

    def record_decision(
        self,
        candidate_id: str,
        symbol: str,
        playbook: str,
        llm_decision: str,
        llm_confidence: float,
        llm_setup_quality: str,
        timestamp: str,
    ) -> None:
        """Record a new LLM decision (without outcome yet).

        Args:
            candidate_id: Unique candidate identifier
            symbol: Trading symbol
            playbook: Playbook name
            llm_decision: "take" or "skip"
            llm_confidence: Confidence score [0.0, 1.0]
            llm_setup_quality: Setup quality grade
            timestamp: Decision timestamp
        """
        decision_record = {
            "candidate_id": candidate_id,
            "symbol": symbol,
            "playbook": playbook,
            "llm_decision": llm_decision,
            "llm_confidence": llm_confidence,
            "llm_setup_quality": llm_setup_quality,
            "timestamp": timestamp,
            "outcome": None,  # Will be updated later
            "r_multiple": None,
            "was_winner": None,
        }

        self.decisions.append(decision_record)

    def update_outcome(
        self,
        candidate_id: str,
        r_multiple: float,
        pnl_usd: float,
    ) -> None:
        """Update outcome for a previously recorded decision.

        Args:
            candidate_id: Candidate identifier
            r_multiple: Risk-adjusted return
            pnl_usd: Profit/loss in USD
        """
        # Find the decision in history
        for decision in reversed(self.decisions):
            if decision["candidate_id"] == candidate_id:
                decision["outcome"] = "closed"
                decision["r_multiple"] = r_multiple
                decision["pnl_usd"] = pnl_usd
                decision["was_winner"] = pnl_usd > 0

                # Update streak
                if pnl_usd > 0:
                    self.current_streak = max(1, self.current_streak + 1)
                else:
                    self.current_streak = min(-1, self.current_streak - 1)

                # Update playbook stats
                self._update_playbook_stats(decision)

                # Update symbol stats
                self._update_symbol_stats(decision)

                logger.debug(
                    f"Updated outcome for {candidate_id}: "
                    f"R={r_multiple:.2f}, PnL=${pnl_usd:.2f}, "
                    f"streak={self.current_streak}"
                )
                break

    def _update_playbook_stats(self, decision: Dict) -> None:
        """Update per-playbook statistics."""
        playbook = decision["playbook"]

        if playbook not in self.playbook_stats:
            self.playbook_stats[playbook] = {
                "total_decisions": 0,
                "total_winners": 0,
                "total_r_multiple": 0.0,
            }

        stats = self.playbook_stats[playbook]
        if decision["llm_decision"] == "take" and decision["outcome"] == "closed":
            stats["total_decisions"] += 1
            if decision["was_winner"]:
                stats["total_winners"] += 1
            stats["total_r_multiple"] += decision["r_multiple"]

    def _update_symbol_stats(self, decision: Dict) -> None:
        """Update per-symbol statistics."""
        symbol = decision["symbol"]

        if symbol not in self.symbol_stats:
            self.symbol_stats[symbol] = {
                "total_decisions": 0,
                "total_winners": 0,
                "total_r_multiple": 0.0,
            }

        stats = self.symbol_stats[symbol]
        if decision["llm_decision"] == "take" and decision["outcome"] == "closed":
            stats["total_decisions"] += 1
            if decision["was_winner"]:
                stats["total_winners"] += 1
            stats["total_r_multiple"] += decision["r_multiple"]

    def get_recent_accuracy(self, lookback: int = 50) -> float:
        """Calculate LLM accuracy over recent decisions.

        Args:
            lookback: Number of recent decisions to consider

        Returns:
            Win rate [0.0, 1.0] or 0.5 if insufficient data
        """
        # Get recent closed positions
        recent_closed = [
            d for d in list(self.decisions)[-lookback:]
            if d["llm_decision"] == "take" and d["outcome"] == "closed"
        ]

        if len(recent_closed) < 5:
            return 0.5  # Insufficient data

        winners = sum(1 for d in recent_closed if d["was_winner"])
        return winners / len(recent_closed)

    def get_recent_sharpe(self, lookback: int = 50) -> float:
        """Calculate LLM Sharpe ratio over recent decisions.

        Args:
            lookback: Number of recent decisions to consider

        Returns:
            Sharpe ratio or 0.0 if insufficient data
        """
        # Get recent closed positions
        recent_closed = [
            d for d in list(self.decisions)[-lookback:]
            if d["llm_decision"] == "take" and d["outcome"] == "closed"
        ]

        if len(recent_closed) < 10:
            return 0.0  # Insufficient data

        # Extract R-multiples
        r_multiples = [d["r_multiple"] for d in recent_closed]

        # Calculate Sharpe (simplified: mean / std)
        mean_r = np.mean(r_multiples)
        std_r = np.std(r_multiples, ddof=1)

        if std_r < 1e-9:
            return 0.0

        return float(mean_r / std_r)

    def get_playbook_accuracy(self, playbook: str) -> float:
        """Get accuracy for specific playbook.

        Args:
            playbook: Playbook name

        Returns:
            Win rate [0.0, 1.0] or 0.5 if no data
        """
        if playbook not in self.playbook_stats:
            return 0.5

        stats = self.playbook_stats[playbook]
        if stats["total_decisions"] < 5:
            return 0.5

        return stats["total_winners"] / stats["total_decisions"]

    def get_symbol_accuracy(self, symbol: str) -> float:
        """Get accuracy for specific symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Win rate [0.0, 1.0] or 0.5 if no data
        """
        if symbol not in self.symbol_stats:
            return 0.5

        stats = self.symbol_stats[symbol]
        if stats["total_decisions"] < 5:
            return 0.5

        return stats["total_winners"] / stats["total_decisions"]

    def get_market_regime(self) -> str:
        """Estimate current market regime (simplified).

        Returns:
            "low_vol", "neutral", or "high_vol"
        """
        if len(self.recent_volatility) < 10:
            return "neutral"

        recent_vol = np.mean(list(self.recent_volatility)[-10:])

        if recent_vol < 0.015:  # < 1.5% ATR
            return "low_vol"
        elif recent_vol > 0.03:  # > 3% ATR
            return "high_vol"
        else:
            return "neutral"

    def update_volatility(self, atr_pct: float) -> None:
        """Update recent volatility estimate.

        Args:
            atr_pct: ATR as percentage (e.g., 0.02 for 2%)
        """
        self.recent_volatility.append(atr_pct)

    def get_llm_history_dict(self) -> Dict:
        """Get LLM history as dict for meta-learner agent.

        Returns:
            Dictionary with all relevant metrics
        """
        return {
            "llm_recent_accuracy": self.get_recent_accuracy(lookback=50),
            "llm_recent_sharpe": self.get_recent_sharpe(lookback=50),
            "playbook_llm_accuracy": 0.5,  # Will be set per-candidate
            "symbol_llm_accuracy": 0.5,    # Will be set per-candidate
            "market_regime": self.get_market_regime(),
            "llm_streak": self.current_streak,
        }

    def get_total_decisions(self) -> int:
        """Get total number of decisions recorded.

        Returns:
            Total decision count
        """
        return len(self.decisions)

    def get_closed_positions_count(self) -> int:
        """Get number of closed positions (decisions with outcomes).

        Returns:
            Count of decisions with outcomes
        """
        return sum(1 for d in self.decisions if d["outcome"] == "closed")
