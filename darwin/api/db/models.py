"""
SQLAlchemy database models for Darwin API.

Defines tables for:
- Users (authentication)
- Teams (multi-tenancy)
- Team members (user-team relationships)
- Team invitations (invite system)
- Sessions (optional session tracking)
- Run metadata (run ownership and status)
"""

from datetime import datetime, timedelta
from typing import Optional
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from darwin.api.db.postgres import Base


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    team_memberships = relationship("TeamMember", back_populates="user", cascade="all, delete")
    created_teams = relationship("Team", back_populates="creator")
    created_runs = relationship("RunMetadata", back_populates="creator")
    sent_invitations = relationship("TeamInvitation", back_populates="inviter")
    sessions = relationship("Session", back_populates="user", cascade="all, delete")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class Team(Base):
    """Team model for multi-tenancy."""

    __tablename__ = "teams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    # Relationships
    creator = relationship("User", back_populates="created_teams")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete")
    invitations = relationship("TeamInvitation", back_populates="team", cascade="all, delete")
    runs = relationship("RunMetadata", back_populates="team", cascade="all, delete")
    sessions = relationship("Session", back_populates="team", cascade="all, delete")

    def __repr__(self) -> str:
        return f"<Team(id={self.id}, name={self.name}, slug={self.slug})>"


class TeamMember(Base):
    """Team membership model with roles."""

    __tablename__ = "team_members"

    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role = Column(String(50), nullable=False)  # 'admin', 'member', 'viewer'
    joined_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_memberships")

    # Indexes
    __table_args__ = (
        Index("idx_team_members_team", "team_id"),
        Index("idx_team_members_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<TeamMember(team_id={self.team_id}, user_id={self.user_id}, role={self.role})>"


class TeamInvitation(Base):
    """Team invitation model for inviting new members."""

    __tablename__ = "team_invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # 'admin', 'member', 'viewer'
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    invited_at = Column(DateTime, default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    token = Column(String(255), unique=True, nullable=False, index=True)

    # Relationships
    team = relationship("Team", back_populates="invitations")
    inviter = relationship("User", back_populates="sent_invitations")

    # Indexes
    __table_args__ = (
        Index("idx_team_invitations_team", "team_id"),
        Index("idx_team_invitations_email", "email"),
    )

    @property
    def is_expired(self) -> bool:
        """Check if invitation has expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def is_accepted(self) -> bool:
        """Check if invitation has been accepted."""
        return self.accepted_at is not None

    def __repr__(self) -> str:
        return f"<TeamInvitation(id={self.id}, email={self.email}, team_id={self.team_id})>"


class Session(Base):
    """Session model for tracking user sessions (optional)."""

    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False)

    # Relationships
    user = relationship("User", back_populates="sessions")
    team = relationship("Team", back_populates="sessions")

    # Indexes
    __table_args__ = (
        Index("idx_sessions_user", "user_id"),
        Index("idx_sessions_team", "team_id"),
    )

    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.utcnow() > self.expires_at

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, user_id={self.user_id}, team_id={self.team_id})>"


class RunMetadata(Base):
    """Run metadata model for linking Darwin runs to teams."""

    __tablename__ = "run_metadata"

    run_id = Column(String(255), primary_key=True)  # Matches Darwin's run_id
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=func.now(), nullable=False)
    status = Column(String(50), nullable=True)  # 'queued', 'running', 'completed', 'failed'
    celery_task_id = Column(String(255), nullable=True)  # Link to background job
    config_json = Column(JSONB, nullable=True)  # Snapshot of run config

    # Relationships
    team = relationship("Team", back_populates="runs")
    creator = relationship("User", back_populates="created_runs")

    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint("run_id", "team_id", name="uq_run_team"),
        Index("idx_run_metadata_team", "team_id"),
        Index("idx_run_metadata_status", "status"),
        Index("idx_run_metadata_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<RunMetadata(run_id={self.run_id}, team_id={self.team_id}, status={self.status})>"
