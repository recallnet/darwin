"""Artifact header schema - mandatory for all Darwin artifacts."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ArtifactScope(str, Enum):
    """Scope of the artifact."""

    RUN = "run"
    META = "meta"
    GLOBAL = "global"


class GeneratorInfo(BaseModel):
    """Information about the generator that created the artifact."""

    name: str = Field(..., description="Name of the generator (e.g., 'darwin_runner')")
    version: str = Field(..., description="Version of the generator (e.g., '0.1.0')")


class ArtifactHeaderV1(BaseModel):
    """
    Mandatory header for all Darwin artifacts.

    This header provides:
    - Schema versioning for forward/backward compatibility
    - Provenance tracking (when, by what, for which run)
    - Integrity verification (fingerprints)
    """

    schema: str = Field(..., description="Schema version string (e.g., 'ArtifactHeaderV1')")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when artifact was created"
    )
    run_id: Optional[str] = Field(None, description="Run ID if artifact is run-specific, else null")
    scope: ArtifactScope = Field(..., description="Scope of the artifact")
    generator: GeneratorInfo = Field(..., description="Generator information")
    config_fingerprint: Optional[str] = Field(
        None, description="Short hash of run config (first 8 chars of SHA256)"
    )
    run_config_sha256: Optional[str] = Field(
        None, description="Full SHA256 of run config JSON for integrity verification"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        use_enum_values = True
