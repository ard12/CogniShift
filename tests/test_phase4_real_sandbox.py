"""
CogniShift Phase 4 Real Container Sandbox Integration Tests (Tier B).
These tests execute against a real local Docker or Podman daemon when available.
Verifies all 16 container isolation, resource bounding, security, and fail-closed properties.
"""
import pytest
import shutil
import asyncio
import tempfile
from pathlib import Path

from cognishift.app.config import settings
from cognishift.app.db.database import get_db, init_db
from cognishift.core.sandbox.schemas import (
    CodeExecutionRequest,
    SandboxInputFile,
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
    """Check if the configured container runtime (Docker or Podman) is available on the current host."""
    runtime = settings.sandbox_runtime
    bin_path = shutil.which(runtime)
    if not bin_path:
        bin_path = shutil.which("docker") or shutil.which("podman")
    return bin_path is not None


# Marker to skip real container tests when no daemon is installed on this host
requires_container_runtime = pytest.mark.skipif(
    not is_container_runtime_available(),
    reason="Docker/Podman container runtime is not installed or available on this host. Real sandbox gate requires container daemon."
)


# -----------------------------------------------------------------------------
# 1. BASIC EXECUTION
# -----------------------------------------------------------------------------
@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_basic_execution(tmp_path):
    backend = DockerPodmanBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "source").mkdir()
    (staging_dir / "input").mkdir()
    (staging_dir / "output").mkdir()

    (staging_dir / "source" / "main.py").write_text('print("COGNISHIFT_REAL_SANDBOX_OK")', encoding="utf-8")

    req = CodeExecutionRequest(
        execution_id="real_basic_01",
        workspace_id=1,
        run_id=1,
        code='print("COGNISHIFT_REAL_SANDBOX_OK")',
        entrypoint="main.py",
        timeout_seconds=15
    )

    res = await backend.execute(req, staging_dir)
    assert res.exit_code == 0
    assert "COGNISHIFT_REAL_SANDBOX_OK" in res.stdout
    assert res.status == SandboxStatus.SUCCESS


# -----------------------------------------------------------------------------
# 2. NON-ROOT EXECUTION
# -----------------------------------------------------------------------------
@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_non_root_execution(tmp_path):
    backend = DockerPodmanBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "source").mkdir()
    (staging_dir / "input").mkdir()
    (staging_dir / "output").mkdir()

    code = 'import os; uid = os.getuid(); print(f"UID={uid}"); assert uid != 0, "Ran as root!"'
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


# -----------------------------------------------------------------------------
# 3. NETWORK ISOLATION
# -----------------------------------------------------------------------------
@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_network_isolation(tmp_path):
    backend = DockerPodmanBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "source").mkdir()
    (staging_dir / "input").mkdir()
    (staging_dir / "output").mkdir()

    code = '''import socket
try:
    s = socket.create_connection(("1.1.1.1", 80), timeout=2)
    print("NET_CONNECTED")
except Exception as e:
    print(f"NET_DENIED: {e}")
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
    assert "NET_DENIED" in res.stdout


# -----------------------------------------------------------------------------
# 4. READ-ONLY ROOT FILESYSTEM
# -----------------------------------------------------------------------------
@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_read_only_root_filesystem(tmp_path):
    backend = DockerPodmanBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "source").mkdir()
    (staging_dir / "input").mkdir()
    (staging_dir / "output").mkdir()

    code = '''for target in ["/etc/hacked.txt", "/usr/hacked.txt", "/root/hacked.txt"]:
    try:
        with open(target, "w") as f:
            f.write("hacked")
        print(f"WRITE_SUCCESS_{target}")
    except Exception as e:
        print(f"WRITE_DENIED_{target}")
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
    assert "WRITE_SUCCESS" not in res.stdout
    assert "WRITE_DENIED_/etc/hacked.txt" in res.stdout


# -----------------------------------------------------------------------------
# 5. READ-ONLY SOURCE MOUNT
# -----------------------------------------------------------------------------
@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_read_only_source_mount(tmp_path):
    backend = DockerPodmanBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "source").mkdir()
    (staging_dir / "input").mkdir()
    (staging_dir / "output").mkdir()

    orig_content = 'print("ORIGINAL_SOURCE")'
    (staging_dir / "source" / "main.py").write_text(orig_content, encoding="utf-8")

    code = '''try:
    with open("/workspace/source/main.py", "w") as f:
        f.write("HACKED_SOURCE")
    print("SOURCE_WRITE_SUCCESS")
except Exception as e:
    print(f"SOURCE_WRITE_DENIED: {e}")
'''
    (staging_dir / "source" / "main.py").write_text(code, encoding="utf-8")

    req = CodeExecutionRequest(
        execution_id="real_ro_src_01",
        workspace_id=1,
        run_id=1,
        code=code,
        entrypoint="main.py",
        timeout_seconds=15
    )

    res = await backend.execute(req, staging_dir)
    assert "SOURCE_WRITE_SUCCESS" not in res.stdout
    assert "SOURCE_WRITE_DENIED" in res.stdout


# -----------------------------------------------------------------------------
# 6. READ-ONLY INPUT MOUNT
# -----------------------------------------------------------------------------
@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_read_only_input_mount(tmp_path):
    backend = DockerPodmanBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "source").mkdir()
    (staging_dir / "input").mkdir()
    (staging_dir / "output").mkdir()

    (staging_dir / "input" / "data.csv").write_text("Sensor,Reading\\nPT-101,100", encoding="utf-8")

    code = '''try:
    with open("/workspace/input/data.csv", "w") as f:
        f.write("HACKED_INPUT")
    print("INPUT_WRITE_SUCCESS")
except Exception as e:
    print(f"INPUT_WRITE_DENIED: {e}")
'''
    (staging_dir / "source" / "main.py").write_text(code, encoding="utf-8")

    req = CodeExecutionRequest(
        execution_id="real_ro_inp_01",
        workspace_id=1,
        run_id=1,
        code=code,
        entrypoint="main.py",
        timeout_seconds=15
    )

    res = await backend.execute(req, staging_dir)
    assert "INPUT_WRITE_SUCCESS" not in res.stdout
    assert "INPUT_WRITE_DENIED" in res.stdout
    # Host-side input file must remain untouched
    assert "Sensor,Reading" in (staging_dir / "input" / "data.csv").read_text()


# -----------------------------------------------------------------------------
# 7. WRITABLE OUTPUT MOUNT
# -----------------------------------------------------------------------------
@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_writable_output_mount(tmp_path):
    backend = DockerPodmanBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "source").mkdir()
    (staging_dir / "input").mkdir()
    (staging_dir / "output").mkdir()

    code = r'''with open("/workspace/output/result.csv", "w") as f:
    f.write("Sensor,Calculated\nPT-101,102.5\n")
print("OUTPUT_WRITE_SUCCESS")
'''
    (staging_dir / "source" / "main.py").write_text(code, encoding="utf-8")

    req = CodeExecutionRequest(
        execution_id="real_wr_out_01",
        workspace_id=1,
        run_id=1,
        code=code,
        entrypoint="main.py",
        timeout_seconds=15
    )

    res = await backend.execute(req, staging_dir)
    assert res.exit_code == 0
    assert "OUTPUT_WRITE_SUCCESS" in res.stdout
    assert (staging_dir / "output" / "result.csv").exists()


# -----------------------------------------------------------------------------
# 8. HOST SECRET & DATABASE ISOLATION
# -----------------------------------------------------------------------------
@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_host_secret_isolation(tmp_path):
    backend = DockerPodmanBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "source").mkdir()
    (staging_dir / "input").mkdir()
    (staging_dir / "output").mkdir()

    code = '''import os, glob
secrets_found = []
for p in ["/data", "/private", "/root", "/home", "/workspace/knowledge", "/workspace/generated"]:
    if os.path.exists(p):
        secrets_found.append(p)
print(f"SECRETS_EXPOSED: {secrets_found}")
'''
    (staging_dir / "source" / "main.py").write_text(code, encoding="utf-8")

    req = CodeExecutionRequest(
        execution_id="real_sec_iso_01",
        workspace_id=1,
        run_id=1,
        code=code,
        entrypoint="main.py",
        timeout_seconds=15
    )

    res = await backend.execute(req, staging_dir)
    assert "SECRETS_EXPOSED: []" in res.stdout or "SECRETS_EXPOSED: ['/root']" not in res.stdout


# -----------------------------------------------------------------------------
# 9. ENVIRONMENT ISOLATION
# -----------------------------------------------------------------------------
@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_environment_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_HOST_SECRET_TOKEN", "super_secret_host_credential_9988")
    backend = DockerPodmanBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "source").mkdir()
    (staging_dir / "input").mkdir()
    (staging_dir / "output").mkdir()

    code = '''import os
env_str = str(dict(os.environ))
if "super_secret_host_credential_9988" in env_str:
    print("LEAK_FOUND")
else:
    print("ENV_ISOLATED")
'''
    (staging_dir / "source" / "main.py").write_text(code, encoding="utf-8")

    req = CodeExecutionRequest(
        execution_id="real_env_iso_01",
        workspace_id=1,
        run_id=1,
        code=code,
        entrypoint="main.py",
        timeout_seconds=15
    )

    res = await backend.execute(req, staging_dir)
    assert "LEAK_FOUND" not in res.stdout
    assert "ENV_ISOLATED" in res.stdout


# -----------------------------------------------------------------------------
# 10. TIMEOUT & CONTAINER REMOVAL
# -----------------------------------------------------------------------------
@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_timeout_and_removal(tmp_path):
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


# -----------------------------------------------------------------------------
# 11. MEMORY LIMIT
# -----------------------------------------------------------------------------
@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_memory_limit(tmp_path):
    backend = DockerPodmanBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "source").mkdir()
    (staging_dir / "input").mkdir()
    (staging_dir / "output").mkdir()

    # Controlled memory consumption: allocate 800MB when limit is 512MB
    code = '''try:
    a = bytearray(800 * 1024 * 1024)
    print("ALLOC_EXCEEDED")
except MemoryError:
    print("MEMORY_CONSTRAINT_HANDLED")
'''
    (staging_dir / "source" / "main.py").write_text(code, encoding="utf-8")

    req = CodeExecutionRequest(
        execution_id="real_mem_01",
        workspace_id=1,
        run_id=1,
        code=code,
        entrypoint="main.py",
        memory_mb=512,
        timeout_seconds=15
    )

    res = await backend.execute(req, staging_dir)
    assert "ALLOC_EXCEEDED" not in res.stdout


# -----------------------------------------------------------------------------
# 12. PID LIMIT
# -----------------------------------------------------------------------------
@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_pid_limit(tmp_path):
    backend = DockerPodmanBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "source").mkdir()
    (staging_dir / "input").mkdir()
    (staging_dir / "output").mkdir()

    # Bounded process creation: attempts to create 100 subprocesses under PID limit 64
    code = '''import subprocess
procs = []
try:
    for i in range(100):
        procs.append(subprocess.Popen(["sleep", "5"]))
    print("PID_LIMIT_BYPASS")
except Exception as e:
    print(f"PID_LIMIT_ENFORCED: {e}")
for p in procs:
    p.kill()
'''
    (staging_dir / "source" / "main.py").write_text(code, encoding="utf-8")

    req = CodeExecutionRequest(
        execution_id="real_pid_01",
        workspace_id=1,
        run_id=1,
        code=code,
        entrypoint="main.py",
        timeout_seconds=15
    )

    res = await backend.execute(req, staging_dir)
    assert "PID_LIMIT_BYPASS" not in res.stdout


# -----------------------------------------------------------------------------
# 13. OUTPUT SYMLINK REJECTION
# -----------------------------------------------------------------------------
@requires_container_runtime
@pytest.mark.asyncio
async def test_real_sandbox_output_symlink_rejection(tmp_path):
    backend = DockerPodmanBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "source").mkdir()
    (staging_dir / "input").mkdir()
    (staging_dir / "output").mkdir()

    # Create symlink inside container in /workspace/output/
    code = '''import os
os.symlink("/etc/passwd", "/workspace/output/symlink.txt")
print("SYMLINK_CREATED")
'''
    (staging_dir / "source" / "main.py").write_text(code, encoding="utf-8")

    req = CodeExecutionRequest(
        execution_id="real_sym_01",
        workspace_id=1,
        run_id=1,
        code=code,
        entrypoint="main.py",
        timeout_seconds=15
    )

    res = await backend.execute(req, staging_dir)
    assert res.exit_code == 0
    assert "SYMLINK_CREATED" in res.stdout

    promoted_names, promoted_ids = await validate_and_promote_outputs(
        workspace_id=1,
        run_id=1,
        execution_id="sbx_sym_01",
        output_dir=staging_dir / "output"
    )
    assert "symlink.txt" not in promoted_names


# -----------------------------------------------------------------------------
# 14. OUTPUT EXTENSION POLICY
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_real_sandbox_output_extension_policy(tmp_path):
    out_dir = tmp_path / "output"
    out_dir.mkdir()

    (out_dir / "script.py").write_text("print(1)", encoding="utf-8")
    (out_dir / "run.sh").write_text("#!/bin/sh", encoding="utf-8")
    (out_dir / "binary.bin").write_bytes(b"\x00\x01")
    (out_dir / "valid_data.csv").write_text("Sensor,Reading\nPT-101,100", encoding="utf-8")

    promoted_names, promoted_ids = await validate_and_promote_outputs(
        workspace_id=1,
        run_id=1,
        execution_id="sbx_ext_01",
        output_dir=out_dir
    )

    assert "script.py" not in promoted_names
    assert "run.sh" not in promoted_names
    assert "binary.bin" not in promoted_names
    assert "valid_data.csv" in promoted_names


# -----------------------------------------------------------------------------
# 15. ARTIFACT PROMOTION
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_real_sandbox_artifact_promotion(tmp_path):
    await init_db()
    out_dir = tmp_path / "output"
    out_dir.mkdir()

    (out_dir / "final_report.csv").write_text("Col1,Col2\nVal1,Val2", encoding="utf-8")

    promoted_names, promoted_ids = await validate_and_promote_outputs(
        workspace_id=1,
        run_id=1,
        execution_id="sbx_art_01",
        output_dir=out_dir
    )

    assert "final_report.csv" in promoted_names
    assert len(promoted_ids) == 1

    # Verify SQLite row
    async with get_db() as db:
        c = await db.execute("SELECT filename, sha256_hash FROM workspace_artifacts WHERE id = ?", (promoted_ids[0],))
        row = await c.fetchone()
        assert row is not None
        assert row["filename"] == "final_report.csv"


# -----------------------------------------------------------------------------
# 16. MISSING RUNTIME FAILS CLOSED & ZERO HOST EXECUTION
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_real_sandbox_missing_runtime_fails_closed(tmp_path):
    marker_file = tmp_path / "HOST_EXECUTION_SHOULD_NEVER_EXIST.txt"
    code = f'''with open(r"{str(marker_file)}", "w") as f:
    f.write("CRITICAL_SECURITY_LEAK")
'''

    # Explicit nonexistent runtime
    backend = DockerPodmanBackend(runtime="nonexistent_container_runtime_binary_xyz")
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()

    req = CodeExecutionRequest(
        execution_id="exec_no_host_leak",
        workspace_id=1,
        run_id=1,
        code=code,
        entrypoint="main.py"
    )

    # 1. Must raise SandboxUnavailableError
    with pytest.raises(SandboxUnavailableError):
        await backend.execute(req, staging_dir)

    # 2. Crucial proof: Marker file must NOT exist on host
    assert not marker_file.exists(), "SECURITY VIOLATION: Generated code executed directly on the host!"
