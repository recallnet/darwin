"""
Teams router for Darwin API.

Provides endpoints for:
- Team creation
- Team info retrieval
- Team updates
- Team deletion
- Member management
- Team invitations
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from datetime import datetime, timedelta

from darwin.api.db import get_db, User, Team, TeamMember, TeamInvitation
from darwin.api.models.team import (
    TeamCreateRequest,
    TeamUpdateRequest,
    TeamResponse,
    TeamMemberResponse,
    TeamWithMembersResponse,
    UpdateMemberRoleRequest,
    SendInvitationRequest,
    InvitationResponse,
    AcceptInvitationRequest,
)
from darwin.api.utils.security import create_invitation_token
from darwin.api.middleware.auth import (
    get_current_user,
    get_auth_context,
    require_admin,
    AuthContext,
)

router = APIRouter()


@router.post("/", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    request: TeamCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new team.

    The creating user automatically becomes an admin of the team.

    Args:
        request: Team creation data
        current_user: Authenticated user
        db: Database session

    Returns:
        TeamResponse: Created team information

    Raises:
        HTTPException: If slug already exists
    """
    # Check if slug already exists
    existing_team = db.query(Team).filter(Team.slug == request.slug).first()
    if existing_team:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Team with slug '{request.slug}' already exists",
        )

    # Create team
    team = Team(
        name=request.name,
        slug=request.slug,
        created_by=current_user.id,
    )
    db.add(team)
    db.flush()  # Get team.id without committing

    # Add creator as admin
    team_member = TeamMember(
        team_id=team.id,
        user_id=current_user.id,
        role="admin",
    )
    db.add(team_member)
    db.commit()
    db.refresh(team)

    return TeamResponse.model_validate(team)


@router.get("/{team_id}", response_model=TeamWithMembersResponse)
async def get_team(
    team_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get team information with members list.

    User must be a member of the team to view it.

    Args:
        team_id: Team ID
        auth: Authentication context
        db: Database session

    Returns:
        TeamWithMembersResponse: Team info with members

    Raises:
        HTTPException: If team not found or user not a member
    """
    # Verify team ID matches current team in auth context
    if auth.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view teams you are a member of",
        )

    # Get team with members
    team = db.query(Team).filter(Team.id == team_id).first()
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Get members
    members_query = (
        db.query(TeamMember, User)
        .join(User, TeamMember.user_id == User.id)
        .filter(TeamMember.team_id == team_id)
        .all()
    )

    members = [
        TeamMemberResponse(
            user_id=user.id,
            email=user.email,
            name=user.name,
            role=membership.role,
            joined_at=membership.joined_at,
        )
        for membership, user in members_query
    ]

    team_response = TeamResponse.model_validate(team)
    return TeamWithMembersResponse(team=team_response, members=members)


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: UUID,
    request: TeamUpdateRequest,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Update team information.

    Only admins can update team settings.

    Args:
        team_id: Team ID
        request: Team update data
        auth: Authentication context (requires admin)
        db: Database session

    Returns:
        TeamResponse: Updated team information

    Raises:
        HTTPException: If team not found, user not admin, or slug already exists
    """
    # Verify team ID matches current team in auth context
    if auth.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your current team",
        )

    # Get team
    team = db.query(Team).filter(Team.id == team_id).first()
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Update fields
    if request.name is not None:
        team.name = request.name

    if request.slug is not None:
        # Check if new slug already exists
        existing_team = (
            db.query(Team).filter(Team.slug == request.slug, Team.id != team_id).first()
        )
        if existing_team:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Team with slug '{request.slug}' already exists",
            )
        team.slug = request.slug

    db.commit()
    db.refresh(team)

    return TeamResponse.model_validate(team)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: UUID,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Delete a team.

    Only admins can delete teams. This will also delete all team members,
    invitations, and run metadata.

    Args:
        team_id: Team ID
        auth: Authentication context (requires admin)
        db: Database session

    Raises:
        HTTPException: If team not found or user not admin
    """
    # Verify team ID matches current team in auth context
    if auth.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your current team",
        )

    # Get team
    team = db.query(Team).filter(Team.id == team_id).first()
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Delete team (cascade will delete members, invitations, runs)
    db.delete(team)
    db.commit()


@router.put("/{team_id}/members/{user_id}/role", response_model=TeamMemberResponse)
async def update_member_role(
    team_id: UUID,
    user_id: UUID,
    request: UpdateMemberRoleRequest,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Update a team member's role.

    Only admins can change member roles.

    Args:
        team_id: Team ID
        user_id: User ID of member to update
        request: New role
        auth: Authentication context (requires admin)
        db: Database session

    Returns:
        TeamMemberResponse: Updated member info

    Raises:
        HTTPException: If team/member not found or user not admin
    """
    # Verify team ID matches current team in auth context
    if auth.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage members of your current team",
        )

    # Get team member
    team_member = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
        .first()
    )
    if team_member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    # Prevent self-demotion from admin if they're the last admin
    if user_id == auth.user_id and request.role != "admin":
        admin_count = (
            db.query(TeamMember)
            .filter(TeamMember.team_id == team_id, TeamMember.role == "admin")
            .count()
        )
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last admin. Promote another member first.",
            )

    # Update role
    team_member.role = request.role
    db.commit()

    # Get user info
    user = db.query(User).filter(User.id == user_id).first()

    return TeamMemberResponse(
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=team_member.role,
        joined_at=team_member.joined_at,
    )


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    team_id: UUID,
    user_id: UUID,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Remove a member from the team.

    Only admins can remove members.

    Args:
        team_id: Team ID
        user_id: User ID to remove
        auth: Authentication context (requires admin)
        db: Database session

    Raises:
        HTTPException: If member not found, user not admin, or trying to remove last admin
    """
    # Verify team ID matches current team in auth context
    if auth.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage members of your current team",
        )

    # Get team member
    team_member = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
        .first()
    )
    if team_member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    # Prevent removing last admin
    if team_member.role == "admin":
        admin_count = (
            db.query(TeamMember)
            .filter(TeamMember.team_id == team_id, TeamMember.role == "admin")
            .count()
        )
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last admin. Promote another member first or delete the team.",
            )

    # Remove member
    db.delete(team_member)
    db.commit()


# ===== Invitation Endpoints =====


@router.post("/{team_id}/invites", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def send_invitation(
    team_id: UUID,
    request: SendInvitationRequest,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Send a team invitation.

    Only admins can send invitations. If the email belongs to an existing user,
    they will be able to accept the invitation. If not, they must register first.

    Args:
        team_id: Team ID
        request: Invitation data (email, role)
        auth: Authentication context (requires admin)
        db: Database session

    Returns:
        InvitationResponse: Created invitation

    Raises:
        HTTPException: If team not found, user not admin, or user already member
    """
    # Verify team ID matches current team in auth context
    if auth.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only send invitations for your current team",
        )

    # Check if user is already a member
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        existing_member = (
            db.query(TeamMember)
            .filter(TeamMember.team_id == team_id, TeamMember.user_id == existing_user.id)
            .first()
        )
        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this team",
            )

    # Check for existing pending invitation
    existing_invitation = (
        db.query(TeamInvitation)
        .filter(
            TeamInvitation.team_id == team_id,
            TeamInvitation.email == request.email,
            TeamInvitation.accepted_at.is_(None),
        )
        .first()
    )
    if existing_invitation:
        # Delete old invitation and create new one
        db.delete(existing_invitation)
        db.flush()

    # Create invitation
    invitation_token = create_invitation_token()
    expires_at = datetime.utcnow() + timedelta(days=7)  # 7-day expiration

    invitation = TeamInvitation(
        team_id=team_id,
        email=request.email,
        role=request.role,
        invited_by=auth.user_id,
        expires_at=expires_at,
        token=invitation_token,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    # TODO: Send email with invitation link
    # email_service.send_invitation(request.email, invitation_token, team_name)

    return InvitationResponse.model_validate(invitation)


@router.get("/{team_id}/invites", response_model=List[InvitationResponse])
async def list_invitations(
    team_id: UUID,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    List pending invitations for a team.

    Only admins can view invitations.

    Args:
        team_id: Team ID
        auth: Authentication context (requires admin)
        db: Database session

    Returns:
        List[InvitationResponse]: List of pending invitations
    """
    # Verify team ID matches current team in auth context
    if auth.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view invitations for your current team",
        )

    # Get pending invitations
    invitations = (
        db.query(TeamInvitation)
        .filter(TeamInvitation.team_id == team_id, TeamInvitation.accepted_at.is_(None))
        .all()
    )

    return [InvitationResponse.model_validate(inv) for inv in invitations]


@router.delete("/{team_id}/invites/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invitation(
    team_id: UUID,
    invitation_id: UUID,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Cancel a pending invitation.

    Only admins can cancel invitations.

    Args:
        team_id: Team ID
        invitation_id: Invitation ID
        auth: Authentication context (requires admin)
        db: Database session

    Raises:
        HTTPException: If invitation not found or user not admin
    """
    # Verify team ID matches current team in auth context
    if auth.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only cancel invitations for your current team",
        )

    # Get invitation
    invitation = (
        db.query(TeamInvitation)
        .filter(TeamInvitation.id == invitation_id, TeamInvitation.team_id == team_id)
        .first()
    )
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    # Delete invitation
    db.delete(invitation)
    db.commit()


@router.post("/invites/accept", response_model=TeamResponse)
async def accept_invitation(
    request: AcceptInvitationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accept a team invitation.

    User must be authenticated to accept invitations.
    The invitation email must match the authenticated user's email.

    Args:
        request: Invitation token
        current_user: Authenticated user
        db: Database session

    Returns:
        TeamResponse: Team information

    Raises:
        HTTPException: If invitation not found, expired, or email mismatch
    """
    # Get invitation
    invitation = (
        db.query(TeamInvitation)
        .filter(TeamInvitation.token == request.token)
        .first()
    )
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    # Check if already accepted
    if invitation.accepted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation has already been accepted",
        )

    # Check if expired
    if invitation.is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation has expired",
        )

    # Check if email matches
    if invitation.email != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invitation email does not match your account email",
        )

    # Check if already a member
    existing_member = (
        db.query(TeamMember)
        .filter(
            TeamMember.team_id == invitation.team_id,
            TeamMember.user_id == current_user.id,
        )
        .first()
    )
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already a member of this team",
        )

    # Add user to team
    team_member = TeamMember(
        team_id=invitation.team_id,
        user_id=current_user.id,
        role=invitation.role,
    )
    db.add(team_member)

    # Mark invitation as accepted
    invitation.accepted_at = datetime.utcnow()
    db.commit()

    # Get team info
    team = db.query(Team).filter(Team.id == invitation.team_id).first()

    return TeamResponse.model_validate(team)
