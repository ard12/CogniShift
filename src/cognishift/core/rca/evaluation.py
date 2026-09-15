"""Centralized Metric Threshold Evaluation and Strict Scoring for RCA Benchmarks."""
from enum import Enum
from typing import List, Dict, Any, Tuple, Optional


class MetricStatus(str, Enum):
    PASS = "PASS"
    DEGRADED = "DEGRADED"
    FAIL = "FAIL"
    INFORMATIONAL = "INFORMATIONAL"


def evaluate_threshold(value: float, target: Optional[float], comparison: str = ">=") -> MetricStatus:
    """
    Deterministically evaluates a metric value against its target threshold.
    Returns PASS, DEGRADED, FAIL, or INFORMATIONAL.
    Eliminates hardcoded PASS labels.
    """
    if target is None or comparison == "informational":
        return MetricStatus.INFORMATIONAL

    if comparison in (">=", "gte"):
        if value >= target:
            return MetricStatus.PASS
        elif value >= (target - 0.10) or (target > 1.0 and value >= (target - 10.0)):
            return MetricStatus.DEGRADED
        else:
            return MetricStatus.FAIL

    elif comparison in ("<=", "lte"):
        if value <= target:
            return MetricStatus.PASS
        elif value <= (target + 0.10) or (target > 1.0 and value <= (target + 10.0)):
            return MetricStatus.DEGRADED
        else:
            return MetricStatus.FAIL

    elif comparison in ("==", "eq"):
        if abs(value - target) < 1e-6:
            return MetricStatus.PASS
        return MetricStatus.FAIL

    return MetricStatus.INFORMATIONAL


def score_status_strict(
    matched_status: str,
    expected_status: str,
    tolerated_adjacent_statuses: Optional[List[str]] = None
) -> Tuple[float, str]:
    """
    Scores RCA status strictly:
    - Exact match: 1.0
    - One explicitly adjacent conservative status: 0.5
    - Anything else: 0.0

    Returns:
        (score, match_classification)
    """
    clean_matched = (matched_status or "").strip().upper().replace(" ", "_")
    clean_expected = (expected_status or "").strip().upper().replace(" ", "_")
    tolerated = [s.strip().upper().replace(" ", "_") for s in (tolerated_adjacent_statuses or [])]

    CONFIDENCE_RANK = {
        "CONFIRMED_CAUSE": 4,
        "SUPPORTED_LIKELY_CAUSE": 3,
        "PLAUSIBLE_HYPOTHESIS": 2,
        "INSUFFICIENT_EVIDENCE": 1,
        "ASSET_NOT_FOUND": 0,
        "CONTRADICTORY_EVIDENCE": 1
    }

    if clean_matched == clean_expected:
        return 1.0, "EXACT"

    # For insufficient evidence and OOD, disallow partial credit
    if clean_expected in ("INSUFFICIENT_EVIDENCE", "ASSET_NOT_FOUND"):
        return 0.0, "FAIL"

    matched_rank = CONFIDENCE_RANK.get(clean_matched, 0)
    expected_rank = CONFIDENCE_RANK.get(clean_expected, 0)

    classification = "OVERCONFIDENT" if matched_rank > expected_rank else "UNDERCONFIDENT"

    if clean_matched in tolerated:
        return 0.5, f"ADJACENT_{classification}"

    return 0.0, classification
