"""
Deterministic Page Verifier & Evidence Corroborator.
Cross-references VLM visual claims against deterministic OCR / native text
to corroborate numeric values, instrument tags, and operational readings.
NOTE: Adheres to user rule: OCR is corroborating evidence, not absolute ground truth.
"""
import re
import logging
from typing import Optional, List, Tuple
from cognishift.app.db.database import get_db
from cognishift.core.visual_rag.schemas import CorroborationResult

logger = logging.getLogger(__name__)

# Patterns to extract verifiable assertions
TAG_PATTERN = re.compile(r"\b([A-Z]{1,4}-\d{2,4}[A-Z]?)\b")
NUMERIC_UNIT_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(psi|bar|kpa|mpa|rpm|gpm|m3/h|°c|°f|k|v|a|kw|hz|mpy|mm/year|mm|cm|m|%)\b",
    re.IGNORECASE
)
STANDALONE_NUMBER_PATTERN = re.compile(r"\b(\d{2,}(?:\.\d+)?)\b")


class DeterministicPageVerifier:
    """Verifies and corroborates VLM observations against page OCR/native text."""

    @staticmethod
    def extract_claims(vlm_text: str) -> List[Tuple[str, str]]:
        """
        Extracts testable claims (claim_type, value_str) from VLM output.
        """
        claims: List[Tuple[str, str]] = []
        if not vlm_text:
            return claims

        # 1. Instrument / Equipment Tags
        for match in TAG_PATTERN.finditer(vlm_text):
            tag = match.group(1).upper()
            claims.append(("instrument_tag", tag))

        # 2. Number + Unit
        for match in NUMERIC_UNIT_PATTERN.finditer(vlm_text):
            num_unit = f"{match.group(1)} {match.group(2).lower()}"
            claims.append(("reading_with_unit", num_unit))

        # 3. Standalone significant numbers (>= 2 digits or with decimal)
        for match in STANDALONE_NUMBER_PATTERN.finditer(vlm_text):
            num_val = match.group(1)
            # avoid duplicating if already in reading_with_unit
            if not any(num_val in c[1] for c in claims if c[0] == "reading_with_unit"):
                claims.append(("numeric", num_val))

        return list(dict.fromkeys(claims))

    async def verify_page_claims(
        self,
        workspace_id: int,
        source_id: int,
        processing_version: str,
        page_number: int,
        vlm_observation: str
    ) -> List[CorroborationResult]:
        """
        Retrieves page OCR/native text and evaluates corroboration for each VLM claim.
        """
        claims = self.extract_claims(vlm_observation)
        if not claims:
            return []

        # Retrieve ground truth OCR / native text from SQLite
        page_text = ""
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT text_content FROM document_pages
                   WHERE workspace_id = ? AND source_id = ?
                     AND processing_version = ? AND page_number = ?""",
                (workspace_id, source_id, processing_version, page_number)
            )
            row = await cursor.fetchone()
            if row and row["text_content"]:
                page_text = row["text_content"]

        if not page_text:
            return [
                CorroborationResult(
                    claim_type=c_type,
                    claimed_value=val,
                    ocr_found_value=None,
                    corroborated=False,
                    details="No OCR/native text available for page."
                )
                for c_type, val in claims
            ]

        results: List[CorroborationResult] = []
        page_text_lower = page_text.lower()

        for c_type, val in claims:
            clean_val = val.strip().lower()
            # Direct match check
            if clean_val in page_text_lower:
                results.append(
                    CorroborationResult(
                        claim_type=c_type,
                        claimed_value=val,
                        ocr_found_value=val,
                        corroborated=True,
                        details=f"Corroborated by page text."
                    )
                )
            else:
                # Numeric tolerance check (e.g. '142.5 psi' -> check if '142.5' exists)
                parts = clean_val.split()
                if len(parts) == 2 and parts[0] in page_text_lower:
                    results.append(
                        CorroborationResult(
                            claim_type=c_type,
                            claimed_value=val,
                            ocr_found_value=parts[0],
                            corroborated=True,
                            details=f"Number '{parts[0]}' corroborated; unit '{parts[1]}' implicit or separate."
                        )
                    )
                else:
                    results.append(
                        CorroborationResult(
                            claim_type=c_type,
                            claimed_value=val,
                            ocr_found_value=None,
                            corroborated=False,
                            details=f"Value '{val}' was not found in page OCR text."
                        )
                    )

        return results

    def format_corroboration_summary(self, results: List[CorroborationResult]) -> str:
        """Formats a human-readable corroboration summary for LLM prompt context."""
        if not results:
            return ""

        corroborated = [r.claimed_value for r in results if r.corroborated]
        unverified = [r.claimed_value for r in results if not r.corroborated]

        parts = []
        if corroborated:
            parts.append(f"OCR Corroborated: {', '.join(corroborated)}")
        if unverified:
            parts.append(f"Uncorroborated (VLM only, verify on page): {', '.join(unverified)}")

        return " | ".join(parts)


_global_page_verifier: Optional[DeterministicPageVerifier] = None


def get_page_verifier() -> DeterministicPageVerifier:
    global _global_page_verifier
    if _global_page_verifier is None:
        _global_page_verifier = DeterministicPageVerifier()
    return _global_page_verifier
