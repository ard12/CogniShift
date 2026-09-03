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


class CodeExecutionRequest(BaseModel):
    """Fully validated execution payload prepared for sandbox runner."""
    execution_id: str
    workspace_id: int
    run_id: int
    code: str = Field(..., min_length=1, max_length=100000)
    entrypoint: str = Field(default="main.py", pattern=r"^[A-Za-z0-9_.-]+\.py$")
    input_files: List[SandboxInputFile] = Field(default_factory=list, max_length=10)
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
    error_message: Optional[str] = None
