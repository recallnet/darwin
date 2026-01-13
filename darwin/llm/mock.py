"""Mock LLM for testing without API calls.

Provides deterministic responses based on configurable rules.
"""

import json
from typing import Any, Callable, Dict, Optional

from darwin.schemas.llm_response import LLMResponseV1


class MockLLM:
    """
    Mock LLM that returns deterministic responses for testing.

    Can be configured with:
    - Static responses
    - Rule-based responses (based on payload content)
    - Custom response functions

    Example:
        >>> # Static response
        >>> mock = MockLLM(
        ...     static_response={
        ...         "decision": "skip",
        ...         "setup_quality": "B",
        ...         "confidence": 0.5,
        ...         "risk_flags": [],
        ...         "notes": "Mock response"
        ...     }
        ... )
        >>> result = mock.query({"user": "test"})

        >>> # Rule-based response
        >>> def custom_rule(payload):
        ...     if "breakout" in str(payload):
        ...         return {"decision": "take", "setup_quality": "A", ...}
        ...     return {"decision": "skip", "setup_quality": "C", ...}
        >>> mock = MockLLM(response_fn=custom_rule)
    """

    def __init__(
        self,
        static_response: Optional[Dict[str, Any]] = None,
        response_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        simulate_errors: bool = False,
        error_rate: float = 0.0,
        latency_ms: float = 0.0,
    ):
        """
        Initialize mock LLM.

        Args:
            static_response: Fixed response to return for all queries.
                If None, uses default "skip" response.
            response_fn: Custom function that takes payload and returns response dict.
                If provided, overrides static_response.
            simulate_errors: Whether to simulate API errors.
            error_rate: Probability of error (0.0 to 1.0). Only used if simulate_errors=True.
            latency_ms: Simulated latency in milliseconds.
        """
        self.static_response = static_response or self._default_response()
        self.response_fn = response_fn
        self.simulate_errors = simulate_errors
        self.error_rate = error_rate
        self.latency_ms = latency_ms

        # Tracking
        self.call_count = 0
        self.last_payload: Optional[Dict[str, Any]] = None

    def query(self, payload: Dict[str, Any]) -> str:
        """
        Query the mock LLM.

        Args:
            payload: LLM payload (usually with 'system' and 'user' keys).

        Returns:
            JSON string response.

        Raises:
            RuntimeError: If simulate_errors is True and error should occur.
        """
        self.call_count += 1
        self.last_payload = payload

        # Simulate error
        if self.simulate_errors:
            import random

            if random.random() < self.error_rate:
                raise RuntimeError("Mock LLM error (simulated)")

        # Simulate latency
        if self.latency_ms > 0:
            import time

            time.sleep(self.latency_ms / 1000.0)

        # Generate response
        if self.response_fn:
            response_dict = self.response_fn(payload)
        else:
            response_dict = self.static_response.copy()

        return json.dumps(response_dict, indent=2)

    def reset_stats(self) -> None:
        """Reset call statistics."""
        self.call_count = 0
        self.last_payload = None

    @staticmethod
    def _default_response() -> Dict[str, Any]:
        """Default conservative response."""
        return {
            "decision": "skip",
            "setup_quality": "C",
            "confidence": 0.5,
            "risk_flags": [],
            "notes": "Mock LLM response",
        }


class RuleBasedMockLLM(MockLLM):
    """
    Mock LLM with rule-based responses.

    Analyzes payload content to determine response.
    Useful for testing different scenarios.

    Example:
        >>> mock = RuleBasedMockLLM()
        >>> # Will return "take" for high quality setups
        >>> result = mock.query(payload_with_high_quality_setup)
    """

    def __init__(self, **kwargs):
        super().__init__(response_fn=self._rule_based_response, **kwargs)

    def _rule_based_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate response based on payload content.

        Rules:
        - If risk_mode is "risk_off": always skip
        - If playbook is "breakout" and volume confirms: likely take
        - If playbook is "pullback" and in uptrend: likely take
        - If high chop: skip
        - Default: skip
        """
        user_content = str(payload.get("user", ""))

        # Extract key indicators from prompt
        is_risk_off = "risk_off" in user_content.lower()
        is_breakout = "breakout" in user_content.lower()
        is_pullback = "pullback" in user_content.lower()
        has_volume = "volume: high" in user_content.lower() or "zscore_15m: 1" in user_content.lower()
        high_chop = "chop score: high" in user_content.lower()
        is_uptrend = "trend (1h): up" in user_content.lower()

        # Risk off: always skip
        if is_risk_off:
            return {
                "decision": "skip",
                "setup_quality": "C",
                "confidence": 0.8,
                "risk_flags": ["regime_mismatch"],
                "notes": "Risk-off regime, skip all setups",
            }

        # High chop: skip
        if high_chop:
            return {
                "decision": "skip",
                "setup_quality": "C",
                "confidence": 0.7,
                "risk_flags": ["high_chop"],
                "notes": "High chop environment, poor for directional trades",
            }

        # Breakout with volume: take
        if is_breakout and has_volume:
            return {
                "decision": "take",
                "setup_quality": "A",
                "confidence": 0.85,
                "risk_flags": [],
                "notes": "Strong breakout with volume confirmation",
            }

        # Pullback in uptrend: take
        if is_pullback and is_uptrend:
            return {
                "decision": "take",
                "setup_quality": "A",
                "confidence": 0.80,
                "risk_flags": [],
                "notes": "Clean pullback in established uptrend",
            }

        # Default: skip
        return {
            "decision": "skip",
            "setup_quality": "B",
            "confidence": 0.6,
            "risk_flags": ["weak_setup"],
            "notes": "Setup doesn't meet quality threshold",
        }


class PerfectMockLLM(MockLLM):
    """
    Mock LLM that always makes the "correct" decision.

    Useful for testing upper-bound system performance.
    Always returns high-quality "take" decisions.
    """

    def __init__(self, **kwargs):
        super().__init__(
            static_response={
                "decision": "take",
                "setup_quality": "A+",
                "confidence": 0.95,
                "risk_flags": [],
                "notes": "Perfect setup (mock)",
            },
            **kwargs,
        )


class PessimisticMockLLM(MockLLM):
    """
    Mock LLM that always skips.

    Useful for testing system behavior with no trades.
    """

    def __init__(self, **kwargs):
        super().__init__(
            static_response={
                "decision": "skip",
                "setup_quality": "C",
                "confidence": 0.9,
                "risk_flags": ["weak_setup", "regime_mismatch"],
                "notes": "Pessimistic filter (mock)",
            },
            **kwargs,
        )


def create_mock_response_for_testing(
    decision: str = "skip",
    quality: str = "B",
    confidence: float = 0.5,
    risk_flags: Optional[list] = None,
) -> LLMResponseV1:
    """
    Create a mock LLMResponseV1 for unit testing.

    Args:
        decision: "take" or "skip"
        quality: "A+", "A", "B", or "C"
        confidence: 0.0 to 1.0
        risk_flags: List of risk flags

    Returns:
        LLMResponseV1 instance.

    Example:
        >>> response = create_mock_response_for_testing("take", "A", 0.85)
        >>> assert response.decision == "take"
    """
    return LLMResponseV1(
        decision=decision,
        setup_quality=quality,
        confidence=confidence,
        risk_flags=risk_flags or [],
        notes="Mock response for testing",
    )
