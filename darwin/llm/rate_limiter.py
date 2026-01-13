"""Rate limiter using token bucket algorithm.

Thread-safe rate limiting for LLM API calls.
"""

import threading
import time
from typing import Optional


class RateLimiter:
    """
    Token bucket rate limiter for API calls.

    Thread-safe implementation that blocks when rate limit is reached.
    Uses token bucket algorithm where tokens refill at a constant rate.

    Args:
        max_calls_per_minute: Maximum number of calls allowed per minute.
            Default is 60 (1 per second).
        burst_size: Maximum burst size (initial tokens). If None, defaults
            to max_calls_per_minute. Allows brief bursts above sustained rate.

    Example:
        >>> limiter = RateLimiter(max_calls_per_minute=30)
        >>> limiter.acquire()  # Blocks until token available
        >>> # Make API call here
    """

    def __init__(self, max_calls_per_minute: int = 60, burst_size: Optional[int] = None):
        if max_calls_per_minute <= 0:
            raise ValueError("max_calls_per_minute must be positive")

        self.max_calls_per_minute = max_calls_per_minute
        self.burst_size = burst_size if burst_size is not None else max_calls_per_minute

        # Token refill rate (tokens per second)
        self.refill_rate = max_calls_per_minute / 60.0

        # Current tokens available
        self._tokens = float(self.burst_size)

        # Last refill timestamp
        self._last_refill = time.time()

        # Lock for thread safety
        self._lock = threading.Lock()

    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire a token, blocking until one is available.

        Args:
            timeout: Maximum time to wait in seconds. If None, waits indefinitely.
                If timeout expires, returns False.

        Returns:
            True if token acquired, False if timeout expired.

        Raises:
            ValueError: If timeout is negative.
        """
        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be non-negative")

        start_time = time.time()

        while True:
            with self._lock:
                self._refill_tokens()

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True

            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False

            # Sleep briefly before retrying
            # Sleep for the time needed to accumulate 1 token, or 0.1s max
            sleep_time = min(1.0 / self.refill_rate, 0.1)
            time.sleep(sleep_time)

    def try_acquire(self) -> bool:
        """
        Try to acquire a token without blocking.

        Returns:
            True if token acquired, False otherwise.
        """
        with self._lock:
            self._refill_tokens()

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True

            return False

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time. Must be called with lock held."""
        now = time.time()
        elapsed = now - self._last_refill

        # Add tokens based on elapsed time
        new_tokens = elapsed * self.refill_rate
        self._tokens = min(self._tokens + new_tokens, float(self.burst_size))

        self._last_refill = now

    def get_available_tokens(self) -> float:
        """
        Get current number of available tokens.

        Returns:
            Number of tokens currently available.
        """
        with self._lock:
            self._refill_tokens()
            return self._tokens

    def reset(self) -> None:
        """Reset rate limiter to initial state with full tokens."""
        with self._lock:
            self._tokens = float(self.burst_size)
            self._last_refill = time.time()
