"""LLM backend creation and configuration.

This module provides utilities to create LLM backends using Vercel AI Gateway directly.
"""

import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class LLMBackendError(Exception):
    """Raised when LLM backend cannot be created."""
    pass


def create_llm_backend(
    provider: str = "anthropic",
    model: str = "google/gemini-3-pro-preview",
    api_key: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 1000,
    use_mock: bool = False,
) -> Any:
    """
    Create an LLM backend using Vercel AI Gateway directly.

    Args:
        provider: LLM provider (deprecated - use model format provider/model-name)
        model: Model ID in format provider/model-name (e.g., "google/gemini-3-pro-preview")
        api_key: API key (not used - reads from AI_GATEWAY_API_KEY env var)
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response
        use_mock: Force use of mock LLM

    Returns:
        LLM backend implementing query(payload) -> str

    Raises:
        LLMBackendError: If AI Gateway is not configured and use_mock=False

    Example:
        >>> backend = create_llm_backend(model="google/gemini-3-pro-preview")
        >>> response = backend.query({"user": "Hello"})
    """
    if use_mock or provider == "mock":
        logger.info("Using mock LLM backend")
        from darwin.llm.mock import RuleBasedMockLLM
        return RuleBasedMockLLM()

    # Require AI Gateway configuration
    gateway_url = os.getenv("AI_GATEWAY_BASE_URL")
    gateway_key = os.getenv("AI_GATEWAY_API_KEY")

    if not gateway_url or not gateway_key:
        raise LLMBackendError(
            "AI Gateway not configured.\n\n"
            "Set these environment variables in your .env file:\n"
            "  AI_GATEWAY_BASE_URL=https://ai-gateway.vercel.sh/v1\n"
            "  AI_GATEWAY_API_KEY=your-key-here\n\n"
            "Alternatively, use --use-mock flag to use mock LLM for testing."
        )

    # Create AI Gateway backend
    backend = _create_ai_gateway_backend(
        gateway_url, gateway_key, model, temperature, max_tokens
    )

    return backend


def _is_reasoning_model(model: str) -> bool:
    """Check if a model is a reasoning model that needs extra tokens."""
    reasoning_keywords = [
        "o1",  # OpenAI o1
        "gemini-3",  # Gemini 3 Pro
        "reasoner",  # DeepSeek Reasoner
        "reasoning",  # Any model with "reasoning" in name
        "grok-4",  # Grok 4 reasoning models
    ]
    model_lower = model.lower()
    return any(keyword in model_lower for keyword in reasoning_keywords)


def _create_ai_gateway_backend(
    base_url: str,
    api_key: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> Any:
    """
    Create Vercel AI Gateway backend.

    Args:
        base_url: Base URL of AI Gateway (e.g., https://ai-gateway.vercel.sh/v1)
        api_key: AI Gateway API key
        model: Model ID in format provider/model-name
        temperature: Sampling temperature
        max_tokens: Maximum tokens

    Returns:
        Backend implementing query(payload) -> str
    """
    # Automatically increase max_tokens for reasoning models
    if _is_reasoning_model(model) and max_tokens < 4000:
        original_max_tokens = max_tokens
        max_tokens = max(4000, max_tokens)
        logger.info(
            f"Reasoning model detected ({model}). Increased max_tokens from "
            f"{original_max_tokens} to {max_tokens} to accommodate thinking tokens."
        )

    logger.info(f"Using Vercel AI Gateway at {base_url} with model {model}")

    class AIGatewayBackend:
        """Wrapper for Vercel AI Gateway."""

        def __init__(
            self,
            base_url: str,
            api_key: str,
            model: str,
            temperature: float,
            max_tokens: int,
        ):
            self.base_url = base_url.rstrip('/')
            self.api_key = api_key
            self.model = model
            self.temperature = temperature
            self.max_tokens = max_tokens

        def query(self, payload: Dict[str, Any]) -> str:
            """
            Query AI Gateway using OpenAI-compatible chat completions format.

            The AI Gateway supports the standard OpenAI format:
            POST /v1/chat/completions
            """
            # Build messages array
            messages = []

            # Add system message if present
            if "system" in payload and payload["system"]:
                messages.append({
                    "role": "system",
                    "content": payload["system"]
                })

            # Add user message
            if "user" in payload:
                messages.append({
                    "role": "user",
                    "content": payload["user"]
                })

            # Build request in OpenAI chat completions format
            request_data = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }

            # Make HTTP request to AI Gateway
            try:
                response = httpx.post(
                    f"{self.base_url}/chat/completions",
                    json=request_data,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=60.0,
                )
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise LLMBackendError(
                    f"AI Gateway request failed: {e}\n"
                    f"URL: {self.base_url}/chat/completions\n"
                    f"Model: {self.model}\n"
                    f"Check your AI_GATEWAY_BASE_URL and AI_GATEWAY_API_KEY"
                )

            # Parse response
            try:
                data = response.json()
            except ValueError as e:
                raise LLMBackendError(f"Invalid JSON response from AI Gateway: {e}")

            # Extract message from OpenAI-compatible response
            if "choices" not in data or len(data["choices"]) == 0:
                raise LLMBackendError(f"Unexpected response format: {data}")

            choice = data["choices"][0]
            message = choice.get("message", {})
            content = message.get("content", "")

            # Handle reasoning models that may return empty content with finish_reason='length'
            # This happens when reasoning tokens consume all max_tokens
            if not content:
                finish_reason = choice.get("finish_reason")
                usage = data.get("usage", {})
                reasoning_tokens = usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)

                if finish_reason == "length" and reasoning_tokens > 0:
                    raise LLMBackendError(
                        f"Reasoning model hit token limit. Model used {reasoning_tokens} reasoning tokens "
                        f"but max_tokens={self.max_tokens} was too low. Increase max_tokens to at least "
                        f"{reasoning_tokens + 50} for this model."
                    )

                raise LLMBackendError(
                    f"Empty response from LLM. Finish reason: {finish_reason}\n"
                    f"Response: {data}"
                )

            return content

    return AIGatewayBackend(base_url, api_key, model, temperature, max_tokens)
