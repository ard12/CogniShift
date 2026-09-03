"""
Document Processing Orchestrator Service.
Implements the canonical processing flow:
Upload -> Validation -> Inspection -> Page-Scoped Extraction (Native / OCR / Vision)
-> Page Provenance -> Versioned Generation Chunking -> Vector Indexing -> Activation.
"""
import shutil
import logging
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
import pymupdf

from cognishift.app.config import settings
from cognishift.app.db.database import get_db
from cognishift.core.security import get_workspace_root
from cognishift.core.retriever import chroma_client, embedding_model
from cognishift.core.document_processing.schemas import (
    DocumentType,
    ExtractionMethod,
    VisionRequirement,
    ExtractedPage,
    OCRResult,
    VisionObservation,
    DocumentProcessingError,
    OCRUnavailableError,
    VisionModelUnavailableError
)
from cognishift.core.document_processing.inspector import inspect_document, assess_native_page_quality
from cognishift.core.document_processing.pdf_extractor import extract_native_page, render_page_to_png_bytes
from cognishift.core.document_processing.image_preprocessor import preprocess_image_for_ocr
from cognishift.core.document_processing.ocr_provider import get_ocr_provider, OCRProvider
from cognishift.core.document_processing.vision_service import VisionProcessingService
from cognishift.core.document_processing.provenance import PageAwareChunker
from cognishift.core.document_processing.lifecycle import (
    create_processing_generation,
    activate_processing_generation,
    fail_processing_generation,
    retire_and_purge_old_generations
)

logger = logging.getLogger(__name__)


class DocumentProcessingService:
    """End-to-end multimodal document ingestion service."""

    def __init__(
        self,
        ocr_provider: Optional[OCRProvider] = None,
        vision_service: Optional[VisionProcessingService] = None
    ):
        self.ocr_provider = ocr_provider or get_ocr_provider()
        self.vision_service = vision_service or VisionProcessingService()
        self.chunker = PageAwareChunker()

    async def process_document(
        self,
        workspace_id: int,
        source_id: int,
        file_path: Path,
        filename: Optional[str] = None,
        vision_requirement: VisionRequirement = VisionRequirement.NOT_REQUIRED
    ) -> Dict[str, Any]:
        """
        Executes end-to-end versioned document processing and indexing.
        Guarantees:
        1. Atomic versioned generation.
        2. Preservation of previous active generation on error.
        3. 100% ephemeral temporary file cleanup in finally: block.
        """
        doc_filename = filename or file_path.name
        version = await create_processing_generation(workspace_id, source_id)
        
        # Ephemeral staging path under workspace temporary/
        ws_root = get_workspace_root(workspace_id)
        temp_dir = ws_root / "temporary" / f"doc_proc_{version}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Inspection & validation
            inspection = inspect_document(file_path)
            
            async with get_db() as db:
                await db.execute(
                    """UPDATE document_processing_jobs 
                       SET status = 'extracting', total_pages = ? 
                       WHERE source_id = ? AND processing_version = ?""",
                    (inspection.page_count, source_id, version)
                )
                await db.commit()

            extracted_pages: List[ExtractedPage] = []
            native_count = 0
            ocr_count = 0
            vision_count = 0

            # 2. Document Extraction Loop
            if inspection.document_type == DocumentType.PDF:
                doc = pymupdf.open(str(file_path))
                try:
                    for page_num in range(1, len(doc) + 1):
                        # Page-scoped triage
                        native_text, img_count = extract_native_page(doc, page_num)
                        is_usable = assess_native_page_quality(native_text, img_count)

                        if is_usable:
                            # Use clean native text (0 OCR call)
                            extracted_pages.append(
                                ExtractedPage(
                                    page_number=page_num,
                                    text=native_text,
                                    extraction_method=ExtractionMethod.NATIVE,
                                    has_images=(img_count > 0),
                                    image_count=img_count
                                )
                            )
                            native_count += 1
                        else:
                            # Targeted OCR fallback for unreadable/scanned page
                            page_png = render_page_to_png_bytes(doc, page_num, dpi=settings.max_raster_dpi)
                            proc_png = preprocess_image_for_ocr(page_png)
                            ocr_res = await self.ocr_provider.extract(proc_png)

                            avg_conf = ocr_res.confidence if ocr_res.confidence is not None else 1.0
                            is_uncertain = avg_conf < settings.ocr_normal_confidence_threshold

                            extracted_pages.append(
                                ExtractedPage(
                                    page_number=page_num,
                                    text=ocr_res.text,
                                    extraction_method=ExtractionMethod.OCR,
                                    ocr_confidence=ocr_res.confidence,
                                    ocr_uncertain=is_uncertain,
                                    has_images=True,
                                    image_count=img_count
                                )
                            )
                            ocr_count += 1
                finally:
                    doc.close()

            else:
                # Image document (PNG or JPEG)
                with open(file_path, "rb") as f:
                    img_bytes = f.read()

                proc_ocr_bytes = preprocess_image_for_ocr(img_bytes)
                ocr_res = await self.ocr_provider.extract(proc_ocr_bytes)
                ocr_count += 1

                final_text = ocr_res.text
                method = ExtractionMethod.OCR
                ocr_conf = ocr_res.confidence

                # Optional/Required Vision Analysis
                if vision_requirement != VisionRequirement.NOT_REQUIRED:
                    v_obs = await self.vision_service.analyze_document_image(
                        image_bytes=img_bytes,
                        page_number=1,
                        requirement=vision_requirement
                    )
                    if v_obs:
                        vision_count += 1
                        method = ExtractionMethod.HYBRID
                        final_text = f"{final_text}\n\n--- VISUAL OBSERVATION ---\n{v_obs.description}"

                avg_conf = ocr_conf if ocr_conf is not None else 1.0
                is_uncertain = avg_conf < settings.ocr_normal_confidence_threshold

                extracted_pages.append(
                    ExtractedPage(
                        page_number=1,
                        text=final_text,
                        extraction_method=method,
                        ocr_confidence=ocr_conf,
                        ocr_uncertain=is_uncertain,
                        has_images=True,
                        image_count=1
                    )
                )

            # 3. Store canonical extracted pages in SQLite document_pages
            async with get_db() as db:
                for p in extracted_pages:
                    await db.execute(
                        """INSERT OR REPLACE INTO document_pages 
                           (source_id, workspace_id, processing_version, page_number, extraction_method, ocr_confidence, text_content)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (source_id, workspace_id, version, p.page_number, p.extraction_method.value, p.ocr_confidence, p.text)
                    )
                await db.execute(
                    """UPDATE document_processing_jobs 
                       SET status = 'indexing', native_pages = ?, ocr_pages = ?, vision_pages = ?
                       WHERE source_id = ? AND processing_version = ?""",
                    (native_count, ocr_count, vision_count, source_id, version)
                )
                await db.commit()

            # 4. Page-Aware Chunking & Vector Indexing
            chunks, ids, metadatas = self.chunker.chunk_document_pages(
                pages=extracted_pages,
                workspace_id=workspace_id,
                source_id=source_id,
                processing_version=version,
                filename=doc_filename
            )

            if chunks:
                # Embed chunks with FastEmbed off-thread
                def _embed_batch():
                    gen = embedding_model.embed(chunks)
                    return [e.tolist() if hasattr(e, "tolist") else [float(x) for x in e] for e in gen]

                embeddings = await asyncio.to_thread(_embed_batch)

                # Batch upsert into Chroma
                collection_name = f"workspace_{workspace_id}"
                collection = chroma_client.get_or_create_collection(name=collection_name)

                BATCH_SIZE = 250
                for i in range(0, len(chunks), BATCH_SIZE):
                    b_docs = chunks[i:i + BATCH_SIZE]
                    b_embs = embeddings[i:i + BATCH_SIZE]
                    b_meta = metadatas[i:i + BATCH_SIZE]
                    b_ids = ids[i:i + BATCH_SIZE]
                    await asyncio.to_thread(
                        collection.upsert,
                        documents=b_docs,
                        embeddings=b_embs,
                        metadatas=b_meta,
                        ids=b_ids
                    )

            # 5. Success! Atomically activate new generation
            await activate_processing_generation(workspace_id, source_id, version)

            # Update chunk count on knowledge source
            async with get_db() as db:
                await db.execute(
                    "UPDATE knowledge_sources SET chunk_count = ? WHERE id = ?",
                    (len(chunks), source_id)
                )
                await db.commit()

            # 6. Retire old generation chunks safely
            await retire_and_purge_old_generations(workspace_id, source_id, active_version=version)

            return {
                "source_id": source_id,
                "processing_version": version,
                "status": "completed",
                "total_pages": len(extracted_pages),
                "native_pages": native_count,
                "ocr_pages": ocr_count,
                "vision_pages": vision_count,
                "chunk_count": len(chunks)
            }

        except Exception as e:
            logger.error(f"Processing failed for source {source_id} (version {version}): {e}")
            await fail_processing_generation(
                workspace_id=workspace_id,
                source_id=source_id,
                version=version,
                error_code=type(e).__name__,
                error_msg=str(e)
            )
            raise

        finally:
            # 7. Guaranteed Ephemeral Directory Cleanup
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except Exception as c_err:
                    logger.warning(f"Failed to cleanup temp dir {temp_dir}: {c_err}")
