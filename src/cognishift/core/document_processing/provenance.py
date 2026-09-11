"""
Page-Aware Chunking & Provenance Tracking.
Enforces strict 1-based page boundary preservation, rich metadata formatting,
and untrusted data tagging to prevent prompt injection from documents.
"""
import html
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Set
from cognishift.core.document_processing.schemas import ExtractedPage, ExtractionMethod


class RecursiveCharacterTextSplitter:
    """Zero-dependency recursive text splitter with overlap."""
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 80):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            if end >= len(text):
                chunks.append(text[start:].strip())
                break
            split_at = -1
            for sep in ['\n\n', '\n', '. ', ' ']:
                idx = text.rfind(sep, start, end)
                if idx != -1:
                    split_at = idx + len(sep)
                    break
            if split_at == -1 or split_at <= start:
                split_at = end
            chunk = text[start:split_at].strip()
            if chunk:
                chunks.append(chunk)
            start = max(start + 1, split_at - self.chunk_overlap)
        return [c for c in chunks if c]


class PageAwareChunker:
    """
    Chunks extracted pages strictly within single-page boundaries.
    Ensures that every vector embedding retains unambiguous page and source provenance.
    """
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 80):
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def chunk_document_pages(
        self,
        pages: List[ExtractedPage],
        workspace_id: int,
        source_id: int,
        processing_version: str,
        filename: str
    ) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
        """
        Splits pages into chunks and returns:
        (chunk_texts, chunk_ids, metadatas)
        """
        chunk_texts: List[str] = []
        chunk_ids: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        global_chunk_idx = 0
        for page in pages:
            if not page.text or not page.text.strip():
                continue

            # Split page text strictly within page
            p_chunks = self.splitter.split_text(page.text)
            for c_idx, raw_chunk in enumerate(p_chunks):
                clean_chunk = raw_chunk.strip()
                if not clean_chunk:
                    continue

                chunk_id = f"doc_{source_id}_v_{processing_version[:8]}_p{page.page_number}_c{global_chunk_idx}"
                meta = {
                    "source_id": int(source_id),
                    "workspace_id": int(workspace_id),
                    "processing_version": str(processing_version),
                    "filename": str(filename),
                    "page": int(page.page_number),
                    "chunk_idx": int(global_chunk_idx),
                    "extraction_method": str(page.extraction_method.value),
                    "ocr_confidence": float(page.ocr_confidence) if page.ocr_confidence is not None else 1.0,
                    "ocr_uncertain": bool(page.ocr_uncertain)
                }

                chunk_texts.append(clean_chunk)
                chunk_ids.append(chunk_id)
                metadatas.append(meta)
                global_chunk_idx += 1

        return chunk_texts, chunk_ids, metadatas


def format_grounded_citation(metadata: Dict[str, Any]) -> str:
    """Formats human-facing citation string with document, page, and extraction method."""
    filename = (
        metadata.get("filename")
        or metadata.get("document")
        or metadata.get("document_name")
        or metadata.get("original_filename")
        or metadata.get("name")
        or "Document"
    )
    page = metadata.get("page") or metadata.get("page_number") or 1
    method = metadata.get("extraction_method", "native").upper()
    return f"[{filename} | Page {page} | {method}]"


def wrap_document_data_for_prompt(text: str, metadata: Dict[str, Any]) -> str:
    """
    Wraps untrusted retrieved text into explicit XML-style document context tags.
    Clearly marks document content as DATA, preventing instruction overriding.
    Escapes both metadata attributes and body text to prevent XML delimiter breakout.
    Defense-in-depth data demarcation only; deterministic authorization is enforced separately.
    """
    raw_fname = (
        metadata.get("filename")
        or metadata.get("document")
        or metadata.get("document_name")
        or metadata.get("original_filename")
        or metadata.get("name")
        or "unknown"
    )
    src = html.escape(str(raw_fname), quote=True)
    page_val = metadata.get("page") or metadata.get("page_number") or 1
    page = html.escape(str(page_val), quote=True)
    method = html.escape(str(metadata.get("extraction_method", "native")), quote=True)
    safe_text = html.escape(text, quote=False)
    return f'<document_context source="{src}" page="{page}" method="{method}">\n{safe_text}\n</document_context>'


def extract_and_normalize_citations(text: str = "", model_citations: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Extracts citations from text and/or model_citations list and normalizes them into structured dictionaries:
    [{"filename": str, "page": int, "method": Optional[str], "citation_str": str}]
    """
    candidates: List[str] = []
    if model_citations:
        for c in model_citations:
            if isinstance(c, str) and c.strip():
                candidates.append(c.strip())

    if text:
        # Match bracketed citations like [Document.pdf | Page 3 | NATIVE] or [Document.pdf | Page 3] or [Document.pdf, Page 3]
        bracketed = re.findall(r"\[([^\]]*?(?:\.pdf|\.csv|\.xlsx|\.png|\.jpg|\.txt)[^\]]*?)\]", text, re.IGNORECASE)
        candidates.extend(bracketed)
        # Also match standard [file | Page X] even without known extension
        bracketed_generic = re.findall(r"\[([^\]]*?\|\s*Page\s*\d+[^\]]*?)\]", text, re.IGNORECASE)
        candidates.extend(bracketed_generic)

    results: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, int]] = set()

    for item in candidates:
        raw = item.strip().strip("[]").strip()
        if not raw:
            continue

        parts = [p.strip() for p in re.split(r"\s*[|;,]\s*", raw) if p.strip()]
        if not parts:
            continue

        filename = parts[0]
        page = 1
        method = None

        for p in parts[1:]:
            page_match = re.search(r"(?:page|p\.)\s*(\d+)", p, re.IGNORECASE)
            if page_match:
                page = int(page_match.group(1))
            elif p.upper() in ("NATIVE", "OCR", "TABLE", "SPREADSHEET", "VISION"):
                method = p.upper()

        if page == 1:
            pm = re.search(r"(?:page|p\.)\s*(\d+)", raw, re.IGNORECASE)
            if pm:
                page = int(pm.group(1))

        if not method:
            for m in ("NATIVE", "OCR", "TABLE", "SPREADSHEET", "VISION"):
                if re.search(rf"\b{m}\b", raw, re.IGNORECASE):
                    method = m
                    break

        clean_filename = Path(filename).name if ("/" in filename or "\\" in filename) else filename
        key = (clean_filename.lower(), page)
        if key not in seen:
            seen.add(key)
            canonical = f"[{clean_filename} | Page {page} | {method}]" if method else f"[{clean_filename} | Page {page}]"
            results.append({
                "filename": clean_filename,
                "page": page,
                "method": method,
                "citation_str": canonical
            })

    return results


def reconcile_citations_against_evidence(
    text: str = "",
    model_citations: Optional[List[str]] = None,
    retrieved_evidence: Optional[List[Dict[str, Any]]] = None,
    fallback_to_evidence_if_empty: bool = True
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Reconciles model citations against authoritative retrieved evidence chunks.
    Eliminates page hallucinations by snapping to retrieved pages.
    Deduplicates and canonicalizes citations.
    Returns (verified_citations, sources_used_string).
    """
    if not retrieved_evidence:
        extracted = extract_and_normalize_citations(text, model_citations)
        if extracted:
            sources_str = ", ".join(c["citation_str"] for c in extracted)
            return extracted, sources_str
        return [], "None (No matching manual found)"

    exact_map: Dict[Tuple[str, int], Dict[str, Any]] = {}
    file_to_chunks: Dict[str, List[Dict[str, Any]]] = {}
    for meta in retrieved_evidence:
        fname = (
            meta.get("filename")
            or meta.get("document")
            or meta.get("document_name")
            or meta.get("original_filename")
            or meta.get("name")
            or "Document"
        )
        fname_clean = Path(fname).name if ("/" in fname or "\\" in fname) else fname
        page = int(meta.get("page") or meta.get("page_number") or 1)
        method = str(meta.get("extraction_method", "native")).upper()
        key = (fname_clean.lower(), page)
        canonical = f"[{fname_clean} | Page {page} | {method}]"
        info = {
            "filename": fname_clean,
            "page": page,
            "method": method,
            "citation_str": canonical,
            "meta": meta
        }
        exact_map[key] = info
        file_to_chunks.setdefault(fname_clean.lower(), []).append(info)

    extracted_candidates = extract_and_normalize_citations(text, model_citations)
    verified: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, int]] = set()

    for cand in extracted_candidates:
        cfname = cand["filename"].lower()
        cpage = cand["page"]

        # 1. Exact match (document and page)
        if (cfname, cpage) in exact_map:
            match_info = exact_map[(cfname, cpage)]
            key = (match_info["filename"].lower(), match_info["page"])
            if key not in seen:
                seen.add(key)
                verified.append(match_info)
            continue

        # 2. Document match with different/hallucinated page
        matched_doc_key = None
        if cfname in file_to_chunks:
            matched_doc_key = cfname
        else:
            for known_doc in file_to_chunks:
                if cfname in known_doc or known_doc in cfname:
                    matched_doc_key = known_doc
                    break

        if matched_doc_key:
            chunks = file_to_chunks[matched_doc_key]
            best_chunk = chunks[0]
            if len(chunks) > 1:
                best_chunk = min(chunks, key=lambda c: abs(c["page"] - cpage))
            key = (best_chunk["filename"].lower(), best_chunk["page"])
            if key not in seen:
                seen.add(key)
                verified.append(best_chunk)
            continue

    # 3. Fallback to retrieved evidence if model omitted citations
    if not verified and fallback_to_evidence_if_empty:
        for meta in retrieved_evidence:
            fname = (
                meta.get("filename")
                or meta.get("document")
                or meta.get("document_name")
                or meta.get("original_filename")
                or meta.get("name")
                or "Document"
            )
            fname_clean = Path(fname).name if ("/" in fname or "\\" in fname) else fname
            page = int(meta.get("page") or meta.get("page_number") or 1)
            method = str(meta.get("extraction_method", "native")).upper()
            canonical = f"[{fname_clean} | Page {page} | {method}]"
            key = (fname_clean.lower(), page)
            if key not in seen:
                seen.add(key)
                verified.append({
                    "filename": fname_clean,
                    "page": page,
                    "method": method,
                    "citation_str": canonical,
                    "meta": meta
                })

    sources_used = ", ".join(c["citation_str"] for c in verified) if verified else "None (No matching manual found)"
    return verified, sources_used


def reconcile_citations_in_text(
    text: str,
    verified_citations: List[Dict[str, Any]],
    retrieved_evidence: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Rewrites any hallucinated or malformed bracketed citations inside text
    to authoritative retrieved filenames and page numbers.
    The model is never permitted to dictate page numbers.
    """
    if not text:
        return text

    # Build reference lookup from verified citations and retrieved evidence
    ref_map: Dict[str, Dict[str, Any]] = {}
    if verified_citations:
        for c in verified_citations:
            ref_map[c["filename"].lower()] = c
    if retrieved_evidence:
        for meta in retrieved_evidence:
            fname = (
                meta.get("filename")
                or meta.get("document")
                or meta.get("document_name")
                or meta.get("original_filename")
                or meta.get("name")
                or ""
            )
            if fname:
                fname_clean = Path(fname).name if ("/" in fname or "\\" in fname) else fname
                if fname_clean.lower() not in ref_map:
                    p = int(meta.get("page") or meta.get("page_number") or 1)
                    ref_map[fname_clean.lower()] = {
                        "filename": fname_clean,
                        "page": p,
                        "method": str(meta.get("extraction_method", "native")).upper()
                    }

    def _replace_cite(match: re.Match) -> str:
        raw = match.group(1).strip()
        parts = [p.strip() for p in re.split(r"\s*[|;,]\s*", raw) if p.strip()]
        if not parts:
            return match.group(0)
        cand_fname = parts[0]
        cand_clean = Path(cand_fname).name if ("/" in cand_fname or "\\" in cand_fname) else cand_fname

        # Lookup in ref_map
        matched_info = None
        if cand_clean.lower() in ref_map:
            matched_info = ref_map[cand_clean.lower()]
        else:
            for k, info in ref_map.items():
                if cand_clean.lower() in k or k in cand_clean.lower():
                    matched_info = info
                    break

        if matched_info:
            p = matched_info["page"]
            m = matched_info.get("method")
            if m:
                return f"[{matched_info['filename']} | Page {p} | {m}]"
            return f"[{matched_info['filename']} | Page {p}]"

        return match.group(0)

    pattern = r"\[([^\]]+?(?:\.pdf|\.csv|\.xlsx|\.png|\.jpg|\.txt)[^\]]*?)\]"
    return re.sub(pattern, _replace_cite, text, flags=re.IGNORECASE)


