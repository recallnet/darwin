"""
Pydantic models for authentication API.

Defines request and response schemas for:
- User registration
- User login
- Token responses
- User info
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserRegisterRequest(BaseModel):
    """Request model for user registration."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password (min 8 characters)")
    name: Optional[str] = Field(None, description="User full name")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "securepassword123",
                "name": "John Doe",
            }
        }
    )


class UserLoginRequest(BaseModel):
    """Request model for user login."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "securepassword123",
            }
        }
    )


class TokenResponse(BaseModel):
    """Response model for authentication tokens."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    user_id: UUID = Field(..., description="User ID")
    team_id: Optional[UUID] = Field(None, description="Current team ID")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "team_id": "660e8400-e29b-41d4-a716-446655440001",
            }
        }
    )


class UserInfo(BaseModel):
    """Response model for user information."""

    id: UUID = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    name: Optional[str] = Field(None, description="User full name")
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    is_active: bool = Field(..., description="Account active status")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "user@example.com",
                "name": "John Doe",
                "created_at": "2024-01-15T10:30:00Z",
                "last_login": "2024-01-20T14:15:00Z",
                "is_active": True,
            }
        },
    )


class TeamSelectRequest(BaseModel):
    """Request model for selecting a team (after login)."""

    team_id: UUID = Field(..., description="Team ID to switch to")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "team_id": "660e8400-e29b-41d4-a716-446655440001",
            }
        }
    )


class TeamInfo(BaseModel):
    """Response model for team information."""

    id: UUID = Field(..., description="Team ID")
    name: str = Field(..., description="Team name")
    slug: str = Field(..., description="Team slug")
    role: str = Field(..., description="User's role in team")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "660e8400-e29b-41d4-a716-446655440001",
                "name": "My Trading Team",
                "slug": "my-trading-team",
                "role": "admin",
            }
        }
    )


class UserWithTeamsResponse(BaseModel):
    """Response model for user info with list of teams."""

    user: UserInfo = Field(..., description="User information")
    teams: list[TeamInfo] = Field(..., description="List of teams user belongs to")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "user@example.com",
                    "name": "John Doe",
                    "created_at": "2024-01-15T10:30:00Z",
                    "last_login": "2024-01-20T14:15:00Z",
                    "is_active": True,
                },
                "teams": [
                    {
                        "id": "660e8400-e29b-41d4-a716-446655440001",
                        "name": "My Trading Team",
                        "slug": "my-trading-team",
                        "role": "admin",
                    }
                ],
            }
        }
    )
