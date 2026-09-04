import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
TELEMETRY_PATH = DATA_DIR / "telemetry_stream_tep.json"
MAINTENANCE_PATH = DATA_DIR / "maintenance_orders_sap_pm.json"
TOPOLOGY_PATH = DATA_DIR / "refinery_topology_iso15926.json"


def _load_json(file_path: Path) -> Optional[Dict[str, Any]]:
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load {file_path}: {e}")
    return None


def load_tep_telemetry() -> Dict[str, Any]:
    """Load dynamic Tennessee Eastman SCADA telemetry."""
    return _load_json(TELEMETRY_PATH) or {}


def load_maintenance_orders() -> Dict[str, Any]:
    """Load SAP S/4HANA PM maintenance orders."""
    return _load_json(MAINTENANCE_PATH) or {}


def load_refinery_topology() -> Dict[str, Any]:
    """Load ISO 15926 refinery equipment topology."""
    return _load_json(TOPOLOGY_PATH) or {}


async def execute_tool(
    tool_name: str,
    parameters: dict,
    workspace_id: Optional[int] = None,
    run_id: Optional[int] = None
) -> str:
    """
    Executes tool logic grounded in authentic industrial datasets:
    - Tennessee Eastman Process (TEP) dynamic telemetry
    - ISO 15926 / ISA-95 Plant Topology & P&ID connections
    - SAP S/4HANA PM work order logs and ISO 14224 FMEA
    Strictly simulated to maintain the zero arbitrary command execution security constraint.
    """
    logger.info(f"Executing tool: {tool_name} with params: {parameters}")
    scenario_override = parameters.get("scenario")

    if tool_name == "check_pressure":
        sensor_id = parameters.get("sensor_id", "PT-101").upper()
        tep_data = _load_json(TELEMETRY_PATH)
        
        # Check if a specific TEP scenario is requested or surge triggered
        if tep_data and "scenarios" in tep_data:
            target_scen = None
            if scenario_override:
                target_scen = next((s for s in tep_data["scenarios"] if scenario_override.lower() in s["scenario_id"].lower()), None)
            
            # Default to overpressure surge if requested or parameter indicates emergency
            if not target_scen and any(k in str(parameters).lower() for k in ["surge", "emergency", "high", "trip", "450"]):
                target_scen = next((s for s in tep_data["scenarios"] if "SURGE" in s["scenario_id"]), None)
            
            if target_scen:
                points = [p for p in target_scen.get("telemetry_points", []) if p.get("sensor") == sensor_id]
                if points:
                    pt = points[-1]
                    val = pt.get("value")
                    status = pt.get("status")
                    if val and val > 450.0:
                        return (
                            f"[TEP {target_scen['fault_code']}] Sensor {sensor_id} reports pressure is {val} PSI "
                            f"(Alarm High: 140.0 PSI, Critical Trip: 450.0 PSI). Status: {status}. "
                            f"CRITICAL OVERPRESSURE: MAWP 500.0 PSI boundary threatened. Emergency venting required per OISD-STD-106."
                        )
                    return f"Sensor {sensor_id} reports pressure is {val} PSI. Status: {status}."

        # Nominal TEP baseline (IDV 0)
        return f"Sensor {sensor_id} reports pressure is 105.2 PSI (Normal Operating Range: 80.0 - 120.0 PSI). Status: NOMINAL."

    elif tool_name == "check_temperature":
        sensor_id = parameters.get("sensor_id", "TT-204").upper()
        tep_data = _load_json(TELEMETRY_PATH)
        
        if tep_data and "scenarios" in tep_data:
            target_scen = None
            if scenario_override:
                target_scen = next((s for s in tep_data["scenarios"] if scenario_override.lower() in s["scenario_id"].lower()), None)
            elif any(k in str(parameters).lower() for k in ["bearing", "drift", "overheat", "stick", "trip"]):
                target_scen = next((s for s in tep_data["scenarios"] if "BEARING" in s["scenario_id"]), None)
            
            if target_scen:
                points = [p for p in target_scen.get("telemetry_points", []) if p.get("sensor") == sensor_id]
                if points:
                    pt = points[-1]
                    val = pt.get("value")
                    status = pt.get("status")
                    if val and val >= 95.0:
                        return (
                            f"[TEP {target_scen['fault_code']}] Thermocouple {sensor_id} reports bearing metal temperature is {val} C "
                            f"(Normal Range: 60.0 - 80.0 C, Trip Threshold: 95.0 C). Status: {status}. "
                            f"EMERGENCY TRIP MANDATORY per OISD-STD-240."
                        )
                    return f"Thermocouple {sensor_id} reports temperature is {val} C. Status: {status}."

        return f"Thermocouple {sensor_id} reports bearing temperature is 68.4 C (Normal Operating Range: 60.0 - 80.0 C). Status: NORMAL."

    elif tool_name == "run_diagnostic":
        subsystem = parameters.get("subsystem", "P-101A Crude Feed Booster Pump")
        maint_data = _load_json(MAINTENANCE_PATH)
        past_order = ""
        if maint_data and "orders" in maint_data:
            match = next((o for o in maint_data["orders"] if "101" in o.get("equipment_tag", "")), None)
            if match:
                past_order = f" Past SAP PM Order {match['order_number']}: {match['damage_code']} resolved via {match['corrective_actions_taken'][0]}."
        
        return (
            f"Telemetry diagnostic completed for {subsystem}: Dual cartridge mechanical seal (API 682 Plan 53A) "
            f"barrier pressure differential is +20 PSI. Vibration FFT spectrum shows 2.4 mm/s RMS (ISO 10816 Zone B - Acceptable)."
            f"{past_order} Overall asset health: DEPLOYABLE."
        )

    elif tool_name == "emergency_pressure_relief":
        chamber_id = parameters.get("chamber_id", "Reactor-B")
        valve_tag = parameters.get("valve_tag", "SV-402")
        return (
            f"[STATUTORY EMERGENCY RELIEF EXECUTED] Pilot valve {valve_tag} actuated on {chamber_id} per OISD-STD-106. "
            f"Discharged 35.0 PSI hydrogen/hydrocarbon vapor into High-Pressure Acid Gas Flare Header. "
            f"Transmitter PT-101 pressure dropping to safe envelope. Shift incident report automatically generated."
        )

    elif tool_name == "restart_component":
        component_id = parameters.get("component_id", "P-101A")
        return (
            f"[SUPERVISED RESTART EXECUTED] Motor breaker for {component_id} re-engaged under permit OISD-STD-240. "
            f"Inrush current nominal at 48.2A, pump reached rated speed 2950 RPM. Discharge pressure established at 104.5 PSI."
        )

    elif tool_name == "check_maintenance_order":
        order_no = str(parameters.get("order_number", "400829104"))
        maint_data = _load_json(MAINTENANCE_PATH)
        if maint_data and "orders" in maint_data:
            match = next((o for o in maint_data["orders"] if order_no in o.get("order_number", "")), None)
            if match:
                return (
                    f"SAP PM Order #{match['order_number']} [{match['notification_type']}]: "
                    f"Asset {match['equipment_tag']} ({match['functional_location']}). "
                    f"Damage: {match['damage_code']}, Cause: {match['cause_code']}. "
                    f"Actions: {'; '.join(match['corrective_actions_taken'])}. "
                    f"Signed by: {match['supervisor_sign_off']}. Status: {match['system_status']}."
                )
        return f"SAP PM Order #{order_no} not found in current plant maintenance ledger."

    elif tool_name == "check_network":
        segment = parameters.get("segment", "SCADA-VLAN-10")
        return f"Industrial Ethernet segment {segment} is ONLINE. Gateway: 10.14.0.1, Round-trip latency: 1.8ms, Packet drop: 0%."

    elif tool_name == "restart_service":
        service_name = parameters.get("service_name", "modbus_telemetry_collector")
        return f"Industrial daemon '{service_name}' restarted cleanly under supervisor PID 1842."

    elif tool_name == "check_interlock_status":
        subsystem = parameters.get("subsystem", "P-101A Centrifugal Pump")
        return f"Local tool 'check_interlock_status' executed successfully: Interlocks for {subsystem} are armed. Trip threshold: 450.0 PSI, Bearing temp threshold: 95.0 C."

    # Phase 3 Safe File and Document Tools
    elif tool_name == "file_list":
        from cognishift.core.security import (
            resolve_workspace_path,
            validate_workspace_filesystem_policy,
            get_workspace_root,
            INTERNAL_SUBSYSTEM_ROOTS
        )
        directory = parameters.get("directory", "documents")
        ws_id = workspace_id or parameters.get("workspace_id", 1)
        try:
            target_path = resolve_workspace_path(ws_id, directory, purpose="read")
            validate_workspace_filesystem_policy(ws_id, target_path, operation="list")
            if not target_path.exists():
                return f"Directory '{directory}' does not exist in workspace {ws_id}."
            if not target_path.is_dir():
                return f"Path '{directory}' is a file, not a directory."
            ws_root = get_workspace_root(ws_id)
            is_root = (target_path.resolve() == ws_root.resolve())
            entries = []
            for item in sorted(target_path.iterdir()):
                # Hide internal subsystem directories when listing workspace root
                if is_root and item.name.lower() in INTERNAL_SUBSYSTEM_ROOTS:
                    continue
                entries.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0
                })
            return json.dumps(entries, indent=2)
        except Exception as e:
            return f"Error listing directory '{directory}': {str(e)}"

    elif tool_name == "file_read":
        from cognishift.core.security import resolve_workspace_path, validate_workspace_filesystem_policy
        file_path = parameters.get("file_path", "")
        raw_mb = parameters.get("max_bytes", 65536)
        try:
            parsed_mb = int(raw_mb)
        except (ValueError, TypeError):
            parsed_mb = 65536
        # Defense-in-depth: Strictly clamp between 1 and 1,048,576
        max_bytes = max(1, min(parsed_mb, 1048576))
        ws_id = workspace_id or parameters.get("workspace_id", 1)
        try:
            target_path = resolve_workspace_path(ws_id, file_path, purpose="read")
            validate_workspace_filesystem_policy(ws_id, target_path, operation="read")
            if not target_path.exists():
                return f"File '{file_path}' does not exist in workspace {ws_id}."
            if not target_path.is_file():
                return f"Path '{file_path}' is a directory, not a readable file."
            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_bytes)
            return content
        except Exception as e:
            return f"Error reading file '{file_path}': {str(e)}"

    elif tool_name == "file_write":
        from cognishift.core.security import (
            resolve_workspace_path,
            validate_workspace_filesystem_policy,
            get_workspace_root
        )
        from cognishift.app.db.database import get_db
        file_path = parameters.get("file_path", "")
        content = parameters.get("content", "")
        overwrite = bool(parameters.get("overwrite", False))
        ws_id = workspace_id or parameters.get("workspace_id", 1)
        try:
            target_path = resolve_workspace_path(ws_id, file_path, purpose="write", allow_create_parent=True)
            # 1. Enforce Central Workspace Filesystem Policy (documents/ only for generic write)
            validate_workspace_filesystem_policy(ws_id, target_path, operation="write")

            # 2. Canonical OS Case-Normalized Immutability Check
            ws_root = get_workspace_root(ws_id)
            canonical_target = os.path.normcase(str(target_path.resolve()))
            async with get_db() as db:
                c = await db.execute("SELECT relative_path FROM workspace_artifacts WHERE workspace_id = ?", (ws_id,))
                rows = await c.fetchall()
                for r in rows:
                    art_path = (ws_root / r["relative_path"]).resolve()
                    if canonical_target == os.path.normcase(str(art_path)):
                        return f"Security Error: Cannot overwrite registered immutable artifact '{file_path}' through generic file_write."

            if target_path.exists() and not overwrite:
                return f"Error: File '{file_path}' already exists and overwrite is set to False."

            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote {len(content)} characters to '{file_path}'."
        except Exception as e:
            return f"Error writing file '{file_path}': {str(e)}"

    elif tool_name == "directory_create":
        from cognishift.core.security import resolve_workspace_path, validate_workspace_filesystem_policy
        directory_path = parameters.get("directory_path", "")
        ws_id = workspace_id or parameters.get("workspace_id", 1)
        try:
            target_path = resolve_workspace_path(ws_id, directory_path, purpose="write", allow_create_parent=True)
            validate_workspace_filesystem_policy(ws_id, target_path, operation="mkdir")
            target_path.mkdir(parents=True, exist_ok=True)
            return f"Directory '{directory_path}' successfully created in workspace {ws_id}."
        except Exception as e:
            return f"Error creating directory '{directory_path}': {str(e)}"

    elif tool_name == "generate_docx":
        from cognishift.core.artifact_generators import create_and_register_artifact, generate_docx_document
        filename = parameters.get("filename", "report.docx")
        title = parameters.get("title", "Plant Engineering Report")
        sections = parameters.get("sections", [])
        ws_id = workspace_id or parameters.get("workspace_id", 1)
        try:
            artifact = await create_and_register_artifact(
                workspace_id=ws_id,
                filename=filename,
                artifact_type="docx",
                generator_fn=lambda p: generate_docx_document(p, title, sections),
                title=title,
                description="Generated DOCX Engineering Report",
                run_id=run_id
            )
            return (
                f"Successfully generated and registered DOCX artifact #{artifact['id']}: '{artifact['relative_path']}' "
                f"(SHA-256: {artifact['sha256_hash'][:16]}..., Size: {artifact['file_size']} bytes)."
            )
        except Exception as e:
            return f"Error generating DOCX artifact: {str(e)}"

    elif tool_name == "generate_xlsx":
        from cognishift.core.artifact_generators import create_and_register_artifact, generate_xlsx_workbook
        filename = parameters.get("filename", "telemetry.xlsx")
        title = parameters.get("title", "Plant Telemetry Workbook")
        sheets = parameters.get("sheets", [])
        ws_id = workspace_id or parameters.get("workspace_id", 1)
        try:
            artifact = await create_and_register_artifact(
                workspace_id=ws_id,
                filename=filename,
                artifact_type="xlsx",
                generator_fn=lambda p: generate_xlsx_workbook(p, title, sheets),
                title=title,
                description="Generated XLSX Telemetry Workbook",
                run_id=run_id
            )
            return (
                f"Successfully generated and registered XLSX artifact #{artifact['id']}: '{artifact['relative_path']}' "
                f"(SHA-256: {artifact['sha256_hash'][:16]}..., Size: {artifact['file_size']} bytes)."
            )
        except Exception as e:
            return f"Error generating XLSX artifact: {str(e)}"

    elif tool_name == "generate_pptx":
        from cognishift.core.artifact_generators import create_and_register_artifact, generate_pptx_presentation
        filename = parameters.get("filename", "briefing.pptx")
        title = parameters.get("title", "Plant Operations Briefing")
        subtitle = parameters.get("subtitle")
        slides = parameters.get("slides", [])
        ws_id = workspace_id or parameters.get("workspace_id", 1)
        try:
            artifact = await create_and_register_artifact(
                workspace_id=ws_id,
                filename=filename,
                artifact_type="pptx",
                generator_fn=lambda p: generate_pptx_presentation(p, title, subtitle, slides),
                title=title,
                description="Generated PPTX Executive Presentation",
                run_id=run_id
            )
            return (
                f"Successfully generated and registered PPTX artifact #{artifact['id']}: '{artifact['relative_path']}' "
                f"(SHA-256: {artifact['sha256_hash'][:16]}..., Size: {artifact['file_size']} bytes)."
            )
        except Exception as e:
            return f"Error generating PPTX artifact: {str(e)}"

    elif tool_name == "execute_code":
        from cognishift.core.sandbox.schemas import CodeExecutionRequest, SandboxInputFile, SandboxStatus
        from cognishift.core.sandbox.service import execute_sandbox_code
        
        ws_id = workspace_id or parameters.get("workspace_id", 1)
        r_id = run_id or parameters.get("run_id", 1)
        code = parameters.get("code", "")
        entrypoint = parameters.get("entrypoint", "main.py")
        timeout_seconds = parameters.get("timeout_seconds", 30)
        promote = parameters.get("promote_outputs_to_artifacts", False)
        
        input_refs = []
        for inp in parameters.get("input_files", []):
            if isinstance(inp, dict):
                input_refs.append(SandboxInputFile(source_path=inp.get("source_path", ""), dest_name=inp.get("dest_name", "")))
            elif hasattr(inp, "source_path"):
                input_refs.append(inp)

        req = CodeExecutionRequest(
            execution_id="",
            workspace_id=ws_id,
            run_id=r_id,
            code=code,
            entrypoint=entrypoint,
            input_files=input_refs,
            timeout_seconds=timeout_seconds,
            promote_outputs=promote
        )
        
        try:
            exec_res = await execute_sandbox_code(ws_id, r_id, req)
            if exec_res.status == SandboxStatus.SUCCESS:
                out_msg = f"Sandbox execution succeeded (exit code 0, {exec_res.duration_ms}ms)."
                if exec_res.stdout:
                    out_msg += f"\nSTDOUT:\n{exec_res.stdout}"
                if exec_res.promoted_artifact_ids:
                    out_msg += f"\nPromoted {len(exec_res.promoted_artifact_ids)} artifacts: {exec_res.output_files}"
                return out_msg
            elif exec_res.status == SandboxStatus.TIMEOUT:
                return f"Sandbox execution TIMED OUT after {timeout_seconds}s. Process was killed."
            else:
                err_msg = f"Sandbox execution failed with {exec_res.status.value} (exit code {exec_res.exit_code}, {exec_res.duration_ms}ms)."
                if exec_res.stderr:
                    err_msg += f"\nSTDERR:\n{exec_res.stderr[:2000]}"
                if exec_res.stdout:
                    err_msg += f"\nSTDOUT:\n{exec_res.stdout[:1000]}"
                return err_msg
        except Exception as e:
            return f"Sandbox Execution Error: {str(e)}"

    # Generic fallback
    return f"Tool '{tool_name}' executed successfully with parameters: {json.dumps(parameters)}"
