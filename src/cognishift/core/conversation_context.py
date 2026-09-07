"""
CogniShift Conversation Context Resolver.
Provides bounded structured reference and anaphora resolution across multi-turn dialogue.
Current turn remains authoritative; history never injects stale operational intent.
"""
from dataclasses import dataclass, field
import logging
import re
from pathlib import Path
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
    r'\bthe manual\b',
    r'\btoo\b',
    r'\balso\b',
    r'\banother\b',
    r'\bsame\s+file\b',
    r'\bsame\s+workbook\b',
    r'\bnow\s+chart\b',
    r'\bvisualize\s+it\b',
    r'\bmake\s+a\s+png\b',
    r'\bmake\s+it\s+a\b',
    r'\banother\s+chart\b',
    r'\banother\s+visualization\b',
    r'\banother\s+png\b'
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


async def resolve_target_document_for_query(
    workspace_id: int,
    query: str,
    db: Optional[aiosqlite.Connection] = None
) -> Optional[Dict[str, Any]]:
    """Intelligently resolves the target knowledge source document referenced in a user query.

    Prevents modality cross-contamination (e.g. returning a P&ID PNG image when the operator
    explicitly requested an Excel financial audit).

    Matching Pipeline:
    1. Exact filename or stem match in query text.
    2. Modality alignment (spreadsheets vs images vs PDFs).
    3. Semantic domain keyword scoring across document names.
    4. Fallback to latest ingested document if query requests 'latest' or has no modality conflict.
    """
    db_path = settings.database_path
    if not db_path.exists():
        return None

    fetch_query = """SELECT id, workspace_id, name, original_filename, local_path, 
                            source_type, checksum, chunk_count, created_at, active_processing_version
                     FROM knowledge_sources 
                     WHERE workspace_id = ? AND processing_status = 'completed'
                     ORDER BY created_at DESC, id DESC"""
    try:
        if db is not None:
            cursor = await db.execute(fetch_query, (workspace_id,))
            rows = [dict(r) for r in await cursor.fetchall()]
        else:
            async with get_db() as conn:
                cursor = await conn.execute(fetch_query, (workspace_id,))
                rows = [dict(r) for r in await cursor.fetchall()]
    except Exception as e:
        logger.warning(f"Error fetching knowledge sources for resolution: {e}")
        return None

    if not rows:
        return None

    q_lower = (query or "").lower().strip()

    # If query explicitly specifies 'latest document' or 'newest', return the most recent doc
    is_explicit_latest = bool(LATEST_DOC_REGEX.search(q_lower))

    # 0. Strict Explicit Filename Matching
    # If query mentions an explicit filename (e.g. foo.xlsx), require exact equality.
    # Never allow a non-revision file (e.g. ..._48H.xlsx) to satisfy a request for ..._48H_REV_B.xlsx via stem matching.
    explicit_files = [f.lower().strip() for f in FILE_REGEX.findall(query or "")]
    if explicit_files:
        for ef in explicit_files:
            for r in rows:
                name = (r.get("name") or "").lower().strip()
                orig_name = (r.get("original_filename") or "").lower().strip()
                if ef in (name, orig_name):
                    return r
        # Explicit filename specified in query, but not found among completed knowledge sources.
        # Fail closed: Do NOT allow fuzzy / stem matching of a different file!
        return None

    # 1. Exact filename or stem match in query
    for r in rows:
        name = (r.get("name") or "").lower()
        orig_name = (r.get("original_filename") or "").lower()
        stem = Path(name).stem.lower()
        if (name and name in q_lower) or (orig_name and orig_name in q_lower):
            return r
        if stem and len(stem) > 5 and stem in q_lower:
            return r

    wants_spreadsheet = any(w in q_lower for w in ["excel", "xlsx", "xls", "csv", "spreadsheet", "spreadsheets", "sheets", "workbook"])
    wants_image = any(w in q_lower for w in ["image", "photo", "png", "jpg", "jpeg", "schematic", "p&id", "pid", "diagram", "gauge", "meter", "dial"])
    wants_pdf = any(w in q_lower for w in ["pdf", "manual", "sop", "standard", "policy"])

    # If explicit latest with modality constraint:
    if is_explicit_latest:
        if wants_spreadsheet:
            for r in rows:
                if (r.get("source_type") or "").lower() == "spreadsheet" or (r.get("name") or "").lower().endswith((".xlsx", ".xls", ".csv")):
                    return r
        elif wants_image:
            for r in rows:
                if (r.get("source_type") or "").lower() == "image" or (r.get("name") or "").lower().endswith((".png", ".jpg", ".jpeg")):
                    return r
        elif wants_pdf:
            for r in rows:
                if (r.get("source_type") or "").lower() == "pdf" or (r.get("name") or "").lower().endswith(".pdf"):
                    return r
        return rows[0]

    # Domain keywords for semantic matching
    domain_keywords = [
        "financial", "history", "audit", "revenue", "ebitda", "pat", "cagr", "p&l", "profit",
        "pid", "schematic", "cdu", "hydrocracker", "manifold",
        "pump", "p-101", "p-101a", "sop", "maintenance", "inspection",
        "gauge", "meter", "dial", "photo",
        "handwritten", "note", "shift", "handover",
        "oisd", "prv", "relief", "pressure",
        "scada", "telemetry", "readings", "sap", "work order"
    ]

    scored_candidates = []
    for r in rows:
        name = (r.get("name") or "").lower()
        stype = (r.get("source_type") or "").lower()
        ext = Path(name).suffix.lower()
        score = 0

        # Modality alignment
        if wants_spreadsheet:
            if stype == "spreadsheet" or ext in (".xlsx", ".xls", ".csv"):
                score += 50
            elif stype == "image" or ext in (".png", ".jpg", ".jpeg"):
                score -= 60
        elif wants_image:
            if stype == "image" or ext in (".png", ".jpg", ".jpeg"):
                score += 50
            elif stype == "spreadsheet" or ext in (".xlsx", ".xls", ".csv"):
                score -= 40
        elif wants_pdf:
            if stype == "pdf" or ext == ".pdf":
                score += 30

        # Domain keyword matching
        for kw in domain_keywords:
            if kw in q_lower and kw in name:
                score += 35

        scored_candidates.append((score, r))

    scored_candidates.sort(key=lambda x: x[0], reverse=True)

    if scored_candidates and scored_candidates[0][0] > 0:
        return scored_candidates[0][1]

    return None


def extract_requested_page(text: str) -> Optional[int]:
    """Extract 1-indexed target page number from natural language queries."""
    if not text:
        return None
    t = text.lower()
    if re.search(r'\b(?:first|1st)\s*page\b|\bpage\s*1\b', t):
        return 1
    if re.search(r'\b(?:second|2nd)\s*page\b|\bpage\s*2\b', t):
        return 2
    if re.search(r'\b(?:third|3rd)\s*page\b|\bpage\s*3\b', t):
        return 3
    if re.search(r'\b(?:fourth|4th)\s*page\b|\bpage\s*4\b', t):
        return 4
    if re.search(r'\b(?:fifth|5th)\s*page\b|\bpage\s*5\b', t):
        return 5
    m = re.search(r'\bpage\s*(\d+)\b|\b(\d+)(?:st|nd|rd|th)\s*page\b', t)
    if m:
        val = m.group(1) or m.group(2)
        try:
            return int(val)
        except ValueError:
            return None
    return None


def resolve_target_document_for_query_sync(
    workspace_id: int,
    query: str
) -> Optional[Dict[str, Any]]:
    """Synchronous read-only resolver for target knowledge source document referenced in text."""
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
                      source_type, checksum, chunk_count, created_at, active_processing_version
               FROM knowledge_sources 
               WHERE workspace_id = ? AND processing_status = 'completed'
               ORDER BY created_at DESC, id DESC""",
            (workspace_id,)
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
    except Exception as e:
        logger.warning(f"Error fetching knowledge sources for sync resolution: {e}")
        return None

    if not rows:
        return None

    q_lower = (query or "").lower().strip()

    # 0. Strict Explicit Filename Matching
    # If query mentions an explicit filename (e.g. foo.xlsx), require exact equality.
    # Never allow a non-revision file (e.g. ..._48H.xlsx) to satisfy a request for ..._48H_REV_B.xlsx via stem matching.
    explicit_files = [f.lower().strip() for f in FILE_REGEX.findall(query or "")]
    if explicit_files:
        for ef in explicit_files:
            for r in rows:
                name = (r.get("name") or "").lower().strip()
                orig_name = (r.get("original_filename") or "").lower().strip()
                if ef in (name, orig_name):
                    return r
        # Explicit filename specified in query, but not found among completed knowledge sources.
        # Fail closed: Do NOT allow fuzzy / stem matching of a different file!
        return None

    # 1. Exact filename or stem match in query
    for r in rows:
        name = (r.get("name") or "").lower()
        orig_name = (r.get("original_filename") or "").lower()
        stem = Path(name).stem.lower()
        if (name and name in q_lower) or (orig_name and orig_name in q_lower):
            return r
        if stem and len(stem) > 5 and stem in q_lower:
            return r

    wants_spreadsheet = any(w in q_lower for w in ["excel", "xlsx", "xls", "csv", "spreadsheet", "spreadsheets", "sheets", "workbook"])
    wants_image = any(w in q_lower for w in ["image", "photo", "png", "jpg", "jpeg", "schematic", "p&id", "pid", "diagram", "gauge", "meter", "dial"])
    wants_pdf = any(w in q_lower for w in ["pdf", "manual", "sop", "standard", "policy"])

    domain_keywords = [
        "financial", "history", "audit", "revenue", "ebitda", "pat", "cagr", "p&l", "profit",
        "pid", "schematic", "cdu", "hydrocracker", "manifold",
        "pump", "p-101", "p-101a", "sop", "maintenance", "inspection", "report",
        "gauge", "meter", "dial", "photo",
        "handwritten", "note", "shift", "handover",
        "oisd", "prv", "relief", "pressure",
        "scada", "telemetry", "readings", "sap", "work order"
    ]

    scored_candidates = []
    for r in rows:
        name = (r.get("name") or "").lower()
        stype = (r.get("source_type") or "").lower()
        ext = Path(name).suffix.lower()
        score = 0

        # Modality alignment
        if wants_spreadsheet:
            if stype == "spreadsheet" or ext in (".xlsx", ".xls", ".csv"):
                score += 50
            elif stype == "image" or ext in (".png", ".jpg", ".jpeg"):
                score -= 60
        elif wants_image:
            if stype == "image" or ext in (".png", ".jpg", ".jpeg"):
                score += 50
            elif stype == "spreadsheet" or ext in (".xlsx", ".xls", ".csv"):
                score -= 40
        elif wants_pdf:
            if stype == "pdf" or ext == ".pdf":
                score += 30

        # Domain keyword matching
        for kw in domain_keywords:
            if kw in q_lower and kw in name:
                score += 35

        scored_candidates.append((score, r))

    scored_candidates.sort(key=lambda x: x[0], reverse=True)

    if scored_candidates and scored_candidates[0][0] > 0:
        return scored_candidates[0][1]

    return None


@dataclass
class ResolvedSource:
    """Authoritative canonical source reference object."""
    origin_type: str  # 'knowledge_source' | 'workspace_artifact' | 'file'
    workspace_id: int
    source_id: Optional[int]
    artifact_id: Optional[int]
    filename: str
    original_filename: str
    workspace_relative_path: str
    sha256: str
    processing_status: str
    processing_version: Optional[str] = None
    selected_by: str = "exact_filename"  # 'exact_filename' | 'pinned' | 'anaphora' | 'latest' | 'explicit_prompt'
    strict_source_scope: bool = False
    sheet_name: Optional[str] = None
    table_range: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "origin_type": self.origin_type,
            "workspace_id": self.workspace_id,
            "source_id": self.source_id,
            "artifact_id": self.artifact_id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "workspace_relative_path": self.workspace_relative_path,
            "sha256": self.sha256,
            "processing_status": self.processing_status,
            "processing_version": self.processing_version,
            "selected_by": self.selected_by,
            "strict_source_scope": self.strict_source_scope,
            "sheet_name": self.sheet_name,
            "table_range": self.table_range
        }


async def resolve_authoritative_source(
    workspace_id: int,
    query: str,
    target_filename: Optional[str] = None,
    db: Optional[aiosqlite.Connection] = None
) -> Optional[ResolvedSource]:
    """
    Authoritative single-source resolver.
    Disambiguates between Knowledge Vault sources and generated Workspace Artifacts.
    Enforces strict source scope when queries specify 'Using only X...'.
    """
    from cognishift.core.security import get_workspace_root
    import hashlib

    q_lower = (query or "").lower()
    is_strict = any(w in q_lower for w in ["using only", "strictly from", "only use", "do not use other", "using that workbook only", "using that file only"])

    # Determine target filename candidate
    fn_cand = target_filename
    if not fn_cand:
        file_matches = FILE_REGEX.findall(query or "")
        if file_matches:
            fn_cand = file_matches[0]

    ws_root = get_workspace_root(workspace_id).resolve()

    # 1. Search knowledge_sources first (Knowledge Vault ALWAYS has authority for uploaded data)
    ks_query = """SELECT id, name, original_filename, local_path, source_type, checksum, 
                         processing_status, active_processing_version 
                  FROM knowledge_sources 
                  WHERE workspace_id = ? AND processing_status = 'completed'
                  ORDER BY id DESC"""
    
    source_rows = []
    if db is not None:
        cursor = await db.execute(ks_query, (workspace_id,))
        source_rows = [dict(r) for r in await cursor.fetchall()]
    else:
        async with get_db() as conn:
            cursor = await conn.execute(ks_query, (workspace_id,))
            source_rows = [dict(r) for r in await cursor.fetchall()]

    for src in source_rows:
        s_name = (src.get("name") or "").lower()
        s_orig = (src.get("original_filename") or "").lower()
        matched = False
        selected_by = "exact_filename"

        if fn_cand:
            if fn_cand.lower() == s_name or fn_cand.lower() == s_orig:
                matched = True
                selected_by = "exact_filename"
            elif Path(fn_cand).suffix and Path(fn_cand).suffix.lower() in [".xlsx", ".xls", ".csv", ".pdf", ".docx", ".png", ".jpg"]:
                cand_stem = Path(fn_cand).stem.lower()
                s_stem = Path(s_name).stem.lower()
                if cand_stem == s_stem and ("_rev" not in cand_stem and "_rev" not in s_stem):
                    matched = True
                    selected_by = "stem_match"
            elif Path(fn_cand).stem.lower() == Path(s_name).stem or Path(fn_cand).stem.lower() == Path(s_orig).stem:
                matched = True
                selected_by = "stem_match"
        elif (s_name in q_lower or s_orig in q_lower):
            # Do not allow general query mention if query explicitly names another specific file
            all_q_files = [ef.lower() for ef in FILE_REGEX.findall(q_lower)]
            if not all_q_files or s_name in all_q_files or s_orig in all_q_files:
                matched = True
                selected_by = "query_mention"

        if matched:
            raw_lp = src.get("local_path", "")
            rel_p = raw_lp
            full_p = None
            if raw_lp:
                try:
                    p = Path(raw_lp)
                    if p.is_absolute():
                        full_p = p
                        rel_p = str(p.resolve().relative_to(ws_root)).replace("\\", "/")
                    else:
                        full_p = ws_root / p
                        rel_p = str(p).replace("\\", "/")
                except Exception:
                    rel_p = Path(raw_lp).name
                    full_p = ws_root / "uploads" / Path(raw_lp).name

            # Checksum
            csum = src.get("checksum") or ""
            if not csum and full_p and full_p.exists():
                try:
                    csum = hashlib.sha256(full_p.read_bytes()).hexdigest()
                except Exception:
                    csum = ""

            return ResolvedSource(
                origin_type="knowledge_source",
                workspace_id=workspace_id,
                source_id=src["id"],
                artifact_id=None,
                filename=src["original_filename"] or src["name"],
                original_filename=src["original_filename"] or src["name"],
                workspace_relative_path=rel_p,
                sha256=csum,
                processing_status=src["processing_status"],
                processing_version=src.get("active_processing_version"),
                selected_by=selected_by,
                strict_source_scope=is_strict
            )

    # 2. Search workspace_artifacts if asking about generated files or when not in knowledge_sources
    art_query = """SELECT id, filename, relative_path, file_size, artifact_type, sha256_hash 
                   FROM workspace_artifacts 
                   WHERE workspace_id = ? 
                   ORDER BY id DESC"""
    art_rows = []
    if db is not None:
        cursor = await db.execute(art_query, (workspace_id,))
        art_rows = [dict(r) for r in await cursor.fetchall()]
    else:
        async with get_db() as conn:
            cursor = await conn.execute(art_query, (workspace_id,))
            art_rows = [dict(r) for r in await cursor.fetchall()]

    for art in art_rows:
        a_name = art.get("filename", "").lower()
        matched = False
        selected_by = "exact_filename"

        if fn_cand and (fn_cand.lower() == a_name or Path(fn_cand).stem.lower() == Path(a_name).stem):
            matched = True
        elif not fn_cand and (a_name in q_lower):
            matched = True
            selected_by = "query_mention"

        if matched:
            rel_p = art["relative_path"]
            full_p = ws_root / rel_p
            csum = art.get("sha256_hash") or ""
            if not csum and full_p.exists():
                try:
                    csum = hashlib.sha256(full_p.read_bytes()).hexdigest()
                except Exception:
                    csum = ""

            return ResolvedSource(
                origin_type="workspace_artifact",
                workspace_id=workspace_id,
                source_id=None,
                artifact_id=art["id"],
                filename=art["filename"],
                original_filename=art["filename"],
                workspace_relative_path=rel_p,
                sha256=csum,
                processing_status="completed",
                processing_version="1.0",
                selected_by=selected_by,
                strict_source_scope=is_strict
            )

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
    resolved_source: Optional[ResolvedSource] = None
    is_affirmation: bool = False
    is_cancellation: bool = False
    pending_task_id: Optional[str] = None
    requested_page: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files": self.files,
            "equipment_ids": self.equipment_ids,
            "topic": self.topic,
            "source_turn": self.source_turn,
            "has_anaphora": self.has_anaphora,
            "prior_citations": self.prior_citations,
            "pinned_source": self.pinned_source,
            "resolved_source": self.resolved_source.to_dict() if self.resolved_source else None,
            "is_affirmation": self.is_affirmation,
            "is_cancellation": self.is_cancellation,
            "pending_task_id": self.pending_task_id,
            "requested_page": self.requested_page
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
        requested_page = extract_requested_page(text)

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
                is_cancellation=is_cancellation,
                requested_page=requested_page
            )

        if not text or not conversation_history:
            return ResolvedContext(
                files=list(dict.fromkeys(explicit_files)),
                equipment_ids=list(dict.fromkeys(explicit_equipment)),
                has_anaphora=has_anaphora,
                pinned_source=pinned_source,
                is_affirmation=is_affirmation,
                is_cancellation=is_cancellation,
                requested_page=requested_page
            )

        # If no anaphora, no affirmation, and no reference triggers, do not inherit stale context
        if not has_anaphora:
            return ResolvedContext(
                files=list(dict.fromkeys(explicit_files)),
                equipment_ids=list(dict.fromkeys(explicit_equipment)),
                has_anaphora=False,
                pinned_source=pinned_source,
                is_affirmation=False,
                is_cancellation=False,
                requested_page=requested_page
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
            if not found_files and workspace_id:
                # Also resolve domain document references (e.g. "inspection report", "financial sheet")
                matched_doc = resolve_target_document_for_query_sync(workspace_id, content)
                if matched_doc and matched_doc.get("name"):
                    found_files = [matched_doc["name"]]
                    if pinned_source is None:
                        pinned_source = matched_doc

            if found_files and not resolved_files:
                resolved_files = list(dict.fromkeys(found_files))
                source_turn = turn_idx
                topic = f"Artifact inquiry: {resolved_files[0]}"
                if pinned_source is None and workspace_id:
                    pinned_source = resolve_target_document_for_query_sync(workspace_id, resolved_files[0])

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
            is_cancellation=is_cancellation,
            requested_page=requested_page
        )
