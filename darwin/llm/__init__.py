"""Darwin LLM module - Rate limiting, retry logic, and prompt engineering.

This module provides:
- Rate limiting with token bucket algorithm
- Retry logic with exponential backoff and circuit breaker
- Structured prompt engineering with versioning
- Response parsing and validation
- Mock LLM backends for testing

Example usage:
    >>> from darwin.llm import LLMHarnessWithRetry, RateLimiter, LLMPromptV1
    >>> from darwin.llm.mock import MockLLM
    >>>
    >>> # Create backend and harness
    >>> backend = MockLLM()
    >>> rate_limiter = RateLimiter(max_calls_per_minute=30)
    >>> harness = LLMHarnessWithRetry(
    ...     backend=backend,
    ...     rate_limiter=rate_limiter,
    ...     max_retries=3
    ... )
    >>>
    >>> # Build prompt
    >>> payload = LLMPromptV1.build_payload(context)
    >>>
    >>> # Query LLM
    >>> result = harness.query(payload)
    >>> if result.success:
    ...     print(f"Decision: {result.response.decision}")
"""

# Core components
from darwin.llm.harness import (
    CircuitBreaker,
    CircuitState,
    LLMBackend,
    LLMDecisionResult,
    LLMHarnessWithRetry,
)
from darwin.llm.parser import (
    ParseResult,
    create_fallback_response,
    parse_llm_response,
    validate_response_completeness,
)
from darwin.llm.prompts import LLMPromptV1, build_context_from_payload
from darwin.llm.rate_limiter import RateLimiter

# Mock implementations
from darwin.llm.mock import (
    MockLLM,
    PerfectMockLLM,
    PessimisticMockLLM,
    RuleBasedMockLLM,
    create_mock_response_for_testing,
)

__all__ = [
    # Harness
    "LLMHarnessWithRetry",
    "LLMDecisionResult",
    "LLMBackend",
    "CircuitBreaker",
    "CircuitState",
    # Rate limiting
    "RateLimiter",
    # Prompts
    "LLMPromptV1",
    "build_context_from_payload",
    # Parsing
    "parse_llm_response",
    "ParseResult",
    "create_fallback_response",
    "validate_response_completeness",
    # Mock LLMs
    "MockLLM",
    "RuleBasedMockLLM",
    "PerfectMockLLM",
    "PessimisticMockLLM",
    "create_mock_response_for_testing",
]
