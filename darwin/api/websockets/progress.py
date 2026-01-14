"""
WebSocket endpoint for real-time run progress updates.

Streams progress updates to connected clients as runs execute.
"""

import asyncio
import json
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.orm import Session

from darwin.api.db import get_db, RunMetadata
from darwin.api.services.run_service import RunService
from darwin.api.celery_app import celery_app


class ProgressManager:
    """
    Manages WebSocket connections for progress streaming.
    """

    def __init__(self):
        # Map of run_id to list of connected websockets
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, run_id: str, websocket: WebSocket):
        """
        Accept WebSocket connection and add to active connections.

        Args:
            run_id: Run ID to monitor
            websocket: WebSocket connection
        """
        await websocket.accept()

        if run_id not in self.active_connections:
            self.active_connections[run_id] = []

        self.active_connections[run_id].append(websocket)

    def disconnect(self, run_id: str, websocket: WebSocket):
        """
        Remove WebSocket from active connections.

        Args:
            run_id: Run ID
            websocket: WebSocket connection
        """
        if run_id in self.active_connections:
            self.active_connections[run_id].remove(websocket)

            # Clean up empty lists
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]

    async def send_progress(self, run_id: str, data: dict):
        """
        Send progress update to all connected clients for a run.

        Args:
            run_id: Run ID
            data: Progress data to send
        """
        if run_id in self.active_connections:
            # Send to all connected clients
            disconnected = []
            for websocket in self.active_connections[run_id]:
                try:
                    await websocket.send_json(data)
                except Exception:
                    # Mark for removal if send fails
                    disconnected.append(websocket)

            # Remove disconnected clients
            for websocket in disconnected:
                self.disconnect(run_id, websocket)


# Global progress manager
progress_manager = ProgressManager()


async def stream_progress(
    run_id: str,
    websocket: WebSocket,
    db: Session,
):
    """
    Stream progress updates for a run via WebSocket.

    Args:
        run_id: Run ID to monitor
        websocket: WebSocket connection
        db: Database session
    """
    run_service = RunService()

    # Verify run exists
    metadata = db.query(RunMetadata).filter(RunMetadata.run_id == run_id).first()
    if metadata is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Run not found")
        return

    # Connect websocket
    await progress_manager.connect(run_id, websocket)

    try:
        # Send initial status
        status_info = run_service.get_run_status(run_id, db)
        if status_info:
            await websocket.send_json({
                "type": "status",
                "data": status_info.model_dump(),
            })

        # Poll for updates
        last_manifest_data = None

        while True:
            try:
                # Check for client disconnect (with timeout)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=1.0  # Poll every second
                )

                # Handle ping/pong or control messages
                if data == "ping":
                    await websocket.send_text("pong")

            except asyncio.TimeoutError:
                # Timeout is normal, continue polling
                pass

            except WebSocketDisconnect:
                # Client disconnected
                break

            # Check Celery task state if running
            if metadata.celery_task_id and metadata.status == "running":
                task = celery_app.AsyncResult(metadata.celery_task_id)

                if task.state == "PROGRESS" and task.info:
                    # Send progress update
                    await websocket.send_json({
                        "type": "progress",
                        "data": task.info,
                    })

                elif task.state in ["SUCCESS", "FAILURE"]:
                    # Task completed
                    status_info = run_service.get_run_status(run_id, db)
                    if status_info:
                        await websocket.send_json({
                            "type": "completed",
                            "data": status_info.model_dump(),
                        })
                    break

            # Also check manifest file for updates (in case task state isn't updating)
            manifest = run_service.load_manifest(run_id)
            if manifest:
                manifest_data = manifest.model_dump()

                # Only send if changed
                if manifest_data != last_manifest_data:
                    await websocket.send_json({
                        "type": "progress",
                        "data": {
                            "run_id": run_id,
                            "bars_processed": manifest.bars_processed,
                            "candidates_generated": manifest.candidates_generated,
                            "trades_taken": manifest.trades_taken,
                            "llm_calls_made": manifest.llm_calls_made,
                            "llm_failures": manifest.llm_failures,
                        },
                    })
                    last_manifest_data = manifest_data

                # Check if completed
                if manifest.status in ["completed", "failed", "cancelled"]:
                    status_info = run_service.get_run_status(run_id, db)
                    if status_info:
                        await websocket.send_json({
                            "type": "completed",
                            "data": status_info.model_dump(),
                        })
                    break

            # Refresh metadata
            db.refresh(metadata)

    finally:
        # Disconnect websocket
        progress_manager.disconnect(run_id, websocket)
