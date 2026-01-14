"""
RL monitoring router for Darwin API.

Provides endpoints for:
- Agent status and overview
- Performance metrics and history
- Graduation tracking
- Alert monitoring
- Model version management
- Agent decisions
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from darwin.api.db import get_db
from darwin.api.middleware.auth import get_auth_context, AuthContext
from darwin.api.models.rl import (
    AgentsOverviewResponse,
    AgentDetailResponse,
    PerformanceMetricsResponse,
    PerformanceHistoryResponse,
    GraduationStatusResponse,
    GraduationHistoryResponse,
    AlertsResponse,
    AgentDecisionResponse,
    ModelVersionsResponse,
    RollbackModelRequest,
)
from darwin.api.services.rl_service import RLService

router = APIRouter()

# Initialize service
rl_service = RLService()


@router.get("/agents", response_model=AgentsOverviewResponse)
async def get_agents_overview(
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get overview of all RL agents.

    Returns status summaries for gate, portfolio, and meta-learner agents.
    All team members can view agent status.

    Args:
        auth: Authentication context
        db: Database session

    Returns:
        AgentsOverviewResponse: Overview of all agents

    Raises:
        HTTPException: If error retrieving agent data
    """
    try:
        overview = rl_service.get_agents_overview()
        return overview

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving agents overview: {str(e)}",
        )


@router.get("/agents/{agent_name}", response_model=AgentDetailResponse)
async def get_agent_detail(
    agent_name: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get detailed information for a specific agent.

    Includes graduation status, performance metrics, alerts, and recent activity.
    All team members can view agent details.

    Args:
        agent_name: Name of agent (gate, portfolio, meta_learner)
        auth: Authentication context
        db: Database session

    Returns:
        AgentDetailResponse: Detailed agent information

    Raises:
        HTTPException: If agent not found or error retrieving data
    """
    try:
        detail = rl_service.get_agent_detail(agent_name)
        return detail

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving agent detail: {str(e)}",
        )


@router.get("/agents/{agent_name}/metrics", response_model=PerformanceMetricsResponse)
async def get_performance_metrics(
    agent_name: str,
    window_days: int = Query(30, ge=1, le=365, description="Window size in days"),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get performance metrics for an agent.

    Returns rolling metrics (mean R-multiple, win rate, Sharpe ratio, etc.)
    over the specified window. Includes agent-specific metrics.

    All team members can view performance metrics.

    Args:
        agent_name: Name of agent
        window_days: Window size in days (1-365)
        auth: Authentication context
        db: Database session

    Returns:
        PerformanceMetricsResponse: Performance metrics

    Raises:
        HTTPException: If agent not found or no data available
    """
    try:
        metrics = rl_service.get_performance_metrics(agent_name, window_days=window_days)
        return metrics

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving performance metrics: {str(e)}",
        )


@router.get("/agents/{agent_name}/metrics/history", response_model=PerformanceHistoryResponse)
async def get_performance_history(
    agent_name: str,
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Limit number of snapshots"),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get performance history (time series of snapshots).

    Returns historical performance snapshots for charting trends over time.
    All team members can view performance history.

    Args:
        agent_name: Name of agent
        limit: Optional limit on number of snapshots
        auth: Authentication context
        db: Database session

    Returns:
        PerformanceHistoryResponse: Performance history

    Raises:
        HTTPException: If agent not found
    """
    try:
        history = rl_service.get_performance_history(agent_name, limit=limit)
        return history

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving performance history: {str(e)}",
        )


@router.get("/agents/{agent_name}/graduation", response_model=GraduationStatusResponse)
async def get_graduation_status(
    agent_name: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get graduation status for an agent.

    Shows whether agent can graduate from observe to active mode,
    including all graduation checks and progress metrics.

    All team members can view graduation status.

    Args:
        agent_name: Name of agent
        auth: Authentication context
        db: Database session

    Returns:
        GraduationStatusResponse: Graduation status

    Raises:
        HTTPException: If agent not found
    """
    try:
        graduation = rl_service.get_graduation_status(agent_name)
        return graduation

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving graduation status: {str(e)}",
        )


@router.get("/agents/{agent_name}/graduation/history", response_model=GraduationHistoryResponse)
async def get_graduation_history(
    agent_name: str,
    limit: Optional[int] = Query(None, ge=1, le=100, description="Limit number of records"),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get graduation evaluation history.

    Returns historical graduation evaluations showing when agent
    was promoted/demoted and reasons for decisions.

    All team members can view graduation history.

    Args:
        agent_name: Name of agent
        limit: Optional limit on number of records
        auth: Authentication context
        db: Database session

    Returns:
        GraduationHistoryResponse: Graduation history

    Raises:
        HTTPException: If agent not found
    """
    try:
        history = rl_service.get_graduation_history(agent_name, limit=limit)
        return history

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving graduation history: {str(e)}",
        )


@router.get("/agents/{agent_name}/alerts", response_model=AlertsResponse)
async def get_alerts(
    agent_name: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get active alerts for an agent.

    Returns alerts for performance degradation, excessive overrides,
    low decision rate, etc.

    All team members can view alerts.

    Args:
        agent_name: Name of agent
        auth: Authentication context
        db: Database session

    Returns:
        AlertsResponse: Active alerts

    Raises:
        HTTPException: If agent not found
    """
    try:
        alerts = rl_service.get_alerts(agent_name)
        return alerts

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving alerts: {str(e)}",
        )


@router.get("/agents/{agent_name}/decisions", response_model=List[AgentDecisionResponse])
async def get_decisions(
    agent_name: str,
    run_id: Optional[str] = Query(None, description="Filter by run ID"),
    limit: int = Query(100, ge=1, le=1000, description="Limit number of decisions"),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get agent decisions.

    Returns recent decisions made by the agent, optionally filtered by run ID.
    All team members can view decisions.

    Args:
        agent_name: Name of agent
        run_id: Optional run ID filter
        limit: Limit on number of decisions (1-1000)
        auth: Authentication context
        db: Database session

    Returns:
        List[AgentDecisionResponse]: Agent decisions

    Raises:
        HTTPException: If agent not found
    """
    try:
        decisions = rl_service.get_decisions(agent_name, run_id=run_id, limit=limit)
        return decisions

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving decisions: {str(e)}",
        )


@router.get("/agents/{agent_name}/models", response_model=ModelVersionsResponse)
async def get_model_versions(
    agent_name: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get all model versions for an agent.

    Returns list of all saved model versions with metadata,
    including which version is currently active.

    All team members can view model versions.

    Args:
        agent_name: Name of agent
        auth: Authentication context
        db: Database session

    Returns:
        ModelVersionsResponse: Model versions

    Raises:
        HTTPException: If agent not found
    """
    try:
        versions = rl_service.get_model_versions(agent_name)
        return versions

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving model versions: {str(e)}",
        )


@router.post("/agents/{agent_name}/models/rollback")
async def rollback_model(
    agent_name: str,
    request: RollbackModelRequest,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Rollback model to a specific version.

    Changes the current model version to a previous version.
    Only team admins can rollback models.

    Args:
        agent_name: Name of agent
        request: Rollback request with version
        auth: Authentication context
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If agent not found, version not found, or not authorized
    """
    # Check if user is admin
    if auth.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team admins can rollback models",
        )

    try:
        rl_service.rollback_model(agent_name, request.version)
        return {
            "message": f"Successfully rolled back {agent_name} to version {request.version}",
            "agent_name": agent_name,
            "version": request.version,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rolling back model: {str(e)}",
        )
