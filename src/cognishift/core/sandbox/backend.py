"""
Sandbox Backend Implementations for CogniShift.
Provides DockerPodmanBackend for real container execution and SimulatedSandboxBackend for unit tests.
Zero host-code execution fallback is guaranteed.
"""
import os
import time
import shutil
import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, Tuple

from cognishift.app.config import settings
from cognishift.core.sandbox.schemas import (
    CodeExecutionRequest,
    CodeExecutionResult,
    SandboxStatus,
    SandboxUnavailableError
)

logger = logging.getLogger(__name__)


class SandboxBackend(ABC):
    """Abstract interface for sandbox execution backends."""

    @abstractmethod
    async def execute(self, request: CodeExecutionRequest, staging_dir: Path) -> CodeExecutionResult:
        """Execute request inside isolated sandbox using staged files."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the backend runtime is available and ready."""
        pass


class DockerPodmanBackend(SandboxBackend):
    """
    Production container-based sandbox backend using Docker or Podman.
    Enforces strict container-level isolation:
    - Zero network (--network none)
    - Read-only root filesystem (--read-only)
    - Non-root UID (--user 10001:10001)
    - All capabilities dropped (--cap-drop ALL)
    - No new privileges (--security-opt no-new-privileges)
    - Strict cgroups limits (CPU, RAM, Swap, PIDs)
    - Bounded wall-clock timeout with explicit kill/remove
    """

    def __init__(self, runtime: Optional[str] = None):
        self.runtime = runtime or settings.sandbox_runtime
        self.runtime_bin = shutil.which(self.runtime)

    async def health_check(self) -> bool:
        if not self.runtime_bin:
            return False
        try:
            proc = await asyncio.create_subprocess_exec(
                self.runtime_bin, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            return proc.returncode == 0
        except Exception:
            return False

    async def execute(self, request: CodeExecutionRequest, staging_dir: Path) -> CodeExecutionResult:
        if not self.runtime_bin or not await self.health_check():
            raise SandboxUnavailableError(
                f"Container runtime '{self.runtime}' is not installed or available on this system. "
                f"Host code execution fallback is strictly prohibited by security policy."
            )

        source_dir = staging_dir / "source"
        input_dir = staging_dir / "input"
        output_dir = staging_dir / "output"
        container_name = f"cognishift-sbx-{request.execution_id}"
        if settings.sandbox_image_digest:
            image_ref = f"{settings.sandbox_image}@{settings.sandbox_image_digest}"
        else:
            image_ref = settings.sandbox_image

        # Construct explicit argument vector (NEVER shell=True)
        argv = [
            self.runtime_bin, "run",
            "--rm",
            "--pull", "never",
            "--network", "none",
            "--read-only",
            "--user", "10001:10001",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--cpus", str(request.cpu_count),
            "--memory", f"{request.memory_mb}m",
            "--memory-swap", f"{request.memory_mb}m",
            "--pids-limit", str(settings.sandbox_pid_limit),
            "-v", f"{str(source_dir.resolve())}:/workspace/source:ro",
            "-v", f"{str(input_dir.resolve())}:/workspace/input:ro",
            "-v", f"{str(output_dir.resolve())}:/workspace/output:rw",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m",
            "-w", "/workspace/source",
            "--name", container_name,
            image_ref,
            "python3", f"/workspace/source/{request.entrypoint}"
        ]

        start_time = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=request.timeout_seconds
                )
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                exit_code = proc.returncode or 0

                # Truncate output streams to server limits
                stdout_truncated = len(stdout_bytes) > settings.sandbox_stdout_limit
                stderr_truncated = len(stderr_bytes) > settings.sandbox_stderr_limit

                stdout_clean = stdout_bytes[:settings.sandbox_stdout_limit].decode("utf-8", errors="replace")
                stderr_clean = stderr_bytes[:settings.sandbox_stderr_limit].decode("utf-8", errors="replace")

                # Check if execution failed due to image missing locally (--pull=never)
                if exit_code != 0 and (
                    "unable to find image" in stderr_clean.lower()
                    or "pull access denied" in stderr_clean.lower()
                    or "image is not available" in stderr_clean.lower()
                    or "repository does not exist" in stderr_clean.lower()
                    or "no such image" in stderr_clean.lower()
                ):
                    raise SandboxUnavailableError(
                        f"Sandbox image '{image_ref}' is not available locally. Automated image pulling is prohibited by security policy."
                    )

                # Determine status
                if exit_code == 0:
                    status = SandboxStatus.SUCCESS
                elif exit_code in [137, 139] and "memory" in stderr_clean.lower():
                    status = SandboxStatus.RESOURCE_EXCEEDED
                else:
                    status = SandboxStatus.RUNTIME_ERROR

                return CodeExecutionResult(
                    execution_id=request.execution_id,
                    status=status,
                    exit_code=exit_code,
                    stdout=stdout_clean,
                    stderr=stderr_clean,
                    stdout_truncated=stdout_truncated,
                    stderr_truncated=stderr_truncated,
                    duration_ms=duration_ms,
                    timed_out=False
                )

            except asyncio.TimeoutError:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                # Explicitly kill and purge container
                try:
                    await asyncio.create_subprocess_exec(self.runtime_bin, "kill", container_name)
                    await asyncio.create_subprocess_exec(self.runtime_bin, "rm", "-f", container_name)
                except Exception as k_err:
                    logger.warning(f"Error killing timed-out container {container_name}: {k_err}")

                return CodeExecutionResult(
                    execution_id=request.execution_id,
                    status=SandboxStatus.TIMEOUT,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Execution exceeded hard timeout limit of {request.timeout_seconds}s.",
                    duration_ms=duration_ms,
                    timed_out=True,
                    error_message=f"Timeout limit of {request.timeout_seconds}s exceeded."
                )

        except SandboxUnavailableError:
            raise
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return CodeExecutionResult(
                execution_id=request.execution_id,
                status=SandboxStatus.INTERNAL_ERROR,
                exit_code=-1,
                stderr=str(e),
                duration_ms=duration_ms,
                timed_out=False,
                error_message=f"Sandbox internal error: {str(e)}"
            )


class SimulatedSandboxBackend(SandboxBackend):
    """
    Deterministic Simulated Sandbox Backend for Unit Testing.
    CRITICAL SECURITY INVARIANT:
    NEVER executes the submitted code! Zero exec(), eval(), subprocess, or host interpreter.
    Returns deterministic results based on request flags and mock triggers.
    """

    async def health_check(self) -> bool:
        return True

    async def execute(self, request: CodeExecutionRequest, staging_dir: Path) -> CodeExecutionResult:
        # Check for simulated error triggers inside code string without executing it
        code_str = request.code
        output_dir = staging_dir / "output"

        if "SIMULATE_TIMEOUT" in code_str:
            return CodeExecutionResult(
                execution_id=request.execution_id,
                status=SandboxStatus.TIMEOUT,
                exit_code=-1,
                stderr=f"Execution exceeded timeout limit of {request.timeout_seconds}s.",
                duration_ms=request.timeout_seconds * 1000,
                timed_out=True,
                error_message="Timeout exceeded."
            )

        if "SIMULATE_RESOURCE_EXCEEDED" in code_str:
            return CodeExecutionResult(
                execution_id=request.execution_id,
                status=SandboxStatus.RESOURCE_EXCEEDED,
                exit_code=137,
                stderr="OOMKilled: Process exceeded memory limit of 512MB.",
                duration_ms=120,
                timed_out=False,
                error_message="Resource limit exceeded."
            )

        if "SIMULATE_RUNTIME_ERROR" in code_str or "1/0" in code_str or "ZeroDivisionError" in code_str:
            return CodeExecutionResult(
                execution_id=request.execution_id,
                status=SandboxStatus.RUNTIME_ERROR,
                exit_code=1,
                stderr="Traceback (most recent call last):\n  File 'main.py', line 1, in <module>\nZeroDivisionError: division by zero",
                duration_ms=85,
                timed_out=False,
                error_message="Process exited with return code 1."
            )

        # Default Success Simulation:
        if request.promote_outputs or "GENERATE_OUTPUT" in code_str:
            # Create a safe simulated output file in output directory
            sim_file = output_dir / "telemetry_summary.csv"
            sim_file.write_text("Sensor,Value,Unit\nPT-101,102.5,PSI\nTT-101,68.4,C\n", encoding="utf-8")

        return CodeExecutionResult(
            execution_id=request.execution_id,
            status=SandboxStatus.SUCCESS,
            exit_code=0,
            stdout=f"[SIMULATED SANDBOX] Execution of '{request.entrypoint}' completed successfully with exit code 0.",
            stderr="",
            duration_ms=45,
            timed_out=False
        )


def get_sandbox_backend() -> SandboxBackend:
    """Factory to retrieve the appropriate sandbox backend based on configuration."""
    if settings.operating_mode == "simulated" or settings.sandbox_runtime == "simulated":
        return SimulatedSandboxBackend()
    return DockerPodmanBackend()
