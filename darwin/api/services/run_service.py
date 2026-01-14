"""
Run service layer for Darwin API.

Provides business logic for:
- Run configuration management
- Run metadata queries
- Darwin artifact access (manifests, configs, logs)
- Integration with position ledger and candidate cache
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import desc

from darwin.api.db import RunMetadata, User
from darwin.api.models.run import (
    RunListItem,
    RunDetailResponse,
    RunStatusResponse,
)
from darwin.schemas.run_config import RunConfigV1
from darwin.schemas.run_manifest import RunManifestV1


class RunService:
    """Service for managing Darwin runs."""

    def __init__(self, artifacts_dir: Optional[Path] = None):
        """
        Initialize run service.

        Args:
            artifacts_dir: Artifacts directory (defaults to DARWIN_ARTIFACTS_DIR env var or 'artifacts')
        """
        if artifacts_dir is None:
            artifacts_dir = Path(os.getenv("DARWIN_ARTIFACTS_DIR", "artifacts"))
        self.artifacts_dir = Path(artifacts_dir)
        self.runs_dir = self.artifacts_dir / "runs"

    def get_run_dir(self, run_id: str) -> Path:
        """Get run directory path."""
        return self.runs_dir / run_id

    def get_config_path(self, run_id: str) -> Path:
        """Get run config file path."""
        return self.get_run_dir(run_id) / "run_config.json"

    def get_manifest_path(self, run_id: str) -> Path:
        """Get manifest file path."""
        return self.get_run_dir(run_id) / "manifest.json"

    def get_log_path(self, run_id: str) -> Path:
        """Get run log file path."""
        return self.get_run_dir(run_id) / "run.log"

    def run_dir_exists(self, run_id: str) -> bool:
        """Check if run directory exists."""
        return self.get_run_dir(run_id).exists()

    def load_config(self, run_id: str) -> Optional[RunConfigV1]:
        """
        Load run configuration from disk.

        Args:
            run_id: Run ID

        Returns:
            RunConfigV1 if config exists, None otherwise
        """
        config_path = self.get_config_path(run_id)
        if not config_path.exists():
            return None

        with open(config_path, "r") as f:
            config_data = json.load(f)

        return RunConfigV1(**config_data)

    def save_config(self, config: RunConfigV1) -> Path:
        """
        Save run configuration to disk.

        Args:
            config: Run configuration

        Returns:
            Path to saved config file
        """
        run_dir = self.get_run_dir(config.run_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        config_path = self.get_config_path(config.run_id)
        with open(config_path, "w") as f:
            json.dump(config.model_dump(), f, indent=2, default=str)

        return config_path

    def load_manifest(self, run_id: str) -> Optional[RunManifestV1]:
        """
        Load run manifest from disk.

        Args:
            run_id: Run ID

        Returns:
            RunManifestV1 if manifest exists, None otherwise
        """
        manifest_path = self.get_manifest_path(run_id)
        if not manifest_path.exists():
            return None

        with open(manifest_path, "r") as f:
            manifest_data = json.load(f)

        return RunManifestV1(**manifest_data)

    def load_logs(self, run_id: str, tail_lines: Optional[int] = None) -> Optional[str]:
        """
        Load run logs from disk.

        Args:
            run_id: Run ID
            tail_lines: If provided, return only last N lines

        Returns:
            Log content if log file exists, None otherwise
        """
        log_path = self.get_log_path(run_id)
        if not log_path.exists():
            return None

        if tail_lines is None:
            # Read entire file
            with open(log_path, "r") as f:
                return f.read()
        else:
            # Read last N lines
            with open(log_path, "r") as f:
                lines = f.readlines()
                return "".join(lines[-tail_lines:])

    def get_run_status(self, run_id: str, db: Session) -> Optional[RunStatusResponse]:
        """
        Get run status with progress information.

        Combines database metadata with manifest data.

        Args:
            run_id: Run ID
            db: Database session

        Returns:
            RunStatusResponse if run exists, None otherwise
        """
        # Get metadata from database
        metadata = db.query(RunMetadata).filter(RunMetadata.run_id == run_id).first()
        if metadata is None:
            return None

        # Load manifest for progress info
        manifest = self.load_manifest(run_id)

        # Build status response
        status_data = {
            "run_id": run_id,
            "status": metadata.status or "unknown",
            "celery_task_id": metadata.celery_task_id,
        }

        # Add progress info from manifest if available
        if manifest:
            status_data.update({
                "bars_processed": manifest.bars_processed,
                "candidates_generated": manifest.candidates_generated,
                "trades_taken": manifest.trades_taken,
                "llm_calls_made": manifest.llm_calls_made,
                "llm_failures": manifest.llm_failures,
                "started_at": manifest.started_at,
                "completed_at": manifest.completed_at,
                "error_message": manifest.error_message,
            })

        return RunStatusResponse(**status_data)

    def list_runs(
        self,
        team_id: UUID,
        db: Session,
        status_filter: Optional[str] = None,
        page: int = 0,
        page_size: int = 20,
    ) -> Tuple[List[RunListItem], int]:
        """
        List runs for a team with pagination.

        Args:
            team_id: Team ID
            db: Database session
            status_filter: Optional status filter ('running', 'completed', 'failed', etc.)
            page: Page number (0-indexed)
            page_size: Page size

        Returns:
            Tuple of (list of RunListItem, total count)
        """
        # Build query
        query = db.query(RunMetadata).filter(RunMetadata.team_id == team_id)

        if status_filter:
            query = query.filter(RunMetadata.status == status_filter)

        # Get total count
        total = query.count()

        # Get page of results
        metadata_list = (
            query.order_by(desc(RunMetadata.created_at))
            .offset(page * page_size)
            .limit(page_size)
            .all()
        )

        # Build list items
        items = []
        for metadata in metadata_list:
            # Load config for key info
            config = self.load_config(metadata.run_id)
            manifest = self.load_manifest(metadata.run_id)

            if config:
                item = RunListItem(
                    run_id=metadata.run_id,
                    description=config.description,
                    status=metadata.status or "unknown",
                    symbols=config.market_scope.symbols,
                    playbooks=[pb.name for pb in config.playbooks],
                    start_date=config.market_scope.start_date,
                    end_date=config.market_scope.end_date,
                    created_by=metadata.created_by,
                    created_at=metadata.created_at,
                    bars_processed=manifest.bars_processed if manifest else 0,
                    trades_taken=manifest.trades_taken if manifest else 0,
                )
                items.append(item)

        return items, total

    def get_run_detail(self, run_id: str, team_id: UUID, db: Session) -> Optional[RunDetailResponse]:
        """
        Get detailed run information.

        Args:
            run_id: Run ID
            team_id: Team ID (for authorization check)
            db: Database session

        Returns:
            RunDetailResponse if run exists and belongs to team, None otherwise
        """
        # Get metadata from database
        metadata = (
            db.query(RunMetadata)
            .filter(RunMetadata.run_id == run_id, RunMetadata.team_id == team_id)
            .first()
        )
        if metadata is None:
            return None

        # Load config and manifest
        config = self.load_config(run_id)
        if config is None:
            return None

        manifest = self.load_manifest(run_id)

        # Build detail response
        return RunDetailResponse(
            run_id=run_id,
            team_id=metadata.team_id,
            created_by=metadata.created_by,
            created_at=metadata.created_at,
            status=metadata.status or "unknown",
            celery_task_id=metadata.celery_task_id,
            config=config,
            manifest=manifest,
            run_dir=str(self.get_run_dir(run_id)),
            config_file=str(self.get_config_path(run_id)),
            manifest_file=str(self.get_manifest_path(run_id)),
        )

    def create_run_metadata(
        self,
        config: RunConfigV1,
        team_id: UUID,
        user_id: UUID,
        db: Session,
    ) -> RunMetadata:
        """
        Create run metadata in database.

        Args:
            config: Run configuration
            team_id: Team ID
            user_id: User ID
            db: Database session

        Returns:
            Created RunMetadata
        """
        metadata = RunMetadata(
            run_id=config.run_id,
            team_id=team_id,
            created_by=user_id,
            status="created",
            config_json=config.model_dump(),
        )
        db.add(metadata)
        db.commit()
        db.refresh(metadata)

        return metadata

    def update_run_status(
        self,
        run_id: str,
        status: str,
        celery_task_id: Optional[str] = None,
        db: Session = None,
    ) -> Optional[RunMetadata]:
        """
        Update run status in database.

        Args:
            run_id: Run ID
            status: New status
            celery_task_id: Optional Celery task ID
            db: Database session

        Returns:
            Updated RunMetadata if run exists, None otherwise
        """
        metadata = db.query(RunMetadata).filter(RunMetadata.run_id == run_id).first()
        if metadata is None:
            return None

        metadata.status = status
        if celery_task_id is not None:
            metadata.celery_task_id = celery_task_id

        db.commit()
        db.refresh(metadata)

        return metadata

    def delete_run(self, run_id: str, team_id: UUID, db: Session) -> bool:
        """
        Delete a run (metadata and artifacts).

        Args:
            run_id: Run ID
            team_id: Team ID (for authorization check)
            db: Database session

        Returns:
            True if deleted, False if run not found
        """
        # Get metadata
        metadata = (
            db.query(RunMetadata)
            .filter(RunMetadata.run_id == run_id, RunMetadata.team_id == team_id)
            .first()
        )
        if metadata is None:
            return False

        # Delete from database
        db.delete(metadata)
        db.commit()

        # Delete artifacts directory
        run_dir = self.get_run_dir(run_id)
        if run_dir.exists():
            import shutil
            shutil.rmtree(run_dir)

        return True
