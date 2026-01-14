"""Meta-learner agent for LLM decision override."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

from darwin.rl.agents.base import RLAgent
from darwin.rl.utils.state_encoding import MetaLearnerStateEncoder
from darwin.schemas.candidate import CandidateRecordV1

logger = logging.getLogger(__name__)

# Action constants
AGREE = 0
OVERRIDE_TO_SKIP = 1
OVERRIDE_TO_TAKE = 2


class MetaLearnerAgent(RLAgent):
    """Meta-learner agent for deciding when to override LLM decisions.

    Uses PyTorch neural network with discrete action space for three actions:
    - AGREE (0): Follow LLM decision
    - OVERRIDE_TO_SKIP (1): Override LLM "take" to "skip"
    - OVERRIDE_TO_TAKE (2): Override LLM "skip" to "take"
    """

    def __init__(self, model_path: str | None = None):
        """Initialize meta-learner agent.

        Args:
            model_path: Path to trained model (optional)
        """
        super().__init__(agent_name="meta_learner", model_path=model_path)
        self.encoder = MetaLearnerStateEncoder()

        # Load model if path provided
        if model_path:
            self.load_model(model_path)

    def predict(
        self,
        candidate: CandidateRecordV1,
        llm_response: Dict[str, Any],
        llm_history: Optional[Dict[str, Any]] = None,
        portfolio_state: Optional[Dict[str, Any]] = None,
        deterministic: bool = True,
    ) -> int:
        """Predict whether to agree or override LLM decision.

        Args:
            candidate: Candidate record
            llm_response: LLM response with decision context
            llm_history: Rolling LLM performance history
            portfolio_state: Current portfolio state
            deterministic: Use deterministic prediction

        Returns:
            Action (0=agree, 1=override_to_skip, 2=override_to_take)
        """
        if not self.is_loaded():
            raise ValueError("Model not loaded. Call load_model() first.")

        # Encode state
        state = self.encoder.encode(
            candidate, llm_response, llm_history or {}, portfolio_state or {}
        )

        # Get action from PPO model
        action, _ = self.model.predict(state, deterministic=deterministic)

        return int(action)

    def predict_with_confidence(
        self,
        candidate: CandidateRecordV1,
        llm_response: Dict[str, Any],
        llm_history: Optional[Dict[str, Any]] = None,
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, float]:
        """Predict action with confidence estimate.

        Args:
            candidate: Candidate record
            llm_response: LLM response
            llm_history: Rolling LLM performance history
            portfolio_state: Current portfolio state

        Returns:
            Tuple of (action, confidence)
        """
        if not self.is_loaded():
            raise ValueError("Model not loaded. Call load_model() first.")

        # Encode state
        state = self.encoder.encode(
            candidate, llm_response, llm_history or {}, portfolio_state or {}
        )

        # Get action probabilities from PPO policy
        action_probs = self.model.policy.get_distribution(state).distribution.probs.detach().numpy()

        # Get most likely action
        action = int(np.argmax(action_probs))
        confidence = float(action_probs[action])

        return action, confidence

    def should_override(
        self,
        candidate: CandidateRecordV1,
        llm_response: Dict[str, Any],
        llm_history: Optional[Dict[str, Any]] = None,
        portfolio_state: Optional[Dict[str, Any]] = None,
        deterministic: bool = True,
    ) -> Optional[str]:
        """Determine if LLM decision should be overridden.

        Args:
            candidate: Candidate record
            llm_response: LLM response with decision
            llm_history: Rolling LLM performance history
            portfolio_state: Current portfolio state
            deterministic: Use deterministic prediction

        Returns:
            Override decision ("skip", "take") or None to agree with LLM
        """
        action = self.predict(
            candidate, llm_response, llm_history, portfolio_state, deterministic
        )

        if action == AGREE:
            return None
        elif action == OVERRIDE_TO_SKIP:
            return "skip"
        else:  # OVERRIDE_TO_TAKE
            return "take"

    def get_state_dim(self) -> int:
        """Get state dimension.

        Returns:
            State dimension (38)
        """
        return self.encoder.state_dim

    def get_action_space(self) -> str:
        """Get action space description.

        Returns:
            Action space description
        """
        return "Discrete(3)"

    def explain_decision(
        self,
        candidate: CandidateRecordV1,
        llm_response: Dict[str, Any],
        llm_history: Optional[Dict[str, Any]] = None,
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Explain meta-learner decision.

        Args:
            candidate: Candidate record
            llm_response: LLM response
            llm_history: Rolling LLM performance history
            portfolio_state: Current portfolio state

        Returns:
            Explanation dictionary
        """
        if not self.is_loaded():
            raise ValueError("Model not loaded. Call load_model() first.")

        # Get prediction
        action, confidence = self.predict_with_confidence(
            candidate, llm_response, llm_history, portfolio_state
        )

        # Get state features
        state = self.encoder.encode(
            candidate, llm_response, llm_history or {}, portfolio_state or {}
        )

        # Extract key features
        feature_names = self.encoder.feature_names
        top_features = {}
        for i, name in enumerate(feature_names[:10]):  # Top 10 features
            top_features[name] = float(state[i])

        # Action interpretation
        action_names = {
            AGREE: "agree",
            OVERRIDE_TO_SKIP: "override_to_skip",
            OVERRIDE_TO_TAKE: "override_to_take",
        }

        explanation = {
            "action": action,
            "action_name": action_names.get(action, "unknown"),
            "confidence": confidence,
            "top_features": top_features,
            "llm_decision": llm_response.get("decision", "skip"),
            "llm_confidence": llm_response.get("confidence", 0.0),
            "llm_history": llm_history or {},
        }

        return explanation
