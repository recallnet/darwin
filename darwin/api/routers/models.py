"""
Models router for Darwin API.

Provides endpoints for listing available LLM models from Vercel AI Gateway.
"""

from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ModelInfo(BaseModel):
    """Model information."""

    value: str  # Format: "provider/model"
    label: str
    provider: str
    description: str


class ModelsListResponse(BaseModel):
    """Response for models list."""

    models: List[ModelInfo]
    default_model: str


@router.get("/", response_model=ModelsListResponse)
async def list_models():
    """
    List all available LLM models from Vercel AI Gateway.

    Returns models with their display labels and metadata.
    The list is sourced from Vercel AI Gateway's model catalog.

    Returns:
        ModelsListResponse: List of available models with default
    """
    # TODO: In future, fetch this dynamically from Vercel AI Gateway API
    # For now, return the curated list based on platform configuration

    models = [
        ModelInfo(
            value="google/gemini-3-flash",
            label="Google - Gemini 3 Flash (Recommended)",
            provider="google",
            description="Pro-level reasoning at Flash speed - fast, reliable, and cost-effective"
        ),
        ModelInfo(
            value="google/gemini-3-pro-preview",
            label="Google - Gemini 3 Pro Preview (Reasoning Model)",
            provider="google",
            description="Extended reasoning with thinking tokens - slower but most thorough"
        ),
        ModelInfo(
            value="anthropic/claude-sonnet-4-5",
            label="Anthropic - Claude Sonnet 4.5",
            provider="anthropic",
            description="Best quality and most reliable, highest accuracy"
        ),
        ModelInfo(
            value="google/gemini-2.0-flash",
            label="Google - Gemini 2.0 Flash",
            provider="google",
            description="Fast and cheap with good performance"
        ),
        ModelInfo(
            value="deepseek/deepseek-v3.2",
            label="DeepSeek - V3.2",
            provider="deepseek",
            description="Very cheap, good for high-volume testing"
        ),
        ModelInfo(
            value="anthropic/claude-3-opus-20240229",
            label="Anthropic - Claude 3 Opus",
            provider="anthropic",
            description="Previous generation flagship model"
        ),
        ModelInfo(
            value="anthropic/claude-3-sonnet-20240229",
            label="Anthropic - Claude 3 Sonnet",
            provider="anthropic",
            description="Balanced performance and cost"
        ),
        ModelInfo(
            value="anthropic/claude-3-haiku-20240307",
            label="Anthropic - Claude 3 Haiku",
            provider="anthropic",
            description="Fast and economical"
        ),
        ModelInfo(
            value="openai/gpt-4-turbo-preview",
            label="OpenAI - GPT-4 Turbo",
            provider="openai",
            description="Latest GPT-4 with extended context"
        ),
        ModelInfo(
            value="openai/gpt-4",
            label="OpenAI - GPT-4",
            provider="openai",
            description="Reliable GPT-4 baseline"
        ),
        ModelInfo(
            value="openai/gpt-3.5-turbo",
            label="OpenAI - GPT-3.5 Turbo",
            provider="openai",
            description="Fast and economical"
        ),
    ]

    return ModelsListResponse(
        models=models,
        default_model="google/gemini-3-flash"
    )
