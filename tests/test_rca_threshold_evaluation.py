"""Unit tests for centralized threshold evaluation and strict status scoring."""
import pytest
from cognishift.core.rca.evaluation import (
    evaluate_threshold,
    score_status_strict,
    MetricStatus
)


def test_evaluate_threshold_rejects_below_target_as_not_pass():
    """Verify that 87.1% against a >=90.0% target strictly evaluates to DEGRADED, NEVER PASS."""
    res = evaluate_threshold(87.1, 90.0, comparison=">=")
    assert res != MetricStatus.PASS
    assert res == MetricStatus.DEGRADED

    res_dec = evaluate_threshold(0.871, 0.900, comparison=">=")
    assert res_dec != MetricStatus.PASS
    assert res_dec == MetricStatus.DEGRADED


def test_evaluate_threshold_pass_and_fail():
    """Verify passing and failing metric evaluations."""
    assert evaluate_threshold(95.0, 90.0, ">=") == MetricStatus.PASS
    assert evaluate_threshold(50.0, 90.0, ">=") == MetricStatus.FAIL
    assert evaluate_threshold(0.0, 0.0, "<=") == MetricStatus.PASS
    assert evaluate_threshold(0.05, 0.0, "<=") == MetricStatus.DEGRADED
    assert evaluate_threshold(0.20, 0.0, "<=") == MetricStatus.FAIL


def test_strict_status_scoring_exact_and_adjacent():
    """Verify 1.0 for exact, 0.5 for adjacent, and 0.0 for others."""
    # Exact match
    score, classif = score_status_strict("SUPPORTED_LIKELY_CAUSE", "SUPPORTED_LIKELY_CAUSE", ["PLAUSIBLE_HYPOTHESIS"])
    assert score == 1.0
    assert classif == "EXACT"

    # Adjacent conservative match
    score, classif = score_status_strict("PLAUSIBLE_HYPOTHESIS", "SUPPORTED_LIKELY_CAUSE", ["PLAUSIBLE_HYPOTHESIS"])
    assert score == 0.5
    assert "ADJACENT" in classif

    # Overconfident unverified claim gets 0.0
    score, classif = score_status_strict("CONFIRMED_CAUSE", "SUPPORTED_LIKELY_CAUSE", ["PLAUSIBLE_HYPOTHESIS"])
    assert score == 0.0
    assert classif == "OVERCONFIDENT"


def test_insufficient_evidence_disallows_partial_credit():
    """For insufficient evidence cases, only exact INSUFFICIENT_EVIDENCE earns credit."""
    score, _ = score_status_strict("INSUFFICIENT_EVIDENCE", "INSUFFICIENT_EVIDENCE", [])
    assert score == 1.0

    score_hyp, _ = score_status_strict("PLAUSIBLE_HYPOTHESIS", "INSUFFICIENT_EVIDENCE", ["PLAUSIBLE_HYPOTHESIS"])
    assert score_hyp == 0.0
