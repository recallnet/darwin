"""LLM harness with retry logic, circuit breaker, and rate limiting.

Wraps LLM calls with resilience patterns for production use.
"""

import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Protocol

from darwin.llm.parser import ParseResult, create_fallback_response, parse_llm_response
from darwin.llm.rate_limiter import RateLimiter
from darwin.schemas.llm_response import LLMResponseV1

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit tripped, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class LLMBackend(Protocol):
    """Protocol for LLM backend interface."""

    def query(self, payload: Dict[str, Any]) -> str:
        """Query the LLM with a payload, return raw response string."""
        ...


@dataclass
class LLMDecisionResult:
    """
    Result of LLM decision with metadata.

    Attributes:
        success: True if LLM call succeeded and response parsed.
        response: Parsed LLMResponseV1, or fallback if failed.
        fallback_used: True if fallback response was used due to error.
        error: Error message if call failed.
        retries: Number of retries attempted.
        latency_ms: Total latency in milliseconds.
        circuit_state: State of circuit breaker at call time.
    """

    success: bool
    response: LLMResponseV1
    fallback_used: bool
    error: Optional[str] = None
    retries: int = 0
    latency_ms: float = 0.0
    circuit_state: str = CircuitState.CLOSED


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.

    Opens after N consecutive failures, closes after successful test.
    """

    def __init__(self, threshold: int = 5, timeout_seconds: float = 60.0):
        """
        Initialize circuit breaker.

        Args:
            threshold: Number of consecutive failures before opening.
            timeout_seconds: Seconds to wait before attempting half-open test.
        """
        self.threshold = threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time: Optional[float] = None

    def record_success(self) -> None:
        """Record a successful call."""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker: Half-open test succeeded, closing circuit")
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.threshold and self.state == CircuitState.CLOSED:
            logger.warning(
                f"Circuit breaker: Opening after {self.failure_count} consecutive failures"
            )
            self.state = CircuitState.OPEN

    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        if self.state == CircuitState.OPEN:
            # Check if we should attempt half-open
            if (
                self.last_failure_time
                and time.time() - self.last_failure_time > self.timeout_seconds
            ):
                logger.info("Circuit breaker: Attempting half-open test")
                self.state = CircuitState.HALF_OPEN
                return False
            return True
        return False

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = None


class LLMHarnessWithRetry:
    """
    LLM harness with retry logic, circuit breaker, and rate limiting.

    Features:
    - Exponential backoff with jitter on 429/5xx errors
    - Circuit breaker pattern (opens after N consecutive failures)
    - Rate limiting integration
    - Fallback decisions on persistent failures
    - Comprehensive error handling

    Example:
        >>> from darwin.llm.mock import MockLLM
        >>> backend = MockLLM()
        >>> harness = LLMHarnessWithRetry(
        ...     backend=backend,
        ...     max_retries=3,
        ...     rate_limiter=RateLimiter(max_calls_per_minute=30)
        ... )
        >>> result = harness.query({"user": "test prompt"})
        >>> if result.success:
        ...     print(f"Decision: {result.response.decision}")
    """

    def __init__(
        self,
        backend: LLMBackend,
        max_retries: int = 3,
        initial_retry_delay: float = 1.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
        fallback_decision: str = "skip",
        rate_limiter: Optional[RateLimiter] = None,
    ):
        """
        Initialize LLM harness.

        Args:
            backend: LLM backend implementing query(payload) -> str.
            max_retries: Maximum retry attempts (default: 3).
            initial_retry_delay: Initial delay between retries in seconds (default: 1.0).
            circuit_breaker_threshold: Failures before circuit opens (default: 5).
            circuit_breaker_timeout: Seconds before half-open test (default: 60.0).
            fallback_decision: Default decision on failure ("skip" or "take", default: "skip").
            rate_limiter: Optional RateLimiter instance. If None, no rate limiting.
        """
        self.backend = backend
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self.fallback_decision = fallback_decision
        self.rate_limiter = rate_limiter

        self.circuit_breaker = CircuitBreaker(
            threshold=circuit_breaker_threshold, timeout_seconds=circuit_breaker_timeout
        )

        # Statistics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.total_retries = 0

    def query(self, payload: Dict[str, Any]) -> LLMDecisionResult:
        """
        Query LLM with retry logic and circuit breaker.

        Args:
            payload: LLM payload dict (typically with 'system' and 'user' keys).

        Returns:
            LLMDecisionResult with response and metadata.
        """
        self.total_calls += 1
        start_time = time.time()

        # Check circuit breaker
        if self.circuit_breaker.is_open():
            logger.warning("Circuit breaker open, using fallback decision")
            return self._create_fallback_result(
                "Circuit breaker open", CircuitState.OPEN, start_time
            )

        # Try with retries
        last_error: Optional[str] = None
        for attempt in range(self.max_retries + 1):
            try:
                # Rate limiting
                if self.rate_limiter:
                    acquired = self.rate_limiter.acquire(timeout=30.0)
                    if not acquired:
                        raise RuntimeError("Rate limiter timeout (30s)")

                # Make LLM call
                raw_response = self.backend.query(payload)

                # Parse response
                parse_result = parse_llm_response(raw_response)

                if parse_result.success:
                    # Success!
                    self.circuit_breaker.record_success()
                    self.successful_calls += 1
                    self.total_retries += attempt

                    latency_ms = (time.time() - start_time) * 1000
                    return LLMDecisionResult(
                        success=True,
                        response=parse_result.response,
                        fallback_used=False,
                        error=None,
                        retries=attempt,
                        latency_ms=latency_ms,
                        circuit_state=self.circuit_breaker.state,
                    )
                else:
                    # Parse failed, treat as error
                    last_error = f"Parse error: {parse_result.error}"
                    logger.warning(f"Attempt {attempt + 1}: {last_error}")

            except Exception as e:
                last_error = f"{type(e).__name__}: {str(e)}"
                logger.warning(f"Attempt {attempt + 1}: {last_error}")

            # If we have more attempts, retry with backoff
            if attempt < self.max_retries:
                delay = self._calculate_retry_delay(attempt)
                logger.info(f"Retrying in {delay:.2f}s...")
                time.sleep(delay)

        # All retries exhausted
        logger.error(f"All {self.max_retries + 1} attempts failed: {last_error}")
        self.circuit_breaker.record_failure()
        self.failed_calls += 1
        self.total_retries += self.max_retries

        return self._create_fallback_result(
            last_error or "Unknown error", self.circuit_breaker.state, start_time
        )

    def _calculate_retry_delay(self, attempt: int) -> float:
        """
        Calculate retry delay with exponential backoff and jitter.

        Args:
            attempt: Current attempt number (0-indexed).

        Returns:
            Delay in seconds.
        """
        # Exponential backoff: delay = initial * (2 ^ attempt)
        base_delay = self.initial_retry_delay * (2**attempt)

        # Add jitter: randomize ±25%
        jitter = random.uniform(0.75, 1.25)
        delay = base_delay * jitter

        # Cap at 30 seconds
        return min(delay, 30.0)

    def _create_fallback_result(
        self, error: str, circuit_state: CircuitState, start_time: float
    ) -> LLMDecisionResult:
        """Create fallback result on error."""
        fallback_response = create_fallback_response(
            decision=self.fallback_decision, reason=error
        )

        latency_ms = (time.time() - start_time) * 1000

        return LLMDecisionResult(
            success=False,
            response=fallback_response,
            fallback_used=True,
            error=error,
            retries=self.max_retries,
            latency_ms=latency_ms,
            circuit_state=circuit_state,
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get harness statistics.

        Returns:
            Dictionary with call statistics and circuit breaker state.
        """
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": (
                self.successful_calls / self.total_calls if self.total_calls > 0 else 0.0
            ),
            "total_retries": self.total_retries,
            "avg_retries_per_call": (
                self.total_retries / self.total_calls if self.total_calls > 0 else 0.0
            ),
            "circuit_breaker_state": self.circuit_breaker.state,
            "circuit_breaker_failures": self.circuit_breaker.failure_count,
        }

    def reset_stats(self) -> None:
        """Reset statistics (useful for testing)."""
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.total_retries = 0
        self.circuit_breaker.reset()

    def reset_circuit_breaker(self) -> None:
        """Manually reset circuit breaker."""
        self.circuit_breaker.reset()
        logger.info("Circuit breaker manually reset")
