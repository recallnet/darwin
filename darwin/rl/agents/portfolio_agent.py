"""Portfolio agent for position sizing decisions."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
from stable_baselines3 import PPO

from darwin.rl.agents.base import RLAgent
from darwin.rl.utils.state_encoding import PortfolioStateEncoder
from darwin.schemas.candidate import CandidateRecordV1

logger = logging.getLogger(__name__)


class PortfolioAgent(RLAgent):
    """Portfolio agent for determining optimal position sizes.

    Uses PPO with continuous action space [0, 1] for position size fraction.
    """

    def __init__(self):
        """Initialize portfolio agent."""
        super().__init__(agent_name="portfolio")
        self.encoder = PortfolioStateEncoder()
        self.model: Optional[PPO] = None

    def predict(
        self,
        candidate: CandidateRecordV1,
        llm_response: Dict[str, Any],
        portfolio_state: Optional[Dict[str, Any]] = None,
        deterministic: bool = True,
    ) -> float:
        """Predict optimal position size fraction.

        Args:
            candidate: Candidate record
            llm_response: LLM response with decision context
            portfolio_state: Current portfolio state
            deterministic: Use deterministic prediction

        Returns:
            Position size fraction [0, 1]
        """
        if not self.is_loaded():
            raise ValueError("Model not loaded. Call load_model() first.")

        # Encode state
        state = self.encoder.encode(candidate, llm_response, portfolio_state or {})

        # Predict action
        action, _ = self.model.predict(state, deterministic=deterministic)

        # Clip to valid range
        position_size = float(np.clip(action[0], 0.0, 1.0))

        return position_size

    def predict_with_confidence(
        self,
        candidate: CandidateRecordV1,
        llm_response: Dict[str, Any],
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, float]:
        """Predict position size with confidence estimate.

        Args:
            candidate: Candidate record
            llm_response: LLM response
            portfolio_state: Current portfolio state

        Returns:
            Tuple of (position_size_fraction, confidence)
        """
        if not self.is_loaded():
            raise ValueError("Model not loaded. Call load_model() first.")

        # Encode state
        state = self.encoder.encode(candidate, llm_response, portfolio_state or {})

        # Predict with policy
        action, _ = self.model.predict(state, deterministic=False)
        position_size = float(np.clip(action[0], 0.0, 1.0))

        # Estimate confidence from value function
        try:
            obs_tensor = self.model.policy.obs_to_tensor(state)[0]
            with self.model.policy.policy.mlp_extractor.forward(obs_tensor):
                value = self.model.policy.predict_values(obs_tensor)
                confidence = float(np.abs(value.detach().numpy()[0][0]))
        except Exception as e:
            logger.warning(f"Failed to estimate confidence: {e}")
            confidence = 0.5  # Default confidence

        return position_size, confidence

    def get_state_dim(self) -> int:
        """Get state dimension.

        Returns:
            State dimension (30)
        """
        return self.encoder.state_dim

    def get_action_space(self) -> str:
        """Get action space description.

        Returns:
            Action space description
        """
        return "Box(0.0, 1.0, (1,))"

    def load_model(self, model_path: str) -> None:
        """Load trained PPO model.

        Args:
            model_path: Path to model file
        """
        model_file = Path(model_path)
        if not model_file.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        self.model = PPO.load(str(model_file))
        logger.info(f"Loaded portfolio agent model from {model_path}")

    def is_loaded(self) -> bool:
        """Check if model is loaded.

        Returns:
            True if model is loaded
        """
        return self.model is not None

    def explain_decision(
        self,
        candidate: CandidateRecordV1,
        llm_response: Dict[str, Any],
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Explain position sizing decision.

        Args:
            candidate: Candidate record
            llm_response: LLM response
            portfolio_state: Current portfolio state

        Returns:
            Explanation dictionary
        """
        if not self.is_loaded():
            raise ValueError("Model not loaded. Call load_model() first.")

        # Get prediction
        position_size, confidence = self.predict_with_confidence(
            candidate, llm_response, portfolio_state
        )

        # Get state features
        state = self.encoder.encode(candidate, llm_response, portfolio_state or {})

        # Extract key features
        feature_names = self.encoder.feature_names
        top_features = {}
        for i, name in enumerate(feature_names[:10]):  # Top 10 features
            top_features[name] = float(state[i])

        explanation = {
            "position_size_fraction": position_size,
            "confidence": confidence,
            "top_features": top_features,
            "portfolio_exposure": portfolio_state.get("exposure_frac", 0.0)
            if portfolio_state
            else 0.0,
            "llm_confidence": llm_response.get("confidence", 0.0),
        }

        return explanation
