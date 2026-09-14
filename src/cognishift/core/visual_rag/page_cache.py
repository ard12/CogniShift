"""
On-Demand Page Rendering & Bounded In-Memory LRU Cache.
Avoids permanently duplicating every rendered page to disk while providing
rapid access to candidate pages for VLM inspection and UI previews.
"""
import asyncio
import logging
from collections import OrderedDict
from pathlib import Path
from typing import Optional, Tuple
import pymupdf

from cognishift.app.config import settings
from cognishift.core.document_processing.pdf_extractor import render_page_to_png_bytes

logger = logging.getLogger(__name__)


class PageImageCache:
    """Thread-safe bounded in-memory LRU cache for rendered PDF pages."""

    def __init__(self, max_entries: int = 50):
        self.max_entries = max_entries
        self._cache: OrderedDict[Tuple[str, int, int], bytes] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, file_path: str, page_number: int, dpi: int) -> Optional[bytes]:
        key = (str(Path(file_path).resolve()), page_number, dpi)
        async with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    async def put(self, file_path: str, page_number: int, dpi: int, data: bytes) -> None:
        key = (str(Path(file_path).resolve()), page_number, dpi)
        async with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = data
            while len(self._cache) > self.max_entries:
                self._cache.popitem(last=False)

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)


_global_page_cache: Optional[PageImageCache] = None


def get_page_image_cache() -> PageImageCache:
    """Singleton getter for the bounded page image cache."""
    global _global_page_cache
    if _global_page_cache is None:
        cache_size = getattr(settings, "visual_page_cache_size", 50)
        _global_page_cache = PageImageCache(max_entries=cache_size)
    return _global_page_cache


async def render_page_image_on_demand(
    file_path: Path,
    page_number: int,
    dpi: int = 150
) -> bytes:
    """
    Renders a PDF page or Office slide/page to PNG bytes on demand with bounded LRU caching.
    Guarantees no redundant rasterization if recently inspected.
    """
    cache = get_page_image_cache()
    cached = await cache.get(str(file_path), page_number, dpi)
    if cached is not None:
        return cached

    def _render() -> bytes:
        p = Path(file_path)
        ext = p.suffix.lower()
        if ext == ".pptx":
            from cognishift.core.document_processing.office_renderer import render_pptx_slides
            slides, status = render_pptx_slides(p)
            for s_num, s_bytes in slides:
                if s_num == page_number:
                    return s_bytes
            raise ValueError(f"Slide {page_number} not found in {file_path} (render status: {status})")
        elif ext == ".docx":
            from cognishift.core.document_processing.office_renderer import render_docx_pages
            pages, status = render_docx_pages(p)
            if 1 <= page_number <= len(pages):
                return pages[page_number - 1]
            raise ValueError(f"Page {page_number} not found in {file_path} (render status: {status})")
        else:
            doc = pymupdf.open(str(file_path))
            try:
                return render_page_to_png_bytes(doc, page_number, dpi=dpi)
            finally:
                doc.close()

    png_bytes = await asyncio.to_thread(_render)
    await cache.put(str(file_path), page_number, dpi, png_bytes)
    return png_bytes
