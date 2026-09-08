from pathlib import Path


ENGINE = Path(__file__).resolve().parents[1] / "src" / "cognishift" / "core" / "engine.py"


def test_runtime_generation_templates_do_not_claim_unverified_physical_isolation_or_signoff():
    source = ENGINE.read_text(encoding="utf-8")

    forbidden = (
        "100% air-gapped sovereign execution",
        "Verified Zero Egress: 100% On-Premise Sovereign Execution",
        "Sovereign Compliance: Computed in air-gapped environment with zero cloud egress.",
        "Authoritative Sign-Off & Compliance",
        "Lead Auditor / Sign-off",
    )
    for phrase in forbidden:
        assert phrase not in source

    assert "External internet access blocked by strict application policy" in source
    assert "physical isolation not asserted" in source.lower()
