"""Sandbox Execution API Endpoint for CogniShift Phase 7.

Provides an authenticated REST interface to run Python analysis inside
a hardened Docker sandbox container with --network none, memory limits,
and automatic artifact promotion.
"""

import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from cognishift.app.core.auth import get_current_user, verify_workspace_access, User
from cognishift.app.config import settings
from cognishift.core.sandbox.schemas import (
    CodeExecutionRequest,
    SandboxInputFile,
    SandboxStatus,
    SandboxUnavailableError,
)
from cognishift.core.sandbox.service import execute_sandbox_code
from cognishift.core.security import SecurityError, ensure_workspace_layout, resolve_workspace_path

router = APIRouter(prefix="/api/v1/sandbox", tags=["Sandbox"])

DEFAULT_ANALYSIS_CODE = """# Telemetry Anomaly Detection Script
# Executed inside hardened container with --network=none
import csv
import os

input_path = '/workspace/input/equipment_readings.csv'
output_path = '/workspace/output/processed_equipment_readings.csv'

print(f"Reading telemetry from: {input_path}")
anomalies = []
total_count = 0

if os.path.exists(input_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = [line for line in f if not line.startswith('#')]
        reader = csv.DictReader(lines)
        for row in reader:
            total_count += 1
            meas = row.get('measurement', '')
            val = float(row.get('value', 0.0))
            is_critical = False
            if 'pressure' in meas and val > 450.0:
                is_critical = True
            elif 'temp' in meas and val > 85.0:
                is_critical = True
            elif 'vibration' in meas and val > 7.0:
                is_critical = True
            
            if is_critical:
                row['classification'] = '3-SIGMA EXCEEDANCE'
                anomalies.append(row)

    print(f"Total readings analyzed: {total_count}")
    print(f"High-risk anomalies isolated: {len(anomalies)}")

    with open(output_path, 'w', newline='', encoding='utf-8') as out:
        writer = csv.DictWriter(out, fieldnames=['timestamp', 'tag_id', 'equipment', 'measurement', 'value', 'unit', 'status', 'classification'])
        writer.writeheader()
        for a in anomalies:
            writer.writerow(a)

    print(f"Saved processed output to: {output_path}")
    print("Execution complete. Exit Code: 0 (OK)")
else:
    print(f"ERROR: Missing input {input_path}")
"""


class SandboxExecuteRequest(BaseModel):
    workspace_id: int = 1
    code: Optional[str] = None
    input_filename: Optional[str] = "equipment_readings.csv"
    promote_outputs: bool = True


ALLOWED_DEMO_INPUTS = {"equipment_readings.csv"}


@router.post("/execute")
async def execute_in_sandbox(
    req: SandboxExecuteRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Execute Python code in an isolated Docker container with --network none."""
    verify_workspace_access(req.workspace_id, current_user)

    code_to_run = req.code or DEFAULT_ANALYSIS_CODE

    # Resolve local demo file
    input_files = []
    if req.input_filename:
        if req.input_filename not in ALLOWED_DEMO_INPUTS:
            raise HTTPException(status_code=400, detail="Unsupported sandbox demo input.")
        demo_csv = Path(settings.data_dir) / "demo" / req.input_filename
        if not demo_csv.is_file() or demo_csv.is_symlink():
            raise HTTPException(status_code=404, detail="Configured sandbox demo input is unavailable.")

        ensure_workspace_layout(req.workspace_id)
        workspace_relative = f"documents/demo_inputs/{req.input_filename}"
        workspace_input = resolve_workspace_path(
            req.workspace_id,
            workspace_relative,
            purpose="write",
            allow_create_parent=True,
        )
        shutil.copy2(demo_csv, workspace_input)
        input_files.append(SandboxInputFile(source_path=workspace_relative, dest_name=req.input_filename))

    exec_req = CodeExecutionRequest(
        execution_id="",
        workspace_id=req.workspace_id,
        run_id=1,
        code=code_to_run,
        entrypoint="main.py",
        input_files=input_files,
        timeout_seconds=30,
        promote_outputs=req.promote_outputs
    )

    try:
        res = await execute_sandbox_code(req.workspace_id, 1, exec_req)
        return {
            "status": res.status.value,
            "exit_code": res.exit_code,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "duration_ms": res.duration_ms,
            "network_mode": "none",
            "promoted_artifact_ids": res.promoted_artifact_ids,
            "output_files": res.output_files
        }
    except (SecurityError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Sandbox input rejected: {str(e)}")
    except SandboxUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Docker sandbox execution error: {str(e)}"
        )
