"""Run manifest schema."""

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field

from darwin.schemas.artifact_header import ArtifactHeaderV1


class RunManifestV1(BaseModel):
    """
    Run manifest with provenance and integrity information.

    Created at run start and updated at completion.
    """

    header: ArtifactHeaderV1 = Field(..., description="Artifact header")

    # Provenance
    started_at: datetime = Field(..., description="Run start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Run completion timestamp (null if incomplete)")
    status: str = Field(default="running", description="Status: running, completed, failed, cancelled")

    # Data sources
    data_provider: str = Field(default="replay-lab", description="Data provider name")
    data_version: Optional[str] = Field(None, description="Data version or commit hash")

    # Execution stats
    bars_processed: int = Field(default=0, description="Number of bars processed")
    candidates_generated: int = Field(default=0, description="Number of candidates generated")
    trades_taken: int = Field(default=0, description="Number of trades taken")
    llm_calls_made: int = Field(default=0, description="Number of LLM calls made")
    llm_failures: int = Field(default=0, description="Number of LLM failures")

    # Content hashes for verification
    content_hashes: Dict[str, str] = Field(
        default_factory=dict,
        description="SHA256 hashes of key artifacts"
    )

    # Error info (if failed)
    error_message: Optional[str] = Field(None, description="Error message if run failed")
    error_traceback: Optional[str] = Field(None, description="Error traceback if run failed")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
