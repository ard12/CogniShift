"""
Phase 4 Sandbox Data Models and Schemas.
Enforces strict typing, resource bounds, and execution contracts for isolated code execution.
"""
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator


class SandboxStatus(str, Enum):
    """Explicit status outcomes of sandbox execution."""
    SUCCESS = "success"
    RUNTIME_ERROR = "runtime_error"
    TIMEOUT = "timeout"
    RESOURCE_EXCEEDED = "resource_exceeded"
    SANDBOX_UNAVAILABLE = "sandbox_unavailable"
    VALIDATION_FAILED = "validation_failed"
    INTERNAL_ERROR = "internal_error"

class SandboxUnavailableError(Exception):
    """Raised when container runtime (Docker/Podman) is missing or daemon is offline."""
    pass


class SandboxInputFile(BaseModel):
    """Reference to an authorized input file to stage into the sandbox."""
    source_path: str = Field(..., description="Workspace-relative path to source file (e.g. 'documents/data.csv')")
    dest_name: str = Field(..., pattern=r"^[A-Za-z0-9_.-]+$", description="Destination filename inside /workspace/input")
    source_kind: str = Field(default="workspace_artifact", description="Origin kind: 'workspace_artifact', 'knowledge_source', 'file'")
    source_id: Optional[int] = Field(default=None, description="Primary ID if sourced from knowledge_sources")
    artifact_id: Optional[int] = Field(default=None, description="Primary ID if sourced from workspace_artifacts")
    expected_sha256: Optional[str] = Field(default=None, description="Cryptographic SHA-256 hash required for registered source integrity")

    @field_validator("dest_name")
    @classmethod
    def reject_directory_names(cls, value):
        if value in {".", ".."}:
            raise ValueError("Input destination must be a filename")
        return value


class StagingManifestEntry(BaseModel):
    """Integrity record for an individual staged file."""
    source_path: str
    dest_name: str
    source_kind: str
    source_id: Optional[int] = None
    artifact_id: Optional[int] = None
    expected_sha256: Optional[str] = None
    source_sha256: str
    staged_sha256: str
    verified: bool


class StagingIntegrityManifest(BaseModel):
    """Audit manifest of cryptographic input provenance."""
    execution_id: str
    workspace_id: int
    entries: List[StagingManifestEntry] = Field(default_factory=list)
    all_verified: bool = True


class ExecutionProvenance(BaseModel):
    execution_id: str
    backend: str
    backend_verified: bool
    container_runtime: Optional[str] = None
    image_name: Optional[str] = None
    image_digest: Optional[str] = None
    code_sha256: str
    staged_code_sha256: str
    command: List[str] = Field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    exit_code: int = 0
    stdout_sha256: str = ""
    stderr_sha256: str = ""
    artifact_ids: List[int] = Field(default_factory=list)
    artifact_sha256s: Dict[str, str] = Field(default_factory=dict)
    simulated: bool = False
    failure_reason: Optional[str] = None


class CodeExecutionRequest(BaseModel):
    """Fully validated execution payload prepared for sandbox runner."""
    execution_id: str = Field(default="", pattern=r"^[A-Za-z0-9_-]{0,100}$")
    workspace_id: int = Field(default=1)
    run_id: int = Field(default=0)
    code: str = Field(..., min_length=1, max_length=100000)
    entrypoint: str = Field(default="main.py", pattern=r"^[A-Za-z0-9_.-]+\.py$")
    input_files: List[SandboxInputFile] = Field(default_factory=list, max_length=10)
    input_requirement: str = Field(default="none", description="Contract: 'none', 'file', 'tabular', 'numeric_series'")
    required_input_source_ids: List[int] = Field(default_factory=list, description="IDs of authorized knowledge sources that must be staged")
    timeout_seconds: int = Field(default=30, ge=5, le=120)
    cpu_count: float = Field(default=1.0, ge=0.1, le=2.0)
    memory_mb: int = Field(default=512, ge=64, le=1024)
    promote_outputs: bool = False


class CodeExecutionResult(BaseModel):
    """Deterministic result record of sandbox execution."""
    execution_id: str
    status: SandboxStatus
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    duration_ms: int = 0
    timed_out: bool = False
    output_files: List[str] = Field(default_factory=list)
    promoted_artifact_ids: List[int] = Field(default_factory=list)
    provenance: Optional[ExecutionProvenance] = None
    error_message: Optional[str] = None
