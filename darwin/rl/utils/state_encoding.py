"""State encoding utilities for RL agents.

Convert candidate features into state vectors for different agent types.
"""

import logging
from typing import Any, Dict, Optional

import numpy as np

from darwin.schemas.candidate import CandidateRecordV1, PlaybookType

logger = logging.getLogger(__name__)


class StateEncoder:
    """Base class for state encoders."""

    def __init__(self):
        """Initialize encoder."""
        self.feature_names: list[str] = []
        self.state_dim: int = 0

    def encode(self, *args: Any, **kwargs: Any) -> np.ndarray:
        """Encode inputs to state vector.

        Returns:
            State numpy array of shape (state_dim,)
        """
        raise NotImplementedError

    def get_state_dim(self) -> int:
        """Get state dimension."""
        return self.state_dim


class GateStateEncoder(StateEncoder):
    """Encode candidate features for gate agent.

    State space: 34 features
    - Price/Trend: 10 features
    - Volatility: 6 features
    - Momentum: 5 features
    - Volume: 4 features
    - Playbook-specific: 5 features
    - Portfolio context: 4 features
    """

    def __init__(self):
        """Initialize gate state encoder."""
        super().__init__()
        self.feature_names = [
            # Price/Trend (10)
            "close",
            "ret_1",
            "ret_4",
            "ret_16",
            "ret_96",
            "ema20_slope_bps",
            "ema50_slope_bps",
            "trend_dir",
            "trend_strength",
            "adx14",
            # Volatility (6)
            "atr_bps",
            "atr_z_96",
            "realized_vol_96",
            "bb_width_bps",
            "bb_pos",
            "vol_regime",
            # Momentum (5)
            "rsi14",
            "macd_hist",
            "di_plus_14",
            "di_minus_14",
            "momentum_z",
            # Volume (4)
            "volume_ratio_96",
            "vol_z_96",
            "adv_usd",
            "turnover_usd",
            # Playbook (5)
            "playbook_type",
            "breakout_dist_atr",
            "pullback_dist_ema20_atr",
            "pullback_dist_ema50_atr",
            "direction",
            # Portfolio (4)
            "open_positions",
            "exposure_frac",
            "dd_24h_bps",
            "halt_flag",
        ]
        self.state_dim = len(self.feature_names)

    def encode(
        self,
        candidate: CandidateRecordV1,
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        """Encode candidate to gate agent state.

        Args:
            candidate: Candidate record with features
            portfolio_state: Optional portfolio state dict

        Returns:
            State array of shape (35,)
        """
        state = np.zeros(self.state_dim, dtype=np.float32)
        features = candidate.features

        # Extract features with defaults
        for i, name in enumerate(self.feature_names):
            if name == "playbook_type":
                # Encode playbook type: breakout=0, pullback=1
                state[i] = 0.0 if candidate.playbook == PlaybookType.BREAKOUT else 1.0
            elif name == "direction":
                # Encode direction: long=1, short=-1
                state[i] = 1.0 if candidate.direction == "long" else -1.0
            elif name in ["open_positions", "exposure_frac", "dd_24h_bps", "halt_flag"]:
                # Portfolio context from external state
                if portfolio_state:
                    state[i] = float(portfolio_state.get(name, 0.0))
                else:
                    state[i] = 0.0
            else:
                # Feature from candidate
                state[i] = float(features.get(name, 0.0))

        # Handle NaN/Inf
        state = np.nan_to_num(state, nan=0.0, posinf=1e6, neginf=-1e6)

        return state


class PortfolioStateEncoder(StateEncoder):
    """Encode candidate + LLM + portfolio for portfolio agent.

    State space: 30 features
    - Candidate features (subset): 15 features
    - LLM output: 4 features
    - Portfolio context: 8 features
    - Risk specification: 3 features
    """

    def __init__(self):
        """Initialize portfolio state encoder."""
        super().__init__()
        self.feature_names = [
            # Candidate features (15)
            "atr_bps",
            "atr_z_96",
            "trend_strength",
            "trend_dir",
            "adx14",
            "rsi14",
            "macd_hist",
            "adv_usd",
            "spread_bps",
            "direction",
            "close",
            "vol_regime",
            "momentum_z",
            "volume_ratio_96",
            "bb_pos",
            # LLM output (4)
            "llm_confidence",
            "llm_setup_quality",
            "llm_has_risk_flags",
            "llm_decision",
            # Portfolio context (8)
            "current_equity_usd",
            "open_positions",
            "max_positions",
            "exposure_frac",
            "max_exposure_frac",
            "dd_24h_bps",
            "halt_flag",
            "available_capacity",
            # Risk specification (3)
            "stop_dist_atr",
            "tp_dist_atr",
            "risk_reward_ratio",
        ]
        self.state_dim = len(self.feature_names)

    def encode(
        self,
        candidate: CandidateRecordV1,
        llm_response: Dict[str, Any],
        portfolio_state: Dict[str, Any],
    ) -> np.ndarray:
        """Encode candidate + LLM + portfolio to portfolio agent state.

        Args:
            candidate: Candidate record
            llm_response: LLM response dict
            portfolio_state: Portfolio state dict

        Returns:
            State array of shape (30,)
        """
        state = np.zeros(self.state_dim, dtype=np.float32)
        features = candidate.features

        for i, name in enumerate(self.feature_names):
            if name == "direction":
                state[i] = 1.0 if candidate.direction == "long" else -1.0
            elif name == "llm_confidence":
                state[i] = float(llm_response.get("confidence", 0.5))
            elif name == "llm_setup_quality":
                # Encode quality: C=0, B=1, A=2, A+=3
                quality = llm_response.get("setup_quality", "C")
                quality_map = {"C": 0, "B": 1, "A": 2, "A+": 3}
                state[i] = float(quality_map.get(quality, 0))
            elif name == "llm_has_risk_flags":
                risk_flags = llm_response.get("risk_flags", [])
                state[i] = 1.0 if risk_flags else 0.0
            elif name == "llm_decision":
                decision = llm_response.get("decision", "skip")
                state[i] = 1.0 if decision == "take" else 0.0
            elif name in portfolio_state:
                state[i] = float(portfolio_state[name])
            elif name in ["stop_dist_atr", "tp_dist_atr", "risk_reward_ratio"]:
                # Compute from exit spec
                entry = candidate.entry_price
                stop = candidate.exit_spec.stop_loss_price
                tp = candidate.exit_spec.take_profit_price
                atr = candidate.atr_at_entry

                if name == "stop_dist_atr":
                    state[i] = abs(entry - stop) / atr if atr > 0 else 0.0
                elif name == "tp_dist_atr":
                    state[i] = abs(tp - entry) / atr if atr > 0 else 0.0
                elif name == "risk_reward_ratio":
                    stop_dist = abs(entry - stop)
                    tp_dist = abs(tp - entry)
                    state[i] = tp_dist / stop_dist if stop_dist > 0 else 0.0
            else:
                state[i] = float(features.get(name, 0.0))

        # Handle NaN/Inf
        state = np.nan_to_num(state, nan=0.0, posinf=1e6, neginf=-1e6)

        return state


class MetaLearnerStateEncoder(StateEncoder):
    """Encode candidate + LLM + history for meta-learner agent.

    State space: 38 features
    - Candidate features (subset): 20 features
    - LLM decision context: 6 features
    - Meta-learning context: 8 features
    - Portfolio context: 4 features
    """

    def __init__(self):
        """Initialize meta-learner state encoder."""
        super().__init__()
        self.feature_names = [
            # Candidate features (20)
            "close",
            "ret_1",
            "ret_4",
            "ret_16",
            "atr_bps",
            "atr_z_96",
            "realized_vol_96",
            "trend_strength",
            "trend_dir",
            "adx14",
            "rsi14",
            "macd_hist",
            "volume_ratio_96",
            "vol_z_96",
            "adv_usd",
            "spread_bps",
            "breakout_dist_atr",
            "pullback_dist_ema20_atr",
            "direction",
            "playbook_type",
            # LLM decision context (6)
            "llm_decision",
            "llm_confidence",
            "llm_setup_quality",
            "llm_risk_flags_count",
            "llm_response_time_ms",
            "llm_has_notes",
            # Meta-learning context (8)
            "llm_recent_accuracy",
            "llm_recent_sharpe",
            "playbook_llm_accuracy",
            "symbol_llm_accuracy",
            "market_regime",
            "time_of_day",
            "day_of_week",
            "llm_streak",
            # Portfolio context (4)
            "open_positions",
            "exposure_frac",
            "dd_24h_bps",
            "halt_flag",
        ]
        self.state_dim = len(self.feature_names)

    def encode(
        self,
        candidate: CandidateRecordV1,
        llm_response: Dict[str, Any],
        llm_history: Dict[str, Any],
        portfolio_state: Dict[str, Any],
    ) -> np.ndarray:
        """Encode candidate + LLM + history to meta-learner state.

        Args:
            candidate: Candidate record
            llm_response: LLM response dict
            llm_history: LLM historical performance dict
            portfolio_state: Portfolio state dict

        Returns:
            State array of shape (38,)
        """
        state = np.zeros(self.state_dim, dtype=np.float32)
        features = candidate.features

        for i, name in enumerate(self.feature_names):
            if name == "direction":
                state[i] = 1.0 if candidate.direction == "long" else -1.0
            elif name == "playbook_type":
                state[i] = 0.0 if candidate.playbook == PlaybookType.BREAKOUT else 1.0
            elif name == "llm_decision":
                decision = llm_response.get("decision", "skip")
                state[i] = 1.0 if decision == "take" else 0.0
            elif name == "llm_confidence":
                state[i] = float(llm_response.get("confidence", 0.5))
            elif name == "llm_setup_quality":
                quality = llm_response.get("setup_quality", "C")
                quality_map = {"C": 0, "B": 1, "A": 2, "A+": 3}
                state[i] = float(quality_map.get(quality, 0))
            elif name == "llm_risk_flags_count":
                risk_flags = llm_response.get("risk_flags", [])
                state[i] = float(len(risk_flags))
            elif name == "llm_response_time_ms":
                state[i] = float(llm_response.get("response_time_ms", 0.0))
            elif name == "llm_has_notes":
                notes = llm_response.get("notes", "")
                state[i] = 1.0 if notes else 0.0
            elif name in llm_history:
                # LLM historical metrics
                state[i] = float(llm_history[name])
            elif name in portfolio_state:
                # Portfolio context
                state[i] = float(portfolio_state[name])
            elif name == "time_of_day":
                # Normalize hour to [0, 1]
                hour = candidate.timestamp.hour
                state[i] = hour / 24.0
            elif name == "day_of_week":
                # Normalize day to [0, 1]
                day = candidate.timestamp.weekday()
                state[i] = day / 7.0
            else:
                # Candidate feature
                state[i] = float(features.get(name, 0.0))

        # Handle NaN/Inf
        state = np.nan_to_num(state, nan=0.0, posinf=1e6, neginf=-1e6)

        return state
