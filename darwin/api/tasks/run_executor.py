"""
Run executor Celery task.

Executes Darwin runs in background subprocesses with progress tracking.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.orm import Session

from darwin.api.celery_app import celery_app
from darwin.api.db import SessionLocal, RunMetadata
from darwin.api.services.run_service import RunService


class RunExecutorTask(Task):
    """
    Custom task class for run execution with progress tracking.
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Handle task failure.

        Args:
            exc: Exception that caused failure
            task_id: Celery task ID
            args: Task arguments
            kwargs: Task keyword arguments
            einfo: Exception info
        """
        run_id = args[0] if args else None
        if run_id:
            db = SessionLocal()
            try:
                run_service = RunService()
                run_service.update_run_status(
                    run_id=run_id,
                    status="failed",
                    db=db,
                )

                # Update manifest with error
                manifest_path = run_service.get_manifest_path(run_id)
                if manifest_path.exists():
                    with open(manifest_path, "r") as f:
                        manifest_data = json.load(f)

                    manifest_data["status"] = "failed"
                    manifest_data["completed_at"] = datetime.utcnow().isoformat()
                    manifest_data["error_message"] = str(exc)
                    manifest_data["error_traceback"] = str(einfo)

                    with open(manifest_path, "w") as f:
                        json.dump(manifest_data, f, indent=2)
            finally:
                db.close()


@celery_app.task(bind=True, base=RunExecutorTask, name="darwin.api.tasks.run_executor.execute_run")
def execute_run(
    self,
    run_id: str,
    use_mock_llm: bool = False,
    resume_from_checkpoint: bool = False,
) -> dict:
    """
    Execute a Darwin run in a subprocess.

    Args:
        run_id: Run ID
        use_mock_llm: Use mock LLM for testing
        resume_from_checkpoint: Resume from checkpoint if available

    Returns:
        dict: Execution result with status and metrics
    """
    db = SessionLocal()
    run_service = RunService()

    try:
        # Update status to running
        run_service.update_run_status(
            run_id=run_id,
            status="running",
            celery_task_id=self.request.id,
            db=db,
        )

        # Build command
        config_path = run_service.get_config_path(run_id)
        cmd = [
            sys.executable,  # Python interpreter
            "-m",
            "darwin.cli",
            "run",
            str(config_path),
        ]

        if use_mock_llm:
            cmd.append("--mock-llm")

        if resume_from_checkpoint:
            cmd.append("--resume")

        # Get run directory for logging
        run_dir = run_service.get_run_dir(run_id)
        log_file = run_service.get_log_path(run_id)

        # Create log file directory if needed
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Execute subprocess
        with open(log_file, "w") as log_f:
            process = subprocess.Popen(
                cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
            )

            # Poll process and track progress
            manifest_path = run_service.get_manifest_path(run_id)
            last_update = time.time()
            update_interval = 5.0  # Update status every 5 seconds

            while process.poll() is None:
                # Check for soft time limit
                try:
                    time.sleep(1.0)
                except SoftTimeLimitExceeded:
                    # Kill process gracefully
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()

                    raise SoftTimeLimitExceeded("Run exceeded soft time limit")

                # Update progress periodically
                current_time = time.time()
                if current_time - last_update >= update_interval:
                    # Read manifest for progress
                    if manifest_path.exists():
                        try:
                            with open(manifest_path, "r") as f:
                                manifest_data = json.load(f)

                            # Update Celery task state with progress
                            self.update_state(
                                state="PROGRESS",
                                meta={
                                    "run_id": run_id,
                                    "bars_processed": manifest_data.get("bars_processed", 0),
                                    "candidates_generated": manifest_data.get("candidates_generated", 0),
                                    "trades_taken": manifest_data.get("trades_taken", 0),
                                    "llm_calls_made": manifest_data.get("llm_calls_made", 0),
                                    "llm_failures": manifest_data.get("llm_failures", 0),
                                },
                            )
                        except (json.JSONDecodeError, IOError):
                            pass  # Manifest might be being written

                    last_update = current_time

            # Process completed
            return_code = process.returncode

            if return_code == 0:
                # Success
                run_service.update_run_status(
                    run_id=run_id,
                    status="completed",
                    db=db,
                )

                # Load final manifest for metrics
                manifest = run_service.load_manifest(run_id)
                if manifest:
                    return {
                        "run_id": run_id,
                        "status": "completed",
                        "bars_processed": manifest.bars_processed,
                        "trades_taken": manifest.trades_taken,
                        "llm_calls_made": manifest.llm_calls_made,
                    }
                else:
                    return {
                        "run_id": run_id,
                        "status": "completed",
                    }
            else:
                # Failed
                run_service.update_run_status(
                    run_id=run_id,
                    status="failed",
                    db=db,
                )

                # Read last lines of log for error
                log_content = run_service.load_logs(run_id, tail_lines=50)

                return {
                    "run_id": run_id,
                    "status": "failed",
                    "return_code": return_code,
                    "error_log": log_content,
                }

    except SoftTimeLimitExceeded:
        # Time limit exceeded
        run_service.update_run_status(
            run_id=run_id,
            status="failed",
            db=db,
        )
        raise

    except Exception as e:
        # Unexpected error
        run_service.update_run_status(
            run_id=run_id,
            status="failed",
            db=db,
        )
        raise

    finally:
        db.close()


@celery_app.task(name="darwin.api.tasks.run_executor.cancel_run")
def cancel_run(run_id: str) -> dict:
    """
    Cancel a running task.

    Args:
        run_id: Run ID

    Returns:
        dict: Cancellation result
    """
    db = SessionLocal()
    run_service = RunService()

    try:
        # Get run metadata
        metadata = db.query(RunMetadata).filter(RunMetadata.run_id == run_id).first()
        if metadata is None:
            return {"run_id": run_id, "status": "not_found"}

        if metadata.status != "running":
            return {"run_id": run_id, "status": "not_running"}

        # Revoke Celery task
        if metadata.celery_task_id:
            celery_app.control.revoke(metadata.celery_task_id, terminate=True, signal="SIGTERM")

        # Update status
        run_service.update_run_status(
            run_id=run_id,
            status="cancelled",
            db=db,
        )

        return {"run_id": run_id, "status": "cancelled"}

    finally:
        db.close()
