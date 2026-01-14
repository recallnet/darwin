"""
Authentication router for Darwin API.

Provides endpoints for:
- User registration
- User login
- Team selection
- User info retrieval
"""

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from darwin.api.db import get_db, User, Team, TeamMember
from darwin.api.models.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserInfo,
    TeamSelectRequest,
    TeamInfo,
    UserWithTeamsResponse,
)
from darwin.api.middleware.auth import get_current_user
from darwin.api.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
)

router = APIRouter()


@router.post("/register", response_model=UserWithTeamsResponse, status_code=status.HTTP_201_CREATED)
async def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user.

    Creates a new user account. Does not automatically create a team -
    user must create a team or accept an invitation after registration.

    Args:
        request: User registration data
        db: Database session

    Returns:
        UserWithTeamsResponse: User info with empty teams list

    Raises:
        HTTPException: If email already exists
    """
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Hash password
    password_hash = hash_password(request.password)

    # Create user
    user = User(
        email=request.email,
        password_hash=password_hash,
        name=request.name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Return user info with empty teams
    user_info = UserInfo.model_validate(user)
    return UserWithTeamsResponse(user=user_info, teams=[])


@router.post("/login", response_model=TokenResponse)
async def login(request: UserLoginRequest, db: Session = Depends(get_db)):
    """
    Login and get access token.

    Returns a token with the user's first team. If user belongs to multiple teams,
    they can switch teams using the /auth/team/select endpoint.

    Args:
        request: Login credentials
        db: Database session

    Returns:
        TokenResponse: Access token and user/team info

    Raises:
        HTTPException: If credentials are invalid or user has no teams
    """
    # Get user by email
    user = db.query(User).filter(User.email == request.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # Get user's teams
    team_memberships = db.query(TeamMember).filter(TeamMember.user_id == user.id).all()
    if not team_memberships:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no team memberships. Please create a team or accept an invitation.",
        )

    # Use first team by default
    first_team_id = team_memberships[0].team_id

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    # Create access token
    token_data = {
        "sub": str(user.id),
        "team_id": str(first_team_id),
    }
    access_token = create_access_token(token_data)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        team_id=first_team_id,
    )


@router.post("/team/select", response_model=TokenResponse)
async def select_team(
    request: TeamSelectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Switch to a different team.

    Generates a new token with the selected team_id.

    Args:
        request: Team selection request
        current_user: Authenticated user
        db: Database session

    Returns:
        TokenResponse: New access token with selected team

    Raises:
        HTTPException: If user is not a member of the selected team
    """
    # Check if user is member of requested team
    team_member = (
        db.query(TeamMember)
        .filter(
            TeamMember.user_id == current_user.id, TeamMember.team_id == request.team_id
        )
        .first()
    )

    if team_member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of the selected team",
        )

    # Create new token with selected team
    token_data = {
        "sub": str(current_user.id),
        "team_id": str(request.team_id),
    }
    access_token = create_access_token(token_data)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=current_user.id,
        team_id=request.team_id,
    )


@router.get("/me", response_model=UserWithTeamsResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Get current user information with list of teams.

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        UserWithTeamsResponse: User info with list of teams
    """
    # Get user's team memberships
    team_memberships = (
        db.query(TeamMember, Team)
        .join(Team, TeamMember.team_id == Team.id)
        .filter(TeamMember.user_id == current_user.id)
        .all()
    )

    # Build teams list
    teams = [
        TeamInfo(
            id=team.id,
            name=team.name,
            slug=team.slug,
            role=membership.role,
        )
        for membership, team in team_memberships
    ]

    # Build response
    user_info = UserInfo.model_validate(current_user)
    return UserWithTeamsResponse(user=user_info, teams=teams)
