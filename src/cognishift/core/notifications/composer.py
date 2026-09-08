"""Executive notification composer with local model intelligence and deterministic template fallback.

Adheres strictly to the 3-Tier Security Notification Model:
- Bounded 2.5-second budget for local SLM summary.
- Automatic fallback to deterministic high-fidelity templates if model is busy, slow, or offline.
- Guaranteed delivery: alerts are never lost or delayed.
"""
import asyncio
import html
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import httpx

from cognishift.app.config import settings
from cognishift.core.notifications.schemas import (
    ComposedNotification,
    NotificationEvidencePack,
    NotificationType,
    Severity,
)

logger = logging.getLogger(__name__)


def _build_subject(evidence: NotificationEvidencePack) -> str:
    """Construct an authoritative, structured email subject line."""
    sev = evidence.severity.value.upper()
    etype = evidence.event_type.value

    if evidence.event_type == NotificationType.UNTRUSTED_DEVICE:
        user = evidence.target_user or "unknown"
        ip = evidence.client_ip or "unknown IP"
        return f"[COGNISHIFT - {sev}] Untrusted Device Intercepted: {user} ({ip})"

    elif evidence.event_type == NotificationType.NETWORK_DRIFT:
        user = evidence.target_user or "device"
        return f"[COGNISHIFT - {sev}] Device Network Drift: {user} (Subnet Shift)"

    elif evidence.event_type == NotificationType.FOREIGN_NETWORK_OBSERVED:
        user = evidence.target_user or "device"
        return f"[COGNISHIFT - {sev}] Foreign Network Observed: {user} ({evidence.client_ip})"

    elif evidence.event_type == NotificationType.DEVICE_BLOCKED:
        return f"[COGNISHIFT - {sev}] Security Boundary: Device Access Blocked ({evidence.target_user})"

    elif evidence.event_type == NotificationType.DEVICE_REVOKED:
        return f"[COGNISHIFT - {sev}] Device Credentials Revoked ({evidence.target_user})"

    elif evidence.event_type == NotificationType.SENSITIVE_ACTION_REQUESTED:
        tool = evidence.tool_name or "Critical Tool"
        return f"[GOVERNANCE - {sev}] Four-Eyes Approval Required: {tool} (Run #{evidence.run_id})"

    elif evidence.event_type == NotificationType.FIRST_SUPERVISOR_APPROVAL:
        return f"[GOVERNANCE - {sev}] First Supervisor Signed: Run #{evidence.run_id} (Second Approval Pending)"

    elif evidence.event_type == NotificationType.FOUR_EYES_COMPLETED:
        return f"[GOVERNANCE - {sev}] Four-Eyes Authorization Complete: Run #{evidence.run_id} Executed"

    elif evidence.event_type == NotificationType.ARTIFACT_COMPLETED:
        name = evidence.artifact_name or "Industrial Deliverable"
        return f"[DELIVERABLE - {sev}] Artifact Generated: {name} (Run #{evidence.run_id})"

    elif evidence.event_type == NotificationType.RUN_FAILED:
        return f"[SYSTEM - {sev}] Execution Failure in Run #{evidence.run_id}"

    elif evidence.event_type == NotificationType.TEST_ALERT:
        return f"[TEST - {sev}] Sovereign Notification Pipeline Health Check"

    return f"[COGNISHIFT - {sev}] Security Event: {etype}"


def _render_deterministic_plain_text(
    evidence: NotificationEvidencePack,
    sender: str,
    recipients: List[str],
    subject: str,
) -> str:
    """Render RFC 2822 plain text body using deterministic templates."""
    lines = [
        "================================================================================",
        "             COGNISHIFT SOVEREIGN INDUSTRIAL SECURITY NOTIFICATION",
        "================================================================================",
        f"Subject:    {subject}",
        f"Severity:   [{evidence.severity.value.upper()}]",
        f"Event Type: {evidence.event_type.value}",
        f"Timestamp:  {evidence.timestamp_iso}",
        f"Sender:     {sender}",
        f"Recipients: {', '.join(recipients)}",
        "--------------------------------------------------------------------------------",
        "TELEMETRY & IDENTITY METRICS:",
    ]

    if evidence.target_user:
        lines.append(f"  * User Identity:        {evidence.target_user}")
    if evidence.device_id:
        lines.append(f"  * Device ID:            {evidence.device_id}")
    if evidence.device_fingerprint:
        lines.append(f"  * Key Fingerprint:      SHA256:{evidence.device_fingerprint[:24]}...")
    if evidence.client_ip:
        lines.append(f"  * Current Network IP:   {evidence.client_ip}")
    if evidence.previous_ip:
        lines.append(f"  * Previous Network IP:  {evidence.previous_ip}")
    if evidence.workspace_id:
        lines.append(f"  * Workspace Scope:      Workspace #{evidence.workspace_id}")
    if evidence.run_id:
        lines.append(f"  * Associated Run ID:    Run #{evidence.run_id}")
    if evidence.approval_id:
        lines.append(f"  * Approval Request ID:  Approval #{evidence.approval_id}")
    if evidence.tool_name:
        lines.append(f"  * Industrial Tool:      {evidence.tool_name}")
    if evidence.parameters:
        lines.append(f"  * Parameters:           {evidence.parameters}")
    if evidence.supervisor_1:
        lines.append(f"  * Primary Supervisor:   {evidence.supervisor_1}")
    if evidence.supervisor_2:
        lines.append(f"  * Secondary Supervisor: {evidence.supervisor_2}")
    if evidence.artifact_name:
        lines.append(f"  * Generated Artifact:   {evidence.artifact_name} ({evidence.artifact_path or ''})")

    lines.extend([
        "--------------------------------------------------------------------------------",
        "EXECUTIVE SUMMARY & OPERATIONAL CONTEXT:",
    ])

    if evidence.summary:
        lines.append(f"  {evidence.summary}")
    else:
        # Standard contextual narrative
        if evidence.event_type == NotificationType.UNTRUSTED_DEVICE:
            lines.append(
                f"  An incoming connection from user '{evidence.target_user}' at address {evidence.client_ip} "
                f"presented an unregistered WebCrypto ECDSA key. In accordance with zero-trust sovereign policy, "
                f"access was intercepted with 403 UNKNOWN_DEVICE. Administrator approval is required before "
                f"this hardware identity can interact with the industrial workbench."
            )
        elif evidence.event_type == NotificationType.NETWORK_DRIFT:
            lines.append(
                f"  A known trusted device for '{evidence.target_user}' transitioned from address "
                f"{evidence.previous_ip} to {evidence.client_ip} within the operational network. Cryptographic key "
                f"continuity was validated. Telemetry records have been updated."
            )
        elif evidence.event_type == NotificationType.FOREIGN_NETWORK_OBSERVED:
            lines.append(
                f"  A known trusted device for '{evidence.target_user}' connected from an unexpected foreign address "
                f"{evidence.client_ip} (previously {evidence.previous_ip}). Elevated telemetry logging active."
            )
        elif evidence.event_type == NotificationType.SENSITIVE_ACTION_REQUESTED:
            lines.append(
                f"  Autonomous agent run #{evidence.run_id} attempted sensitive operation '{evidence.tool_name}'. "
                f"The Four-Eyes Principle has halted execution pending independent dual-supervisor sign-offs."
            )
        elif evidence.event_type == NotificationType.FOUR_EYES_COMPLETED:
            lines.append(
                f"  Dual-supervisor Four-Eyes authorization completed for Run #{evidence.run_id}. Authorized by "
                f"'{evidence.supervisor_1}' and '{evidence.supervisor_2}'. Tool execution proceeded safely."
            )
        elif evidence.event_type == NotificationType.ARTIFACT_COMPLETED:
            lines.append(
                f"  Execution Run #{evidence.run_id} successfully compiled artifact '{evidence.artifact_name}'. "
                f"Sovereign cryptographic hash and deliverable packaging verified."
            )
        else:
            lines.append(f"  System security telemetry event: {evidence.event_type.value}")

    if evidence.citations:
        lines.extend([
            "--------------------------------------------------------------------------------",
            "VERIFIED AUDIT & GOVERNANCE CITATIONS:",
        ])
        for c in evidence.citations:
            val_str = "[VERIFIED]" if c.validated else "[PENDING]"
            page_str = f", Page {c.page_number}" if c.page_number else ""
            lines.append(f"  [{c.citation_index}] {val_str} {c.citation_type.value}: {c.display_label} (ID: {c.source_id}{page_str})")

    lines.extend([
        "================================================================================",
        "This is an automated dispatch from the CogniShift Sovereign Platform.",
        "Delivered via local loopback transport (127.0.0.1:1025). Zero Cloud Egress.",
        "================================================================================",
    ])
    return "\n".join(lines)


def _render_deterministic_html(
    evidence: NotificationEvidencePack,
    sender: str,
    recipients: List[str],
    subject: str,
    summary_text: str,
) -> str:
    """Render structured, responsive, modern dark-mode HTML email."""
    sev = evidence.severity.value.upper()
    sev_color = {
        "CRITICAL": "#ef4444",
        "HIGH": "#f97316",
        "MEDIUM": "#eab308",
        "LOW": "#3b82f6",
    }.get(sev, "#64748b")

    rows = []
    if evidence.target_user:
        rows.append(f"<tr><td style='color:#94a3b8;padding:4px 12px;'>Target User</td><td style='color:#f1f5f9;font-weight:600;padding:4px 12px;'>{html.escape(str(evidence.target_user))}</td></tr>")
    if evidence.client_ip:
        rows.append(f"<tr><td style='color:#94a3b8;padding:4px 12px;'>Client IP</td><td style='color:#38bdf8;font-family:monospace;padding:4px 12px;'>{html.escape(str(evidence.client_ip))}</td></tr>")
    if evidence.device_id:
        rows.append(f"<tr><td style='color:#94a3b8;padding:4px 12px;'>Device ID</td><td style='color:#cbd5e1;font-family:monospace;font-size:12px;padding:4px 12px;'>{html.escape(str(evidence.device_id))}</td></tr>")
    if evidence.device_fingerprint:
        rows.append(f"<tr><td style='color:#94a3b8;padding:4px 12px;'>Key Fingerprint</td><td style='color:#a855f7;font-family:monospace;font-size:11px;padding:4px 12px;'>SHA256:{html.escape(str(evidence.device_fingerprint[:24]))}...</td></tr>")
    if evidence.run_id:
        rows.append(f"<tr><td style='color:#94a3b8;padding:4px 12px;'>Run ID</td><td style='color:#f1f5f9;padding:4px 12px;'>#{evidence.run_id}</td></tr>")
    if evidence.tool_name:
        rows.append(f"<tr><td style='color:#94a3b8;padding:4px 12px;'>Industrial Tool</td><td style='color:#fbbf24;font-family:monospace;padding:4px 12px;'>{html.escape(str(evidence.tool_name))}</td></tr>")

    telemetry_table = "".join(rows)

    citation_chips = []
    for c in evidence.citations:
        val_badge = "<span style='background:#166534;color:#86efac;font-size:10px;padding:2px 6px;border-radius:4px;'>VERIFIED</span>" if c.validated else "<span style='background:#854d0e;color:#fef08a;font-size:10px;padding:2px 6px;border-radius:4px;'>PENDING</span>"
        citation_chips.append(
            f"<div style='background:#0f172a;border:1px solid #334155;border-radius:6px;padding:8px 12px;margin-bottom:6px;'>"
            f"<div style='display:flex;justify-content:space-between;font-size:12px;color:#94a3b8;'>"
            f"<span>[{c.citation_index}] {html.escape(c.citation_type.value)}: <strong style='color:#f8fafc;'>{html.escape(c.display_label)}</strong></span>"
            f"{val_badge}"
            f"</div>"
            f"<div style='font-family:monospace;font-size:11px;color:#64748b;margin-top:2px;'>Source ID: {html.escape(str(c.source_id))}</div>"
            f"</div>"
        )
    citations_html = "".join(citation_chips) if citation_chips else "<div style='color:#64748b;font-size:12px;'>No external citations attached.</div>"

    return f"""<!DOCTYPE html>
<html>
<body style="background-color:#020617;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#f8fafc;margin:0;padding:24px;">
  <div style="max-width:680px;margin:0 auto;background:#0f172a;border:1px solid #1e293b;border-radius:12px;overflow:hidden;box-shadow:0 10px 25px rgba(0,0,0,0.5);">
    <div style="background:#1e293b;padding:16px 24px;border-bottom:2px solid {sev_color};display:flex;align-items:center;justify-content:space-between;">
      <div>
        <span style="font-size:11px;letter-spacing:1px;color:#94a3b8;text-transform:uppercase;font-weight:700;">CogniShift Sovereign SOC</span>
        <h2 style="margin:4px 0 0 0;font-size:18px;color:#f8fafc;">{html.escape(subject)}</h2>
      </div>
      <div style="background:{sev_color};color:#ffffff;font-size:12px;font-weight:700;padding:4px 10px;border-radius:6px;text-transform:uppercase;">
        {sev}
      </div>
    </div>
    <div style="padding:24px;">
      <div style="background:#1e293b;border-left:4px solid {sev_color};padding:14px;border-radius:4px;margin-bottom:20px;font-size:14px;line-height:1.6;color:#e2e8f0;">
        {html.escape(summary_text)}
      </div>
      
      <h4 style="color:#94a3b8;text-transform:uppercase;font-size:11px;letter-spacing:1px;margin:0 0 8px 0;">Telemetry & Audit Context</h4>
      <table style="width:100%;border-collapse:collapse;background:#090d16;border-radius:8px;font-size:13px;margin-bottom:24px;">
        {telemetry_table}
      </table>

      <h4 style="color:#94a3b8;text-transform:uppercase;font-size:11px;letter-spacing:1px;margin:0 0 8px 0;">Verified Authoritative Citations</h4>
      {citations_html}
    </div>
    <div style="background:#090d16;padding:14px 24px;border-top:1px solid #1e293b;font-size:11px;color:#64748b;display:flex;justify-content:space-between;">
      <span>Dispatched via 127.0.0.1:1025 (Loopback Only)</span>
      <span>Zero Cloud Egress Guaranteed</span>
    </div>
  </div>
</body>
</html>"""


async def _call_local_slm_for_summary(
    evidence: NotificationEvidencePack,
    timeout_seconds: float = 2.5,
) -> Optional[str]:
    """Invoke local Ollama model to synthesize a crisp executive paragraph."""
    prompt = (
        "You are the Sovereign Security & Governance AI in CogniShift, an air-gapped industrial system.\n"
        "Draft a single, highly professional executive paragraph summarizing the following operational event.\n"
        "Rules: Rely ONLY on the provided facts. Do not invent details. Keep it under 60 words.\n"
        f"Event Type: {evidence.event_type.value}\n"
        f"Severity: {evidence.severity.value}\n"
        f"Target User: {evidence.target_user}\n"
        f"Client IP: {evidence.client_ip}\n"
        f"Device: {evidence.device_id}\n"
        f"Tool/Action: {evidence.tool_name}\n"
        f"Context Details: {evidence.summary}\n"
    )

    try:
        url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
        payload = {
            "model": settings.model_name or "qwen2.5:7b",
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 90},
        }
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                text = resp.json().get("response", "").strip()
                if text and len(text) > 15:
                    return text
    except Exception as exc:
        logger.debug(f"Local SLM composition skipped/timed out: {exc}")
    return None


async def compose_notification(
    evidence: NotificationEvidencePack,
    sender: str,
    recipients: List[str],
) -> ComposedNotification:
    """Compose the final email notification using local model or deterministic fallback."""
    subject = _build_subject(evidence)
    
    # Attempt local SLM composition within strict 2.5s budget
    slm_summary = await _call_local_slm_for_summary(evidence, timeout_seconds=2.5)

    if slm_summary:
        composition_mode = "LOCAL_MODEL"
        summary_to_use = slm_summary
    else:
        composition_mode = "DETERMINISTIC_TEMPLATE_FALLBACK"
        summary_to_use = evidence.summary or ""

    # Generate complete plain text and HTML
    body_text = _render_deterministic_plain_text(evidence, sender, recipients, subject)
    if slm_summary:
        # Prepend executive SLM summary into the plain text narrative
        body_text = body_text.replace(
            "EXECUTIVE SUMMARY & OPERATIONAL CONTEXT:\n",
            f"EXECUTIVE SUMMARY & OPERATIONAL CONTEXT:\n  [Executive Briefing]: {slm_summary}\n\n",
        )

    body_html = _render_deterministic_html(
        evidence=evidence,
        sender=sender,
        recipients=recipients,
        subject=subject,
        summary_text=summary_to_use or "Sovereign telemetry captured.",
    )

    return ComposedNotification(
        event_type=evidence.event_type,
        severity=evidence.severity,
        subject=subject,
        sender=sender,
        recipients=recipients,
        body_text=body_text,
        body_html=body_html,
        composition_mode=composition_mode,
        citations=evidence.citations,
        evidence_pack=evidence,
    )
