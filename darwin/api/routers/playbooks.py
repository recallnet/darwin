"""
Playbooks router for Darwin API.

Provides endpoints for listing available trading strategy playbooks.
"""

from typing import List
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class PlaybookInfo(BaseModel):
    """Playbook information."""

    id: str
    name: str
    description: str


class PlaybooksListResponse(BaseModel):
    """Response for playbooks list."""

    playbooks: List[PlaybookInfo]


@router.get("/", response_model=PlaybooksListResponse)
async def list_playbooks():
    """
    List all available strategy playbooks.

    Returns playbooks with their display information.
    The list reflects actual playbook implementations in the codebase.

    Returns:
        PlaybooksListResponse: List of available playbooks
    """
    playbooks = [
        PlaybookInfo(
            id="breakout",
            name="Breakout",
            description="Trade continuation when price breaks a well-defined recent range with trend + volume confirmation"
        ),
        PlaybookInfo(
            id="pullback",
            name="Pullback",
            description="In an uptrend, buy the dip when price pulls back to a moving average and resumes upward momentum"
        ),
    ]

    return PlaybooksListResponse(playbooks=playbooks)
