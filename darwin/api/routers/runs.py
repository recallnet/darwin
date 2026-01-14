"""
Runs router for Darwin API.

Provides endpoints for:
- Run creation and configuration
- Run listing and filtering
- Run detail retrieval
- Run status monitoring
- Run launching (via Celery)
- Run logs access
- Run deletion
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket
from sqlalchemy.orm import Session

from darwin.api.db import get_db
from darwin.api.middleware.auth import get_auth_context, require_member, AuthContext
from darwin.api.models.run import (
    RunCreateRequest,
    RunUpdateRequest,
    RunDetailResponse,
    RunListResponse,
    RunStatusResponse,
    RunLaunchRequest,
    RunLaunchResponse,
    RunLogsResponse,
)
from darwin.api.services.run_service import RunService
from darwin.api.tasks.run_executor import execute_run, cancel_run as cancel_run_task
from darwin.api.websockets.progress import stream_progress

router = APIRouter()

# Initialize run service (will be moved to dependency injection later)
run_service = RunService()


@router.post("/", response_model=RunDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    request: RunCreateRequest,
    auth: AuthContext = Depends(require_member),
    db: Session = Depends(get_db),
):
    """
    Create a new run configuration.

    Creates the run metadata in the database and saves the config to disk.
    Does not launch the run - use POST /runs/{run_id}/launch to start execution.

    Members and admins can create runs.

    Args:
        request: Run creation request with configuration
        auth: Authentication context
        db: Database session

    Returns:
        RunDetailResponse: Created run details

    Raises:
        HTTPException: If run_id already exists or config is invalid
    """
    config = request.config

    # Check if run already exists
    if run_service.run_dir_exists(config.run_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Run with ID '{config.run_id}' already exists",
        )

    # Save config to disk
    run_service.save_config(config)

    # Create metadata in database
    metadata = run_service.create_run_metadata(
        config=config,
        team_id=auth.team_id,
        user_id=auth.user_id,
        db=db,
    )

    # Return detail response
    return run_service.get_run_detail(config.run_id, auth.team_id, db)


@router.get("/", response_model=RunListResponse)
async def list_runs(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(0, ge=0, description="Page number (0-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Page size (max 100)"),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    List runs for the current team with pagination.

    All team members can list runs.

    Args:
        status_filter: Optional status filter ('running', 'completed', 'failed', etc.)
        page: Page number (0-indexed)
        page_size: Page size (max 100)
        auth: Authentication context
        db: Database session

    Returns:
        RunListResponse: Paginated list of runs
    """
    items, total = run_service.list_runs(
        team_id=auth.team_id,
        db=db,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )

    return RunListResponse(
        runs=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get detailed run information.

    All team members can view run details.

    Args:
        run_id: Run ID
        auth: Authentication context
        db: Database session

    Returns:
        RunDetailResponse: Detailed run information

    Raises:
        HTTPException: If run not found or not owned by team
    """
    run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
    if run_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found",
        )

    return run_detail


@router.get("/{run_id}/status", response_model=RunStatusResponse)
async def get_run_status(
    run_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get run status and progress.

    All team members can view run status.

    Args:
        run_id: Run ID
        auth: Authentication context
        db: Database session

    Returns:
        RunStatusResponse: Run status with progress info

    Raises:
        HTTPException: If run not found or not owned by team
    """
    # Verify run belongs to team
    run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
    if run_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found",
        )

    status_info = run_service.get_run_status(run_id, db)
    if status_info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' status not found",
        )

    return status_info


@router.post("/{run_id}/launch", response_model=RunLaunchResponse)
async def launch_run(
    run_id: str,
    request: RunLaunchRequest,
    auth: AuthContext = Depends(require_member),
    db: Session = Depends(get_db),
):
    """
    Launch a run for execution.

    Queues the run to Celery for background execution.
    Members and admins can launch runs.

    Args:
        run_id: Run ID
        request: Launch options
        auth: Authentication context
        db: Database session

    Returns:
        RunLaunchResponse: Launch confirmation with task ID

    Raises:
        HTTPException: If run not found, already running, or launch fails
    """
    # Verify run belongs to team
    run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
    if run_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found",
        )

    # Check status
    if run_detail.status == "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Run '{run_id}' is already running",
        )

    # Launch Celery task
    task = execute_run.delay(
        run_id,
        use_mock_llm=request.use_mock_llm,
        resume_from_checkpoint=request.resume_from_checkpoint,
    )

    # Task is automatically queued, status will be updated by task
    return RunLaunchResponse(
        run_id=run_id,
        celery_task_id=task.id,
        status="queued",
        message=f"Run '{run_id}' queued for execution",
    )


@router.get("/{run_id}/logs", response_model=RunLogsResponse)
async def get_run_logs(
    run_id: str,
    tail: Optional[int] = Query(None, ge=1, le=10000, description="Return last N lines only"),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Get run logs.

    All team members can view logs.

    Args:
        run_id: Run ID
        tail: Optional - return only last N lines
        auth: Authentication context
        db: Database session

    Returns:
        RunLogsResponse: Log content

    Raises:
        HTTPException: If run not found or logs not available
    """
    # Verify run belongs to team
    run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
    if run_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found",
        )

    logs = run_service.load_logs(run_id, tail_lines=tail)
    if logs is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Logs for run '{run_id}' not found (run may not have started yet)",
        )

    return RunLogsResponse(
        run_id=run_id,
        logs=logs,
        log_file=str(run_service.get_log_path(run_id)),
    )


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(
    run_id: str,
    auth: AuthContext = Depends(require_member),
    db: Session = Depends(get_db),
):
    """
    Delete a run.

    Deletes run metadata and artifacts from disk.
    Members and admins can delete runs.

    Args:
        run_id: Run ID
        auth: Authentication context
        db: Database session

    Raises:
        HTTPException: If run not found or currently running
    """
    # Verify run belongs to team
    run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
    if run_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found",
        )

    # Prevent deleting running runs
    if run_detail.status == "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete run '{run_id}' while it is running. Cancel it first.",
        )

    # Delete run
    success = run_service.delete_run(run_id, auth.team_id, db)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete run '{run_id}'",
        )


@router.post("/{run_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_run(
    run_id: str,
    auth: AuthContext = Depends(require_member),
    db: Session = Depends(get_db),
):
    """
    Cancel a running task.

    Members and admins can cancel runs.

    Args:
        run_id: Run ID
        auth: Authentication context
        db: Database session

    Returns:
        dict: Cancellation result

    Raises:
        HTTPException: If run not found or not running
    """
    # Verify run belongs to team
    run_detail = run_service.get_run_detail(run_id, auth.team_id, db)
    if run_detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found",
        )

    # Check if running
    if run_detail.status != "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Run '{run_id}' is not running (status: {run_detail.status})",
        )

    # Cancel task
    result = cancel_run_task.delay(run_id)

    return {
        "run_id": run_id,
        "status": "cancelling",
        "message": f"Cancellation request sent for run '{run_id}'",
    }


@router.websocket("/{run_id}/progress")
async def progress_websocket(
    websocket: WebSocket,
    run_id: str,
    db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for real-time run progress updates.

    Connect to this endpoint to receive progress updates as the run executes.

    Messages sent:
    - {"type": "status", "data": {...}} - Initial status
    - {"type": "progress", "data": {...}} - Progress updates
    - {"type": "completed", "data": {...}} - Final status

    Client can send "ping" to keep connection alive.

    Args:
        websocket: WebSocket connection
        run_id: Run ID to monitor
        db: Database session
    """
    # Note: Authentication for WebSockets is more complex
    # For now, anyone can connect to monitor progress
    # In production, should validate token from query params or headers

    await stream_progress(run_id, websocket, db)
