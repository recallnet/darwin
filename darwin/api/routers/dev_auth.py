"""
Development-only authentication bypass for testing.

WARNING: This router provides mock authentication for development/testing only.
DO NOT use in production. Remove this file before deploying.
"""

from fastapi import APIRouter
from darwin.api.models.auth import UserLoginRequest, TokenResponse
from darwin.api.utils.security import create_access_token
from uuid import uuid4

router = APIRouter()

# Mock user data for development
MOCK_USER_ID = "00000000-0000-0000-0000-000000000001"
MOCK_TEAM_ID = "00000000-0000-0000-0000-000000000002"

@router.post("/dev-login", response_model=TokenResponse)
async def dev_login(request: UserLoginRequest):
    """
    Development-only login endpoint that bypasses database.

    Accepts any email/password combination and returns a valid token.
    Use this for testing the frontend without database setup.

    Returns:
        TokenResponse: Access token with mock user/team
    """
    # Create access token with mock data
    token_data = {
        "sub": MOCK_USER_ID,
        "team_id": MOCK_TEAM_ID,
    }
    access_token = create_access_token(token_data)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=MOCK_USER_ID,
        team_id=MOCK_TEAM_ID,
    )
