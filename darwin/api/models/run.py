"""
Pydantic models for run management API.

Defines request and response schemas for:
- Run creation and configuration
- Run status and monitoring
- Run listing and filtering
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

# Import Darwin's existing schemas
from darwin.schemas.run_config import RunConfigV1
from darwin.schemas.run_manifest import RunManifestV1


class RunCreateRequest(BaseModel):
    """Request model for creating a new run."""

    config: RunConfigV1 = Field(..., description="Run configuration")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "config": {
                    "run_id": "my-run-001",
                    "description": "Testing breakout strategy on BTC",
                    "market_scope": {
                        "venue": "coinbase",
                        "symbols": ["BTC-USD"],
                        "primary_timeframe": "15m",
                        "start_date": "2024-01-01",
                        "end_date": "2024-03-01",
                    },
                    "playbooks": [
                        {
                            "name": "breakout",
                            "stop_loss_atr": 2.0,
                            "take_profit_atr": 4.0,
                            "time_stop_bars": 32,
                            "trailing_activation_atr": 2.5,
                            "trailing_distance_atr": 1.5,
                        }
                    ],
                }
            }
        }
    )


class RunUpdateRequest(BaseModel):
    """Request model for updating run metadata (not the config itself)."""

    description: Optional[str] = Field(None, description="Updated description")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "description": "Updated: Testing breakout with adjusted parameters",
            }
        }
    )


class RunStatusResponse(BaseModel):
    """Response model for run status."""

    run_id: str = Field(..., description="Run ID")
    status: str = Field(..., description="Status: queued, running, completed, failed, cancelled")
    celery_task_id: Optional[str] = Field(None, description="Celery task ID if running")

    # Progress info (from manifest if available)
    bars_processed: int = Field(default=0, description="Bars processed so far")
    candidates_generated: int = Field(default=0, description="Candidates generated")
    trades_taken: int = Field(default=0, description="Trades taken")
    llm_calls_made: int = Field(default=0, description="LLM calls made")
    llm_failures: int = Field(default=0, description="LLM failures")

    # Timestamps
    started_at: Optional[datetime] = Field(None, description="Run start time")
    completed_at: Optional[datetime] = Field(None, description="Run completion time")

    # Error info
    error_message: Optional[str] = Field(None, description="Error message if failed")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "my-run-001",
                "status": "running",
                "celery_task_id": "abc123-def456",
                "bars_processed": 1250,
                "candidates_generated": 48,
                "trades_taken": 12,
                "llm_calls_made": 48,
                "llm_failures": 0,
                "started_at": "2024-01-20T10:00:00Z",
                "completed_at": None,
                "error_message": None,
            }
        }
    )


class RunListItem(BaseModel):
    """List item model for run in paginated list."""

    run_id: str = Field(..., description="Run ID")
    description: str = Field(..., description="Run description")
    status: str = Field(..., description="Run status")

    # Key config info
    symbols: List[str] = Field(..., description="Trading symbols")
    playbooks: List[str] = Field(..., description="Playbook names")
    start_date: Optional[str] = Field(None, description="Start date")
    end_date: Optional[str] = Field(None, description="End date")

    # Metadata
    created_by: Optional[UUID] = Field(None, description="User who created the run")
    created_at: datetime = Field(..., description="Creation timestamp")

    # Quick stats (from manifest)
    bars_processed: int = Field(default=0, description="Bars processed")
    trades_taken: int = Field(default=0, description="Trades taken")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "run_id": "my-run-001",
                "description": "Testing breakout strategy",
                "status": "completed",
                "symbols": ["BTC-USD"],
                "playbooks": ["breakout"],
                "start_date": "2024-01-01",
                "end_date": "2024-03-01",
                "created_by": "550e8400-e29b-41d4-a716-446655440000",
                "created_at": "2024-01-20T10:00:00Z",
                "bars_processed": 2500,
                "trades_taken": 24,
            }
        },
    )


class RunListResponse(BaseModel):
    """Response model for paginated list of runs."""

    runs: List[RunListItem] = Field(..., description="List of runs")
    total: int = Field(..., description="Total number of runs matching filters")
    page: int = Field(..., description="Current page number (0-indexed)")
    page_size: int = Field(..., description="Page size")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "runs": [
                    {
                        "run_id": "my-run-001",
                        "description": "Testing breakout",
                        "status": "completed",
                        "symbols": ["BTC-USD"],
                        "playbooks": ["breakout"],
                        "start_date": "2024-01-01",
                        "end_date": "2024-03-01",
                        "created_by": "550e8400-e29b-41d4-a716-446655440000",
                        "created_at": "2024-01-20T10:00:00Z",
                        "bars_processed": 2500,
                        "trades_taken": 24,
                    }
                ],
                "total": 1,
                "page": 0,
                "page_size": 20,
            }
        }
    )


class RunDetailResponse(BaseModel):
    """Response model for detailed run information."""

    run_id: str = Field(..., description="Run ID")
    team_id: UUID = Field(..., description="Team ID")
    created_by: Optional[UUID] = Field(None, description="User who created the run")
    created_at: datetime = Field(..., description="Creation timestamp")

    # Status
    status: str = Field(..., description="Run status")
    celery_task_id: Optional[str] = Field(None, description="Celery task ID")

    # Config
    config: RunConfigV1 = Field(..., description="Run configuration")

    # Manifest (if available)
    manifest: Optional[RunManifestV1] = Field(None, description="Run manifest")

    # File paths
    run_dir: str = Field(..., description="Run directory path")
    config_file: str = Field(..., description="Config file path")
    manifest_file: str = Field(..., description="Manifest file path")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "run_id": "my-run-001",
                "team_id": "660e8400-e29b-41d4-a716-446655440001",
                "created_by": "550e8400-e29b-41d4-a716-446655440000",
                "created_at": "2024-01-20T10:00:00Z",
                "status": "completed",
                "celery_task_id": None,
                "config": {"run_id": "my-run-001", "...": "..."},
                "manifest": {
                    "status": "completed",
                    "bars_processed": 2500,
                    "trades_taken": 24,
                },
                "run_dir": "artifacts/runs/my-run-001",
                "config_file": "artifacts/runs/my-run-001/run_config.json",
                "manifest_file": "artifacts/runs/my-run-001/manifest.json",
            }
        },
    )


class RunLaunchRequest(BaseModel):
    """Request model for launching a run."""

    use_mock_llm: bool = Field(default=False, description="Use mock LLM for testing")
    resume_from_checkpoint: bool = Field(default=False, description="Resume from checkpoint if available")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "use_mock_llm": False,
                "resume_from_checkpoint": False,
            }
        }
    )


class RunLaunchResponse(BaseModel):
    """Response model for run launch."""

    run_id: str = Field(..., description="Run ID")
    celery_task_id: str = Field(..., description="Celery task ID for monitoring")
    status: str = Field(default="queued", description="Initial status")
    message: str = Field(..., description="Launch confirmation message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "my-run-001",
                "celery_task_id": "abc123-def456",
                "status": "queued",
                "message": "Run queued for execution",
            }
        }
    )


class RunLogsResponse(BaseModel):
    """Response model for run logs."""

    run_id: str = Field(..., description="Run ID")
    logs: str = Field(..., description="Log content")
    log_file: str = Field(..., description="Log file path")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "my-run-001",
                "logs": "2024-01-20 10:00:00 - INFO - Starting run...\\n2024-01-20 10:00:01 - INFO - Loaded 2500 bars\\n",
                "log_file": "artifacts/runs/my-run-001/run.log",
            }
        }
    )
