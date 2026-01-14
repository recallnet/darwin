"""Portfolio agent for position sizing decisions."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

from darwin.rl.agents.base import RLAgent
from darwin.rl.utils.state_encoding import PortfolioStateEncoder
from darwin.schemas.candidate import CandidateRecordV1

logger = logging.getLogger(__name__)


class PortfolioAgent(RLAgent):
    """Portfolio agent for determining optimal position sizes.

    Uses PyTorch neural network with regression output [0, 1] for position size fraction.
    """

    def __init__(self, model_path: str | None = None):
        """Initialize portfolio agent.

        Args:
            model_path: Path to trained model (optional)
        """
        super().__init__(agent_name="portfolio", model_path=model_path)
        self.encoder = PortfolioStateEncoder()

        # Load model if path provided
        if model_path:
            self.load_model(model_path)

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

        # Get position size from PPO model
        action, _ = self.model.predict(state, deterministic=deterministic)
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

        # Get prediction
        action, _ = self.model.predict(state, deterministic=False)
        position_size = float(np.clip(action[0], 0.0, 1.0))

        # Get value function estimate as confidence
        try:
            obs_tensor = self.model.policy.obs_to_tensor(state)[0]
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
