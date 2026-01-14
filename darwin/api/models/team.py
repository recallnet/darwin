"""
Pydantic models for team management API.

Defines request and response schemas for:
- Team creation
- Team updates
- Team info
- Team members
- Team invitations
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, ConfigDict
import re


class TeamCreateRequest(BaseModel):
    """Request model for team creation."""

    name: str = Field(..., min_length=1, max_length=255, description="Team name")
    slug: str = Field(
        ..., min_length=1, max_length=100, description="URL-safe team slug (lowercase, hyphens)"
    )

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Validate slug is URL-safe."""
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("Slug must contain only lowercase letters, numbers, and hyphens")
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Slug cannot start or end with a hyphen")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "My Trading Team",
                "slug": "my-trading-team",
            }
        }
    )


class TeamUpdateRequest(BaseModel):
    """Request model for team updates."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Team name")
    slug: Optional[str] = Field(
        None, min_length=1, max_length=100, description="URL-safe team slug"
    )

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        """Validate slug is URL-safe."""
        if v is None:
            return v
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("Slug must contain only lowercase letters, numbers, and hyphens")
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Slug cannot start or end with a hyphen")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated Team Name",
            }
        }
    )


class TeamResponse(BaseModel):
    """Response model for team information."""

    id: UUID = Field(..., description="Team ID")
    name: str = Field(..., description="Team name")
    slug: str = Field(..., description="Team slug")
    created_at: datetime = Field(..., description="Team creation timestamp")
    created_by: Optional[UUID] = Field(None, description="User ID of team creator")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "660e8400-e29b-41d4-a716-446655440001",
                "name": "My Trading Team",
                "slug": "my-trading-team",
                "created_at": "2024-01-15T10:30:00Z",
                "created_by": "550e8400-e29b-41d4-a716-446655440000",
            }
        },
    )


class TeamMemberResponse(BaseModel):
    """Response model for team member information."""

    user_id: UUID = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    name: Optional[str] = Field(None, description="User name")
    role: str = Field(..., description="Member role (admin, member, viewer)")
    joined_at: datetime = Field(..., description="Membership start timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "user@example.com",
                "name": "John Doe",
                "role": "admin",
                "joined_at": "2024-01-15T10:30:00Z",
            }
        }
    )


class TeamWithMembersResponse(BaseModel):
    """Response model for team with members list."""

    team: TeamResponse = Field(..., description="Team information")
    members: list[TeamMemberResponse] = Field(..., description="List of team members")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "team": {
                    "id": "660e8400-e29b-41d4-a716-446655440001",
                    "name": "My Trading Team",
                    "slug": "my-trading-team",
                    "created_at": "2024-01-15T10:30:00Z",
                    "created_by": "550e8400-e29b-41d4-a716-446655440000",
                },
                "members": [
                    {
                        "user_id": "550e8400-e29b-41d4-a716-446655440000",
                        "email": "admin@example.com",
                        "name": "Admin User",
                        "role": "admin",
                        "joined_at": "2024-01-15T10:30:00Z",
                    }
                ],
            }
        }
    )


class UpdateMemberRoleRequest(BaseModel):
    """Request model for updating member role."""

    role: str = Field(..., description="New role (admin, member, viewer)")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role is valid."""
        if v not in ["admin", "member", "viewer"]:
            raise ValueError("Role must be 'admin', 'member', or 'viewer'")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "role": "member",
            }
        }
    )


class SendInvitationRequest(BaseModel):
    """Request model for sending team invitation."""

    email: str = Field(..., description="Email address to send invitation to")
    role: str = Field(..., description="Role to assign (admin, member, viewer)")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role is valid."""
        if v not in ["admin", "member", "viewer"]:
            raise ValueError("Role must be 'admin', 'member', or 'viewer'")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "newmember@example.com",
                "role": "member",
            }
        }
    )


class InvitationResponse(BaseModel):
    """Response model for invitation information."""

    id: UUID = Field(..., description="Invitation ID")
    team_id: UUID = Field(..., description="Team ID")
    email: str = Field(..., description="Invitee email")
    role: str = Field(..., description="Role to be assigned")
    invited_by: Optional[UUID] = Field(None, description="User ID of inviter")
    invited_at: datetime = Field(..., description="Invitation timestamp")
    expires_at: datetime = Field(..., description="Expiration timestamp")
    accepted_at: Optional[datetime] = Field(None, description="Acceptance timestamp")
    token: str = Field(..., description="Invitation token")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "770e8400-e29b-41d4-a716-446655440002",
                "team_id": "660e8400-e29b-41d4-a716-446655440001",
                "email": "newmember@example.com",
                "role": "member",
                "invited_by": "550e8400-e29b-41d4-a716-446655440000",
                "invited_at": "2024-01-20T10:00:00Z",
                "expires_at": "2024-01-27T10:00:00Z",
                "accepted_at": None,
                "token": "a1b2c3d4e5f6...",
            }
        },
    )


class AcceptInvitationRequest(BaseModel):
    """Request model for accepting invitation (public endpoint)."""

    token: str = Field(..., description="Invitation token")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "token": "a1b2c3d4e5f6...",
            }
        }
    )
