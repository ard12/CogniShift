"""
Sandbox Execution Orchestration Service.
Coordinates staging, backend container launch, hostile output validation, artifact promotion,
audit event logging, and guaranteed ephemeral cleanup.
"""
import json
import uuid
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from cognishift.app.db.database import get_db
from cognishift.core.sandbox.schemas import (
    CodeExecutionRequest,
    CodeExecutionResult,
    SandboxStatus,
    SandboxUnavailableError
)
from cognishift.core.sandbox.staging import (
    stage_execution_environment,
    cleanup_staging_environment
)
from cognishift.core.sandbox.backend import get_sandbox_backend
from cognishift.core.sandbox.promoter import validate_and_promote_outputs

logger = logging.getLogger(__name__)


async def execute_sandbox_code(
    workspace_id: int,
    run_id: int,
    request: CodeExecutionRequest
) -> CodeExecutionResult:
    """
    Complete lifecycle orchestrator for untrusted code execution:
    1. Ephemeral server-controlled staging.
    2. Isolated container execution (Docker/Podman) or deterministic simulated test backend.
    3. Hostile output inspection and safe Phase 3 artifact promotion.
    4. Audit event logging in SQLite run_events.
    5. Guaranteed ephemeral cleanup in finally: block.
    """
    staging_dir: Optional[Path] = None
    execution_id = request.execution_id or str(uuid.uuid4())

    async def log_event(event_type: str, message: str, structured_data: Dict[str, Any]):
        try:
            async with get_db() as db:
                await db.execute(
                    """
                    INSERT INTO run_events (run_id, event_type, message, structured_data)
                    VALUES (?, ?, ?, ?)
                    """,
                    (run_id, event_type, message, json.dumps(structured_data))
                )
                await db.commit()
        except Exception as e:
            logger.warning(f"Failed to log sandbox event {event_type}: {e}")

    try:
        # 1. Staging
        staging_dir = stage_execution_environment(workspace_id, execution_id, request)

        await log_event(
            "sandbox_execution_started",
            f"Initiated isolated sandbox execution ({execution_id}) for '{request.entrypoint}'.",
            {
                "execution_id": execution_id,
                "entrypoint": request.entrypoint,
                "timeout_seconds": request.timeout_seconds,
                "input_files_count": len(request.input_files)
            }
        )

        # 2. Execution
        backend = get_sandbox_backend()
        result = await backend.execute(request, staging_dir)

        # 3. Output Validation & Promotion
        if result.status == SandboxStatus.SUCCESS and request.promote_outputs:
            promoted_names, promoted_ids = await validate_and_promote_outputs(
                workspace_id=workspace_id,
                run_id=run_id,
                execution_id=execution_id,
                output_dir=staging_dir / "output"
            )
            result.output_files = promoted_names
            result.promoted_artifact_ids = promoted_ids

            if promoted_ids:
                await log_event(
                    "sandbox_artifacts_promoted",
                    f"Promoted {len(promoted_ids)} outputs from sandbox {execution_id} to workspace artifacts.",
                    {"execution_id": execution_id, "artifact_ids": promoted_ids, "filenames": promoted_names}
                )

        # 4. Audit Result Logging
        if result.status == SandboxStatus.SUCCESS:
            await log_event(
                "sandbox_execution_completed",
                f"Sandbox execution {execution_id} completed successfully with exit code 0 ({result.duration_ms}ms).",
                {
                    "execution_id": execution_id,
                    "exit_code": result.exit_code,
                    "duration_ms": result.duration_ms,
                    "stdout_truncated": result.stdout_truncated
                }
            )
        elif result.status == SandboxStatus.TIMEOUT:
            await log_event(
                "sandbox_timeout_exceeded",
                f"Sandbox execution {execution_id} killed after exceeding {request.timeout_seconds}s timeout.",
                {"execution_id": execution_id, "duration_ms": result.duration_ms}
            )
        else:
            await log_event(
                "sandbox_execution_failed",
                f"Sandbox execution {execution_id} terminated with {result.status.value} (exit code {result.exit_code}).",
                {
                    "execution_id": execution_id,
                    "status": result.status.value,
                    "exit_code": result.exit_code,
                    "stderr_snippet": result.stderr[:200]
                }
            )

        return result

    finally:
        # 5. Guaranteed Teardown
        if staging_dir:
            cleanup_staging_environment(staging_dir)
            await log_event(
                "sandbox_cleanup_completed",
                f"Ephemeral sandbox staging directory for {execution_id} removed.",
                {"execution_id": execution_id}
            )
