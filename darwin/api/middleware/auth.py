"""
Authentication middleware for Darwin API.

Provides dependencies for:
- Token verification
- User authentication
- Team access control
- Role-based permissions
"""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from darwin.api.db import get_db, User, Team, TeamMember
from darwin.api.utils.security import decode_access_token

# HTTP Bearer token security scheme
security = HTTPBearer()


class AuthContext:
    """
    Authentication context containing user and team information.

    Attributes:
        user: Authenticated user
        team: Current team
        team_member: Team membership record (includes role)
    """

    def __init__(self, user: User, team: Team, team_member: TeamMember):
        self.user = user
        self.team = team
        self.team_member = team_member

    @property
    def user_id(self) -> UUID:
        """Get user ID."""
        return self.user.id

    @property
    def team_id(self) -> UUID:
        """Get team ID."""
        return self.team.id

    @property
    def role(self) -> str:
        """Get user's role in current team."""
        return self.team_member.role

    def is_admin(self) -> bool:
        """Check if user is admin in current team."""
        return self.role == "admin"

    def is_member(self) -> bool:
        """Check if user is at least a member (admin or member)."""
        return self.role in ["admin", "member"]

    def is_viewer(self) -> bool:
        """Check if user has any access (admin, member, or viewer)."""
        return self.role in ["admin", "member", "viewer"]


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency to get current authenticated user.

    Args:
        credentials: HTTP Bearer token
        db: Database session

    Returns:
        User: Authenticated user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials

    # Decode token
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user ID
    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


async def get_auth_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> AuthContext:
    """
    Dependency to get full authentication context (user + team).

    Requires team_id in JWT token payload.

    Args:
        credentials: HTTP Bearer token
        db: Database session

    Returns:
        AuthContext: Authentication context with user, team, and role

    Raises:
        HTTPException: If token is invalid, team not found, or user not member
    """
    token = credentials.credentials

    # Decode token
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user ID and team ID
    user_id_str = payload.get("sub")
    team_id_str = payload.get("team_id")

    if user_id_str is None or team_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = UUID(user_id_str)
        team_id = UUID(team_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid ID format in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # Get team
    team = db.query(Team).filter(Team.id == team_id).first()
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Get team membership
    team_member = (
        db.query(TeamMember)
        .filter(TeamMember.user_id == user_id, TeamMember.team_id == team_id)
        .first()
    )
    if team_member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this team",
        )

    return AuthContext(user=user, team=team, team_member=team_member)


async def require_admin(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    """
    Dependency to require admin role.

    Args:
        auth: Authentication context

    Returns:
        AuthContext: Authentication context (if admin)

    Raises:
        HTTPException: If user is not admin
    """
    if not auth.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required for this operation",
        )
    return auth


async def require_member(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    """
    Dependency to require member role (admin or member).

    Args:
        auth: Authentication context

    Returns:
        AuthContext: Authentication context (if member or admin)

    Raises:
        HTTPException: If user is not member or admin
    """
    if not auth.is_member():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Member role required for this operation",
        )
    return auth


async def require_viewer(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    """
    Dependency to require any team access (admin, member, or viewer).

    Args:
        auth: Authentication context

    Returns:
        AuthContext: Authentication context (if has any access)

    Raises:
        HTTPException: If user does not have team access
    """
    if not auth.is_viewer():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team access required for this operation",
        )
    return auth
