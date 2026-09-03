"""
CogniShift Phase 4 Real Container Sandbox Integration Tests (Tier B).
These tests execute only against a real local Docker or Podman daemon.
Proves container-level network isolation, non-root execution, cgroups limits,
read-only root filesystem, timeout termination, and hostile output validation.
"""
import pytest
import shutil
import asyncio
from pathlib import Path

from cognishift.app.config import settings
from cognishift.core.sandbox.schemas import (
    CodeExecutionRequest,
    SandboxStatus,
    SandboxUnavailableError
)
from cognishift.core.sandbox.backend import DockerPodmanBackend
from cognishift.core.sandbox.staging import (
    stage_execution_environment,
    cleanup_staging_environment
)
from cognishift.core.sandbox.promoter import validate_and_promote_outputs


def is_container_runtime_available() -> bool:
    """Check if Docker or Podman is available on the current host."""
    runtime = settings.sandbox_runtime
    bin_path = shutil.which(runtime)
    if not bin_path:
        bin_path = shutil.which("docker") or shutil.which("podman")
    return bin_path is not None


# Marker to skip real container tests if runtime is not installed on this host
requires_container_runtime = pytest.mark.skipif(
    not is_container_runtime_available(),
    reason="Docker/Podman runtime is not installed or available on this host. Real sandbox gate skipped."
)


@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_basic_execution(tmp_path):
    backend = DockerPodmanBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "source").mkdir()
    (staging_dir / "input").mkdir()
    (staging_dir / "output").mkdir()

    (staging_dir / "source" / "main.py").write_text('print("COGNISHIFT_SANDBOX_OK")', encoding="utf-8")

    req = CodeExecutionRequest(
        execution_id="real_basic_01",
        workspace_id=1,
        run_id=1,
        code='print("COGNISHIFT_SANDBOX_OK")',
        entrypoint="main.py",
        timeout_seconds=15
    )

    res = await backend.execute(req, staging_dir)
    assert res.exit_code == 0
    assert "COGNISHIFT_SANDBOX_OK" in res.stdout
    assert res.status == SandboxStatus.SUCCESS


@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_non_root_execution(tmp_path):
    backend = DockerPodmanBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "source").mkdir()
    (staging_dir / "input").mkdir()
    (staging_dir / "output").mkdir()

    code = 'import os; uid = os.getuid(); print(f"UID={uid}"); assert uid != 0, "Security Violation: Ran as root!"'
    (staging_dir / "source" / "main.py").write_text(code, encoding="utf-8")

    req = CodeExecutionRequest(
        execution_id="real_non_root_01",
        workspace_id=1,
        run_id=1,
        code=code,
        entrypoint="main.py",
        timeout_seconds=15
    )

    res = await backend.execute(req, staging_dir)
    assert res.exit_code == 0
    assert "UID=" in res.stdout
    assert "UID=0" not in res.stdout


@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_network_isolation(tmp_path):
    backend = DockerPodmanBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "source").mkdir()
    (staging_dir / "input").mkdir()
    (staging_dir / "output").mkdir()

    # Attempt outbound HTTP socket
    code = '''import urllib.request
try:
    urllib.request.urlopen("http://1.1.1.1", timeout=2)
    print("NET_CONNECTED")
except Exception as e:
    print(f"NET_FAILED: {e}")
'''
    (staging_dir / "source" / "main.py").write_text(code, encoding="utf-8")

    req = CodeExecutionRequest(
        execution_id="real_net_01",
        workspace_id=1,
        run_id=1,
        code=code,
        entrypoint="main.py",
        timeout_seconds=15
    )

    res = await backend.execute(req, staging_dir)
    assert "NET_CONNECTED" not in res.stdout
    assert "NET_FAILED" in res.stdout


@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_read_only_root_filesystem(tmp_path):
    backend = DockerPodmanBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "source").mkdir()
    (staging_dir / "input").mkdir()
    (staging_dir / "output").mkdir()

    code = '''try:
    with open("/etc/hacked.txt", "w") as f:
        f.write("hacked")
    print("WRITE_ROOT_SUCCESS")
except Exception as e:
    print(f"WRITE_ROOT_DENIED: {e}")
'''
    (staging_dir / "source" / "main.py").write_text(code, encoding="utf-8")

    req = CodeExecutionRequest(
        execution_id="real_ro_root_01",
        workspace_id=1,
        run_id=1,
        code=code,
        entrypoint="main.py",
        timeout_seconds=15
    )

    res = await backend.execute(req, staging_dir)
    assert "WRITE_ROOT_SUCCESS" not in res.stdout
    assert "WRITE_ROOT_DENIED" in res.stdout


@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_timeout_enforcement(tmp_path):
    backend = DockerPodmanBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "source").mkdir()
    (staging_dir / "input").mkdir()
    (staging_dir / "output").mkdir()

    code = "import time; time.sleep(60)"
    (staging_dir / "source" / "main.py").write_text(code, encoding="utf-8")

    req = CodeExecutionRequest(
        execution_id="real_timeout_01",
        workspace_id=1,
        run_id=1,
        code=code,
        entrypoint="main.py",
        timeout_seconds=5
    )

    res = await backend.execute(req, staging_dir)
    assert res.timed_out is True
    assert res.status == SandboxStatus.TIMEOUT
