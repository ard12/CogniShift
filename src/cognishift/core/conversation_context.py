"""
CogniShift Conversation Context Resolver.
Provides bounded structured reference and anaphora resolution across multi-turn dialogue.
Current turn remains authoritative; history never injects stale operational intent.
"""
from dataclasses import dataclass, field
import logging
import re
from typing import List, Dict, Any, Optional

import sqlite3
import aiosqlite
from cognishift.app.config import settings
from cognishift.app.db.database import get_db
from cognishift.core.pending_tasks import detect_affirmation_or_cancellation

logger = logging.getLogger(__name__)

# Regular expressions for file references and equipment tags
FILE_REGEX = re.compile(
    r'\b([a-zA-Z0-9_\-\.]+\.(?:csv|tsv|xlsx|xls|docx|pdf|pptx|json|yaml|yml|txt|md|xml|py|log))\b',
    re.IGNORECASE
)
EQUIPMENT_REGEX = re.compile(
    r'\b([A-Z]{1,4}-\d{2,4}[A-Z]?)\b'
)

LATEST_DOC_REGEX = re.compile(
    r'\b(?:latest\s+(?:ingested\s+)?(?:document|file|pdf|manual)|newest\s+(?:ingested\s+)?(?:document|file|pdf|manual))\b',
    re.IGNORECASE
)

# Pronouns and anaphoric trigger phrases
ANAPHORA_TRIGGERS = [
    r'\bthat\b',
    r'\bit\b',
    r'\bits\b',
    r'\bthis\b',
    r'\bthe file\b',
    r'\bthis file\b',
    r'\bthat file\b',
    r'\bthe spreadsheet\b',
    r'\bthis spreadsheet\b',
    r'\bthe document\b',
    r'\bthis document\b',
    r'\bthat document\b',
    r'\bthe report\b',
    r'\bthis report\b',
    r'\bthat report\b',
    r'\bwhich page\b',
    r'\bthat source\b',
    r'\bthe previous\b',
    r'\babout that\b',
    r'\bon that\b',
    r'\bthat pdf\b',
    r'\bthis pdf\b',
    r'\bthe pdf\b',
    r'\bthat manual\b',
    r'\bthis manual\b',
    r'\bthe manual\b'
]
ANAPHORA_PATTERN = re.compile('|'.join(ANAPHORA_TRIGGERS), re.IGNORECASE)


async def get_latest_ingested_document_async(
    workspace_id: int, 
    db: Optional[aiosqlite.Connection] = None
) -> Optional[Dict[str, Any]]:
    """Authoritatively query latest successfully ingested knowledge source asynchronously without event-loop blocking.
    
    CRITICAL DISTINCTION:
    Distinguishes completed knowledge_sources from generated artifacts or temporary uploads.
    """
    db_path = settings.database_path
    if not db_path.exists():
        return None
    query = """SELECT id, workspace_id, name, original_filename, local_path, 
                      checksum, chunk_count, created_at, active_processing_version
               FROM knowledge_sources 
               WHERE workspace_id = ? AND processing_status = 'completed'
               ORDER BY created_at DESC, id DESC LIMIT 1"""
    try:
        if db is not None:
            cursor = await db.execute(query, (workspace_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
        else:
            async with get_db() as conn:
                cursor = await conn.execute(query, (workspace_id,))
                row = await cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        logger.warning(f"Error querying latest ingested document async: {e}")
        return None


def get_latest_ingested_document(workspace_id: int) -> Optional[Dict[str, Any]]:
    """Authoritatively query latest successfully ingested knowledge source from database.
    
    Uses read-only URI mode and timeout to prevent table lock contention.
    """
    db_path = settings.database_path
    if not db_path.exists():
        return None
    try:
        uri_path = f"file:{db_path.resolve().as_posix()}?mode=ro"
        conn = sqlite3.connect(uri_path, uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, workspace_id, name, original_filename, local_path, 
                      checksum, chunk_count, created_at, active_processing_version
               FROM knowledge_sources 
               WHERE workspace_id = ? AND processing_status = 'completed'
               ORDER BY created_at DESC, id DESC LIMIT 1""",
            (workspace_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return dict(row)
    except Exception as e:
        logger.warning(f"Error querying latest ingested document: {e}")
        return None


@dataclass
class ResolvedContext:
    """Structured context resolved from conversation history."""
    files: List[str] = field(default_factory=list)
    equipment_ids: List[str] = field(default_factory=list)
    topic: Optional[str] = None
    source_turn: Optional[int] = None
    has_anaphora: bool = False
    prior_citations: List[str] = field(default_factory=list)
    pinned_source: Optional[Dict[str, Any]] = None
    is_affirmation: bool = False
    is_cancellation: bool = False
    pending_task_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files": self.files,
            "equipment_ids": self.equipment_ids,
            "topic": self.topic,
            "source_turn": self.source_turn,
            "has_anaphora": self.has_anaphora,
            "prior_citations": self.prior_citations,
            "pinned_source": self.pinned_source,
            "is_affirmation": self.is_affirmation,
            "is_cancellation": self.is_cancellation,
            "pending_task_id": self.pending_task_id
        }


class ConversationContextResolver:
    """
    Bounded Conversation Context Resolver.
    Inspects recent conversation history only when the current prompt exhibits
    clear anaphora or ellipsis ('that', 'it', 'the file', 'generate a report on that').
    """

    def __init__(self, max_history_turns: int = 8):
        self.max_history_turns = max_history_turns

    def parse_raw_history(self, raw_text: str) -> List[Dict[str, str]]:
        """Extract historical messages from text formatted with [Recent Conversation Context]."""
        if not raw_text or "[Recent Conversation Context]" not in raw_text:
            return []
        parts = raw_text.split("[Recent Conversation Context]")
        context_block = parts[1]
        if "[Current Operator Query]" in context_block:
            context_block = context_block.split("[Current Operator Query]")[0]
        
        history = []
        for line in context_block.strip().split("\n"):
            line = line.strip()
            if line.startswith("Operator:"):
                history.append({"role": "user", "content": line[len("Operator:"):].strip()})
            elif line.startswith("Assistant:"):
                history.append({"role": "assistant", "content": line[len("Assistant:"):].strip()})
            elif line:
                history.append({"role": "unknown", "content": line})
        return history

    def resolve(
        self,
        current_turn: str,
        conversation_history: Optional[List[Any]] = None,
        raw_input: Optional[str] = None,
        workspace_id: int = 1,
        latest_doc: Optional[Dict[str, Any]] = None
    ) -> ResolvedContext:
        """
        Resolves references from structured conversation history for current turn.
        If current turn is self-contained or explicitly introduces a new subject,
        returns an empty context to prevent context pollution.
        """
        text = (current_turn or "").strip()
        if not conversation_history and raw_input:
            conversation_history = self.parse_raw_history(raw_input)
        if not conversation_history and "[Recent Conversation Context]" in text:
            conversation_history = self.parse_raw_history(text)

        is_affirmation, is_cancellation = detect_affirmation_or_cancellation(text)

        # Check for presence of anaphora in current turn
        has_anaphora = bool(ANAPHORA_PATTERN.search(text)) or is_affirmation or is_cancellation
        
        # Check if current turn already explicitly names its own files
        explicit_files = FILE_REGEX.findall(text)
        explicit_equipment = EQUIPMENT_REGEX.findall(text)

        # Check for authoritative "latest ingested document" reference
        pinned_source = None
        if LATEST_DOC_REGEX.search(text):
            if latest_doc is None and workspace_id:
                latest_doc = get_latest_ingested_document(workspace_id)
            if latest_doc:
                pinned_source = latest_doc
                if latest_doc.get("name") and latest_doc["name"] not in explicit_files:
                    explicit_files.append(latest_doc["name"])

        # If current turn has its own explicit file and not an affirmation/cancellation, return immediately
        if explicit_files and not (is_affirmation or is_cancellation):
            return ResolvedContext(
                files=list(dict.fromkeys(explicit_files)),
                equipment_ids=list(dict.fromkeys(explicit_equipment)),
                has_anaphora=has_anaphora,
                pinned_source=pinned_source,
                is_affirmation=is_affirmation,
                is_cancellation=is_cancellation
            )

        if not text or not conversation_history:
            return ResolvedContext(
                files=list(dict.fromkeys(explicit_files)),
                equipment_ids=list(dict.fromkeys(explicit_equipment)),
                has_anaphora=has_anaphora,
                pinned_source=pinned_source,
                is_affirmation=is_affirmation,
                is_cancellation=is_cancellation
            )

        # If no anaphora, no affirmation, and no reference triggers, do not inherit stale context
        if not has_anaphora:
            return ResolvedContext(
                files=list(dict.fromkeys(explicit_files)),
                equipment_ids=list(dict.fromkeys(explicit_equipment)),
                has_anaphora=False,
                pinned_source=pinned_source,
                is_affirmation=False,
                is_cancellation=False
            )

        # Bounded scan backwards through history (up to max_history_turns)
        bounded_history = conversation_history[-self.max_history_turns:]
        resolved_files: List[str] = list(explicit_files)
        resolved_equipment: List[str] = list(explicit_equipment)
        prior_citations: List[str] = []
        source_turn: Optional[int] = None
        topic: Optional[str] = None

        turn_idx = len(bounded_history)
        for msg in reversed(bounded_history):
            turn_idx -= 1
            content = ""
            if isinstance(msg, dict):
                content = msg.get("content") or msg.get("text") or ""
            elif hasattr(msg, "content"):
                content = getattr(msg, "content", "")
            elif hasattr(msg, "text"):
                content = getattr(msg, "text", "")

            if not content:
                continue

            # Check for latest ingested document referenced in historical turn
            if pinned_source is None and LATEST_DOC_REGEX.search(content):
                if latest_doc is None and workspace_id:
                    latest_doc = get_latest_ingested_document(workspace_id)
                if latest_doc:
                    pinned_source = latest_doc
                    if latest_doc.get("name") and latest_doc["name"] not in resolved_files:
                        resolved_files.append(latest_doc["name"])

            # Look for referenced files in historical turn
            found_files = FILE_REGEX.findall(content)
            if found_files and not resolved_files:
                resolved_files = list(dict.fromkeys(found_files))
                source_turn = turn_idx
                topic = f"Artifact inquiry: {resolved_files[0]}"

            # Look for equipment tags if equipment was not resolved
            found_equipment = EQUIPMENT_REGEX.findall(content)
            if found_equipment and not resolved_equipment:
                resolved_equipment = list(dict.fromkeys(found_equipment))
                if source_turn is None:
                    source_turn = turn_idx
                    topic = f"Equipment inquiry: {resolved_equipment[0]}"

            # Look for page / manual citations
            found_citations = re.findall(r'\[(.*?\|\s*Page\s*\d+)\]', content)
            if found_citations and not prior_citations:
                prior_citations = list(dict.fromkeys(found_citations))

            # Stop once we have resolved the most immediate prior subject
            if resolved_files or resolved_equipment:
                break

        return ResolvedContext(
            files=resolved_files,
            equipment_ids=resolved_equipment,
            topic=topic,
            source_turn=source_turn,
            has_anaphora=has_anaphora,
            prior_citations=prior_citations,
            pinned_source=pinned_source,
            is_affirmation=is_affirmation,
            is_cancellation=is_cancellation
        )
