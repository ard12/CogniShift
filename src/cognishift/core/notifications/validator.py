"""Fail-closed citation validator for sovereign security notifications.

Validates that every cited audit record, device identity, run ID, approval request,
knowledge source document, and artifact exists in the authoritative SQLite database.
Unverified citations are marked invalid or stripped to prevent LLM hallucinations.
"""
import logging
from typing import List, Tuple
from cognishift.app.db.database import get_db
from cognishift.core.notifications.schemas import CitationClass, NotificationCitation

logger = logging.getLogger(__name__)


async def validate_citation(citation: NotificationCitation) -> bool:
    """Check whether a single citation is backed by authoritative records."""
    try:
        async with get_db() as db:
            src = str(citation.source_id).strip()

            if citation.citation_type == CitationClass.AUDIT:
                try:
                    audit_id = int(src)
                    row = await (await db.execute("SELECT id FROM audit_events WHERE id = ?", (audit_id,))).fetchone()
                    return row is not None
                except ValueError:
                    return False

            elif citation.citation_type == CitationClass.DEVICE:
                row = await (await db.execute(
                    "SELECT id FROM trusted_devices WHERE device_id = ? OR key_fingerprint = ?",
                    (src, src),
                )).fetchone()
                return row is not None

            elif citation.citation_type == CitationClass.RUN:
                try:
                    run_id = int(src)
                    row = await (await db.execute("SELECT id FROM agent_runs WHERE id = ?", (run_id,))).fetchone()
                    return row is not None
                except ValueError:
                    return False

            elif citation.citation_type == CitationClass.APPROVAL:
                try:
                    app_id = int(src)
                    row = await (await db.execute("SELECT id FROM approval_requests WHERE id = ?", (app_id,))).fetchone()
                    return row is not None
                except ValueError:
                    return False

            elif citation.citation_type == CitationClass.ARTIFACT:
                try:
                    art_id = int(src)
                    row = await (await db.execute("SELECT id FROM workspace_artifacts WHERE id = ?", (art_id,))).fetchone()
                    if row:
                        return True
                except ValueError:
                    pass
                # Check by filename or relative path
                row = await (await db.execute(
                    "SELECT id FROM workspace_artifacts WHERE filename = ? OR relative_path = ?",
                    (src, src),
                )).fetchone()
                return row is not None

            elif citation.citation_type == CitationClass.DOCUMENT:
                try:
                    doc_id = int(src)
                    row = await (await db.execute("SELECT id FROM knowledge_sources WHERE id = ?", (doc_id,))).fetchone()
                    if row:
                        return True
                except ValueError:
                    pass
                row = await (await db.execute(
                    "SELECT id FROM knowledge_sources WHERE name = ? OR original_filename = ?",
                    (src, src),
                )).fetchone()
                return row is not None

            elif citation.citation_type == CitationClass.AUTHENTICATION:
                # Session hash or user ID
                row = await (await db.execute(
                    "SELECT session_hash FROM active_device_sessions WHERE session_hash = ? OR user_id = ?",
                    (src, src),
                )).fetchone()
                return row is not None

            return True
    except Exception as exc:
        logger.warning(f"Error validating citation {citation}: {exc}")
        return False


async def validate_citations(
    citations: List[NotificationCitation],
    strip_invalid: bool = False,
) -> Tuple[List[NotificationCitation], bool]:
    """Validate a list of citations.

    Returns:
        (validated_citations, all_valid)
    """
    validated_list: List[NotificationCitation] = []
    all_valid = True

    for cit in citations:
        is_valid = await validate_citation(cit)
        cit.validated = is_valid
        if is_valid:
            validated_list.append(cit)
        else:
            all_valid = False
            if not strip_invalid:
                validated_list.append(cit)

    return validated_list, all_valid
