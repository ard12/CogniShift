"""Real capability probes and regressions; submitted code executes only in Docker."""
import json
import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError
from cognishift.app.config import settings
from cognishift.core.sandbox.backend import DockerPodmanBackend, read_bounded
from cognishift.core.sandbox.schemas import CodeExecutionRequest, SandboxInputFile, SandboxStatus
from cognishift.core.sandbox.service import execute_sandbox_code
from cognishift.core.sandbox.promoter import validate_and_promote_outputs
from test_phase4_real_sandbox import requires_container_runtime, setup_sandbox_db


PROBES = [
    ("engineering_math", "import math,statistics,decimal; assert math.isclose(math.pi*2**2,12.566370614359172); assert statistics.mean([10,20,30])==20; print('OK')", "success"),
    ("csv_json_sqlite", "import csv,io,json,sqlite3; rows=list(csv.DictReader(io.StringIO('x,y\\n2,3\\n'))); db=sqlite3.connect(':memory:'); assert db.execute('select 2+3').fetchone()[0]==5; assert json.loads(json.dumps(rows))[0]['x']=='2'; print('OK')", "success"),
    ("subprocess_inside_container", "import subprocess; assert subprocess.check_output(['python3','-c','print(42)'],text=True).strip()=='42'; print('OK')", "success"),
    ("temporary_files", "import tempfile; f=tempfile.TemporaryFile(); f.write(b'hello'); f.seek(0); assert f.read()==b'hello'; print('OK')", "success"),
    ("missing_package", "import non_existent_package_xyz", "runtime_error"),
    ("syntax_error", "def broken(", "runtime_error"),
    ("runtime_traceback", "raise ValueError('intentional probe')", "runtime_error"),
    ("bounded_streams", "import sys; print('x'*200000); print('e'*200000,file=sys.stderr)", "success"),
    ("privileges", "import pathlib; s=pathlib.Path('/proc/self/status').read_text(); assert 'CapEff:\\t0000000000000000' in s; assert 'NoNewPrivs:\\t1' in s; assert not pathlib.Path('/var/run/docker.sock').exists(); print('OK')", "success"),
]


@requires_container_runtime
@pytest.mark.asyncio
@pytest.mark.parametrize("name,code,expected", PROBES, ids=[p[0] for p in PROBES])
async def test_real_capability(name, code, expected, tmp_path):
    for directory in ('source', 'input', 'output'):
        (tmp_path / directory).mkdir()
    (tmp_path / 'source' / 'main.py').write_text(code, encoding='utf-8')
    request = CodeExecutionRequest(execution_id='probe_'+uuid.uuid4().hex, workspace_id=1, run_id=1, code=code)
    result = await DockerPodmanBackend().execute(request, tmp_path)
    assert result.status.value == expected, result.stderr
    if name == 'bounded_streams':
        assert result.stdout_truncated and result.stderr_truncated
        assert len(result.stdout) == settings.sandbox_stdout_limit
        assert len(result.stderr) == settings.sandbox_stderr_limit
    elif expected == 'success':
        assert 'OK' in result.stdout
    else:
        assert result.exit_code != 0 and result.stderr


@requires_container_runtime
@pytest.mark.asyncio
async def test_real_service_generated_id_promotion_and_cleanup(monkeypatch):
    from cognishift.core.security import get_workspace_root
    monkeypatch.setattr(settings, 'operating_mode', 'local')
    monkeypatch.setattr(settings, 'sandbox_runtime', 'docker')
    code = "from pathlib import Path; Path('/workspace/output/result.csv').write_text('value\\n42\\n'); print('OK')"
    request = CodeExecutionRequest(execution_id='', workspace_id=1, run_id=1, code=code, promote_outputs=True)
    result = await execute_sandbox_code(1, 1, request)
    assert result.status == SandboxStatus.SUCCESS, result.stderr
    assert result.execution_id
    assert result.output_files == ['result.csv']
    assert len(result.promoted_artifact_ids) == 1
    assert not (get_workspace_root(1) / 'temporary' / ('sandbox_'+result.execution_id)).exists()


@pytest.mark.asyncio
async def test_hardlink_output_rejected(tmp_path):
    original = tmp_path / 'original.txt'
    original.write_text('synthetic hardlink probe')
    output = tmp_path / 'output'
    output.mkdir()
    os.link(original, output / 'linked.txt')
    assert await validate_and_promote_outputs(1, 1, 'hardlink_probe', output) == ([], [])


@pytest.mark.parametrize('name', ['.', '..'])
def test_directory_input_names_rejected(name):
    with pytest.raises(ValidationError):
        SandboxInputFile(source_path='documents/a.csv', dest_name=name)


@pytest.mark.asyncio
async def test_health_requires_daemon():
    backend = DockerPodmanBackend()
    backend.runtime_bin = 'docker'
    proc = AsyncMock()
    proc.returncode = 1
    with patch('asyncio.create_subprocess_exec', return_value=proc) as spawn:
        assert await backend.health_check() is False
        assert spawn.call_args.args == ('docker', 'info')


@pytest.mark.asyncio
async def test_bounded_reader_drains_entire_stream():
    stream = AsyncMock()
    stream.read.side_effect = [b'1234', b'5678', b'90', b'']
    assert await read_bounded(stream, 5) == (b'12345', True)
    assert stream.read.await_count == 4


@pytest.mark.asyncio
async def test_disabled_sandbox_cannot_stage_or_execute(monkeypatch):
    from cognishift.core.sandbox.schemas import SandboxUnavailableError
    monkeypatch.setattr(settings, 'sandbox_enabled', False)
    req = CodeExecutionRequest(execution_id='', workspace_id=1, run_id=1, code='print(1)')
    with patch('cognishift.core.sandbox.service.stage_execution_environment') as stage:
        with pytest.raises(SandboxUnavailableError, match='disabled'):
            await execute_sandbox_code(1, 1, req)
        stage.assert_not_called()


def test_duplicate_execution_does_not_erase_files():
    from cognishift.core.sandbox.staging import stage_execution_environment, cleanup_staging_environment
    req = CodeExecutionRequest(execution_id='collision_probe', workspace_id=1, run_id=1, code='print(1)')
    directory = stage_execution_environment(1, req.execution_id, req)
    try:
        marker = directory / 'output' / 'keep.txt'
        marker.write_text('preserve')
        with pytest.raises(FileExistsError):
            stage_execution_environment(1, req.execution_id, req)
        assert marker.read_text() == 'preserve'
    finally:
        cleanup_staging_environment(directory)


def test_invalid_input_cleans_partial_staging():
    from cognishift.core.sandbox.staging import stage_execution_environment
    from cognishift.core.security import get_workspace_root
    req = CodeExecutionRequest(execution_id='bad_input_probe', workspace_id=1, run_id=1,
        code='print(1)', input_files=[SandboxInputFile(source_path='documents/missing-input.csv', dest_name='input.csv')])
    with pytest.raises(Exception):
        stage_execution_environment(1, req.execution_id, req)
    assert not (get_workspace_root(1) / 'temporary' / 'sandbox_bad_input_probe').exists()


@pytest.mark.asyncio
async def test_server_resource_caps_override_request(monkeypatch, tmp_path):
    from cognishift.core.sandbox.schemas import CodeExecutionResult
    monkeypatch.setattr(settings, 'sandbox_cpu_limit', 0.5)
    monkeypatch.setattr(settings, 'sandbox_memory_mb', 128)
    monkeypatch.setattr(settings, 'sandbox_max_timeout', 10)
    backend = AsyncMock()
    backend.execute.return_value = CodeExecutionResult(execution_id='limits', status=SandboxStatus.SUCCESS, exit_code=0)
    req = CodeExecutionRequest(execution_id='limits', workspace_id=2, run_id=2,
        code='print(1)', cpu_count=2, memory_mb=1024, timeout_seconds=120)
    with patch('cognishift.core.sandbox.service.stage_execution_environment', return_value=tmp_path / 'unused'), patch('cognishift.core.sandbox.service.get_sandbox_backend', return_value=backend):
        await execute_sandbox_code(1, 1, req)
    passed = backend.execute.call_args.args[0]
    assert (passed.cpu_count, passed.memory_mb, passed.timeout_seconds) == (0.5, 128, 10)
    assert (passed.workspace_id, passed.run_id) == (1, 1)
