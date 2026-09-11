"""Test suite for RCA Evidence Acquisition, Contract Parsing, and OOD Asset Checks."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from cognishift.core.rca.evidence_acquisition import RCAEvidenceAcquirer
from cognishift.core.rca.schemas import EvidenceRole, ChannelExecutionHealth


def test_parse_evidence_contract_explicit_sources_and_roles():
    acquirer = RCAEvidenceAcquirer(allow_simulation=True)

    query = "Investigate P-101A trip. Cross-reference the inspection report, maintenance SOP, and vibration logs for cavitation."
    contract = acquirer.parse_evidence_contract(query)

    assert "P-101A" in contract["assets"]
    assert "inspection_report" in contract["explicit_sources"]
    assert "maintenance_sop" in contract["explicit_sources"]
    assert "vibration_log" in contract["explicit_sources"]
    assert EvidenceRole.INSPECTION in contract["required_roles"]
    assert EvidenceRole.SOP_BASELINE in contract["required_roles"]
    assert EvidenceRole.VIBRATION in contract["required_roles"]


def test_parse_evidence_contract_pressure_temperature_trip():
    acquirer = RCAEvidenceAcquirer(allow_simulation=True)

    query = "Why did K-101 trip on discharge overpressure and high bearing temperature?"
    contract = acquirer.parse_evidence_contract(query)

    assert "K-101" in contract["assets"]
    assert EvidenceRole.PRESSURE in contract["required_roles"]
    assert EvidenceRole.TEMPERATURE in contract["required_roles"]
    assert EvidenceRole.INCIDENT_CHRONOLOGY in contract["required_roles"]


@pytest.mark.asyncio
async def test_verify_asset_registration_known_asset():
    acquirer = RCAEvidenceAcquirer(allow_simulation=True)
    db_mock = AsyncMock()

    # P-101A is in SUPPORTED_SIMULATED_TARGETS
    is_registered = await acquirer.verify_asset_registration(workspace_id=1, asset_id="P-101A", db=db_mock)
    assert is_registered is True


@pytest.mark.asyncio
async def test_verify_asset_registration_unknown_asset_fails_closed():
    acquirer = RCAEvidenceAcquirer(allow_simulation=True)
    db_mock = AsyncMock()

    # Simulate DB queries returning None for nonexistent K-888
    cursor_mock = AsyncMock()
    cursor_mock.fetchone.return_value = None
    db_mock.execute.return_value = cursor_mock

    is_registered = await acquirer.verify_asset_registration(workspace_id=1, asset_id="K-888", db=db_mock)
    assert is_registered is False


@pytest.mark.asyncio
async def test_acquire_evidence_triggers_ood_on_unregistered_asset():
    acquirer = RCAEvidenceAcquirer(allow_simulation=True)
    db_mock = AsyncMock()

    cursor_mock = AsyncMock()
    cursor_mock.fetchone.return_value = None
    db_mock.execute.return_value = cursor_mock

    bundle = await acquirer.acquire_evidence(workspace_id=1, query="Why did compressor K-888 trip?", db=db_mock)

    assert bundle.retrieval_diagnostics.get("ood_triggered") is True
    assert "K-888" in bundle.retrieval_diagnostics.get("unregistered_assets", [])
    assert len(bundle.evidence_items) == 0
