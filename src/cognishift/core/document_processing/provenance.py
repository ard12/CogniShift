"""
Page-Aware Chunking & Provenance Tracking.
Enforces strict 1-based page boundary preservation, rich metadata formatting,
and untrusted data tagging to prevent prompt injection from documents.
"""
import html
from typing import List, Dict, Any, Tuple
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
    filename = metadata.get("filename", "Document")
    page = metadata.get("page", 1)
    method = metadata.get("extraction_method", "native").upper()
    return f"[{filename} | Page {page} | {method}]"


def wrap_document_data_for_prompt(text: str, metadata: Dict[str, Any]) -> str:
    """
    Wraps untrusted retrieved text into explicit XML-style document context tags.
    Clearly marks document content as DATA, preventing instruction overriding.
    Escapes metadata attributes to prevent XML delimiter breakout.
    """
    src = html.escape(str(metadata.get("filename", "unknown")), quote=True)
    page = html.escape(str(metadata.get("page", 1)), quote=True)
    method = html.escape(str(metadata.get("extraction_method", "native")), quote=True)
    return f'<document_context source="{src}" page="{page}" method="{method}">\n{text}\n</document_context>'
