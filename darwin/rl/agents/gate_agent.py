"""Gate Agent implementation.

The gate agent filters candidates before sending to LLM.
"""

import logging
from typing import Any, Dict, Optional

import numpy as np

from darwin.rl.agents.base import RLAgent
from darwin.rl.utils.state_encoding import GateStateEncoder
from darwin.schemas.candidate import CandidateRecordV1

logger = logging.getLogger(__name__)


class GateAgent(RLAgent):
    """Gate Agent for filtering candidates before LLM.

    Action space: Discrete(2)
    - 0: SKIP (don't send to LLM)
    - 1: PASS (send to LLM)
    """

    SKIP = 0
    PASS = 1

    def __init__(self, model_path: str | None = None):
        """Initialize gate agent.

        Args:
            model_path: Path to trained PPO model (optional)
        """
        super().__init__(agent_name="gate", model_path=model_path)
        self.encoder = GateStateEncoder()

        # Load model if path provided
        if model_path:
            self.load_model(model_path)

    def predict(
        self,
        candidate: CandidateRecordV1,
        portfolio_state: Optional[Dict[str, Any]] = None,
        deterministic: bool = True,
    ) -> int:
        """Predict whether to skip or pass candidate to LLM.

        Args:
            candidate: Candidate record
            portfolio_state: Portfolio state dict (optional)
            deterministic: Whether to use deterministic policy (default: True)

        Returns:
            Action (0=skip, 1=pass)

        Raises:
            ValueError: If model not loaded
        """
        if not self.is_loaded():
            raise ValueError(
                f"Model not loaded for {self.agent_name} agent. "
                "Call load_model() first or initialize with model_path."
            )

        # Encode state
        state = self.encoder.encode(candidate, portfolio_state or {})

        # Get action from model
        action, _ = self.model.predict(state, deterministic=deterministic)

        # Convert to int
        action = int(action)

        logger.debug(
            f"Gate agent prediction for {candidate.candidate_id}: "
            f"{'SKIP' if action == self.SKIP else 'PASS'}"
        )

        return action

    def predict_with_confidence(
        self,
        candidate: CandidateRecordV1,
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> tuple[int, float]:
        """Predict action with confidence score.

        Args:
            candidate: Candidate record
            portfolio_state: Portfolio state dict (optional)

        Returns:
            Tuple of (action, confidence)
            - action: 0=skip, 1=pass
            - confidence: Probability of selected action [0, 1]
        """
        if not self.is_loaded():
            raise ValueError("Model not loaded")

        # Encode state
        state = self.encoder.encode(candidate, portfolio_state or {})

        # Get action probabilities
        action_probs = self.model.policy.get_distribution(state).distribution.probs.detach().numpy()

        # Get most likely action
        action = int(np.argmax(action_probs))
        confidence = float(action_probs[action])

        return action, confidence

    def should_pass(
        self,
        candidate: CandidateRecordV1,
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Convenience method to check if should pass to LLM.

        Args:
            candidate: Candidate record
            portfolio_state: Portfolio state dict (optional)

        Returns:
            True if should pass to LLM, False if should skip
        """
        action = self.predict(candidate, portfolio_state)
        return action == self.PASS

    def get_state_dim(self) -> int:
        """Get state dimension.

        Returns:
            State dimension (34)
        """
        return self.encoder.get_state_dim()

    def get_action_space(self) -> str:
        """Get action space description.

        Returns:
            Action space description
        """
        return "Discrete(2): 0=skip, 1=pass"

    def explain_decision(
        self,
        candidate: CandidateRecordV1,
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Explain agent's decision for a candidate.

        Args:
            candidate: Candidate record
            portfolio_state: Portfolio state dict (optional)

        Returns:
            Dictionary with decision explanation
        """
        action, confidence = self.predict_with_confidence(candidate, portfolio_state)
        state = self.encoder.encode(candidate, portfolio_state or {})

        return {
            "candidate_id": candidate.candidate_id,
            "action": "skip" if action == self.SKIP else "pass",
            "confidence": confidence,
            "state_dim": len(state),
            "playbook": candidate.playbook.value,
            "direction": candidate.direction,
            "model_path": self.model_path,
        }
