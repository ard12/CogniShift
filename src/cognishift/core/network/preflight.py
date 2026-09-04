"""
Deterministic Network & Local Asset Readiness Preflight.
Verifies all required models, images, and services exist locally without triggering any downloads.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import os
import subprocess

from cognishift.app.config import settings
from cognishift.core.network.client import get_sovereign_async_client
from cognishift.core.network.schemas import (
    ModelAssetUnavailableError,
    LocalServiceUnavailable,
)

logger = logging.getLogger(__name__)


@dataclass
class PreflightComponentStatus:
    name: str
    status: str  # "READY", "MISSING", "UNAVAILABLE", "ACTIVE", "INACTIVE"
    details: str
    is_ready: bool


@dataclass
class PreflightReport:
    mode: str
    all_ready: bool
    components: Dict[str, PreflightComponentStatus] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


async def check_ollama_readiness() -> PreflightComponentStatus:
    """Checks Ollama daemon connectivity and configured model presence via guarded loopback."""
    base_url = settings.ollama_base_url.rstrip("/")
    required_models = {settings.text_model, settings.vision_model}
    
    try:
        async with get_sovereign_async_client(timeout=5.0, component="preflight") as client:
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code != 200:
                return PreflightComponentStatus(
                    name="Ollama Daemon",
                    status="UNAVAILABLE",
                    details=f"Ollama returned HTTP {resp.status_code}",
                    is_ready=False
                )
            data = resp.json()
            available = [m.get("name", "") for m in data.get("models", [])]
            
            missing = [req for req in required_models if not any(req in avail for avail in available)]
            if missing:
                return PreflightComponentStatus(
                    name="Ollama Models",
                    status="MISSING",
                    details=f"Required model(s) missing from local Ollama: {missing}. Manual 'ollama pull' required.",
                    is_ready=False
                )
            
            return PreflightComponentStatus(
                name="Ollama Models",
                status="READY",
                details=f"Ollama online with required models: {list(required_models)}",
                is_ready=True
            )
    except Exception as e:
        return PreflightComponentStatus(
            name="Ollama Daemon",
            status="UNAVAILABLE",
            details=f"Could not reach local Ollama on {base_url}: {e}",
            is_ready=False
        )


def check_fastembed_readiness() -> PreflightComponentStatus:
    """Verifies that FastEmbed BGE-small ONNX model exists in application cache without downloading."""
    cache_dir = settings.fastembed_cache_dir
    model_dir_name = "models--qdrant--bge-small-en-v1.5-onnx-q"
    
    # Check application cache first, then temp cache
    target_path = cache_dir / model_dir_name
    if not target_path.exists():
        import tempfile
        alt_path = Path(tempfile.gettempdir()) / "fastembed_cache" / model_dir_name
        if alt_path.exists():
            target_path = alt_path

    if target_path.exists():
        return PreflightComponentStatus(
            name="FastEmbed Model",
            status="READY",
            details=f"Model cached locally at {target_path}",
            is_ready=True
        )
    return PreflightComponentStatus(
        name="FastEmbed Model",
        status="MISSING",
        details=f"FastEmbed model missing from {cache_dir}. Auto-download disabled in strict mode.",
        is_ready=False
    )


def check_rapidocr_readiness() -> PreflightComponentStatus:
    """Verifies RapidOCR engine readiness without downloading."""
    try:
        from cognishift.core.document_processing.ocr_provider import RapidOCREngine
        engine = RapidOCREngine()
        if engine._engine is not None:
            return PreflightComponentStatus(
                name="RapidOCR Engine",
                status="READY",
                details="Local RapidOCR ONNX models initialized successfully",
                is_ready=True
            )
        return PreflightComponentStatus(
            name="RapidOCR Engine",
            status="MISSING",
            details=f"RapidOCR initialization failed: {engine._init_error}",
            is_ready=False
        )
    except Exception as e:
        return PreflightComponentStatus(
            name="RapidOCR Engine",
            status="UNAVAILABLE",
            details=f"RapidOCR error: {e}",
            is_ready=False
        )


def check_docker_sandbox_readiness() -> PreflightComponentStatus:
    """Verifies that the Docker sandbox image is present locally without pulling."""
    image_name = settings.sandbox_image
    try:
        # Check via docker command with timeout
        result = subprocess.run(
            ["docker", "image", "inspect", image_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return PreflightComponentStatus(
                name="Docker Sandbox Image",
                status="READY",
                details=f"Sandbox image '{image_name}' present locally",
                is_ready=True
            )
        return PreflightComponentStatus(
            name="Docker Sandbox Image",
            status="MISSING",
            details=f"Sandbox image '{image_name}' not found locally. Auto-pull disabled (--pull=never).",
            is_ready=False
        )
    except Exception as e:
        return PreflightComponentStatus(
            name="Docker Sandbox Image",
            status="UNAVAILABLE",
            details=f"Docker inspect failed: {e}",
            is_ready=False
        )


def check_frontend_external_assets() -> PreflightComponentStatus:
    """Scans static index.html to guarantee 0 external CDN references."""
    static_file = settings.static_dir / "index.html"
    if not static_file.exists():
        return PreflightComponentStatus(
            name="Frontend Static Assets",
            status="MISSING",
            details=f"{static_file} does not exist",
            is_ready=False
        )
    
    text = static_file.read_text(encoding="utf-8")
    import re
    external_refs = [
        line.strip() for line in text.splitlines()
        if re.search(r'https?://', line) and not line.strip().startswith("//") and not line.strip().startswith("<!--")
    ]
    
    if len(external_refs) == 0:
        return PreflightComponentStatus(
            name="Frontend Static Assets",
            status="READY",
            details="Zero external CDN or font references in frontend",
            is_ready=True
        )
    return PreflightComponentStatus(
        name="Frontend Static Assets",
        status="NON_SOVEREIGN",
        details=f"Found {len(external_refs)} external CDN references: {external_refs[:2]}",
        is_ready=False
    )


def check_firewall_status() -> PreflightComponentStatus:
    """Checks whether the operator has enabled the Windows Defender Firewall strict policy."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-NetFirewallRule -Group 'CogniShift-Phase6' -ErrorAction SilentlyContinue | Measure-Object | Select-Object -ExpandProperty Count"],
            capture_output=True,
            text=True,
            timeout=5
        )
        count = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
        if count > 0:
            return PreflightComponentStatus(
                name="OS Firewall Rules",
                status="ACTIVE",
                details=f"{count} CogniShift-Phase6 firewall rule(s) active",
                is_ready=True
            )
        return PreflightComponentStatus(
            name="OS Firewall Rules",
            status="INACTIVE",
            details="CogniShift-Phase6 firewall rules not detected. Run enable_strict_network_policy.ps1.",
            is_ready=False
        )
    except Exception as e:
        return PreflightComponentStatus(
            name="OS Firewall Rules",
            status="UNKNOWN",
            details=f"Could not query firewall rules: {e}",
            is_ready=False
        )


async def run_network_preflight() -> PreflightReport:
    """Executes the complete deterministic preflight check without downloading any resources."""
    mode = getattr(settings, "network_policy_mode", "strict")
    report = PreflightReport(mode=mode, all_ready=True)

    ollama_status = await check_ollama_readiness()
    report.components["ollama"] = ollama_status

    fastembed_status = check_fastembed_readiness()
    report.components["fastembed"] = fastembed_status

    ocr_status = check_rapidocr_readiness()
    report.components["rapidocr"] = ocr_status

    docker_status = check_docker_sandbox_readiness()
    report.components["docker_sandbox"] = docker_status

    frontend_status = check_frontend_external_assets()
    report.components["frontend"] = frontend_status

    firewall_status = check_firewall_status()
    report.components["firewall"] = firewall_status

    # In strict mode, essential runtime components must be ready
    essential = [ollama_status, fastembed_status, ocr_status, docker_status, frontend_status]
    report.all_ready = all(c.is_ready for c in essential)
    
    return report
