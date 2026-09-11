"""Test suite for RCA Equipment Sensor Resolution Subsystem."""
import pytest
from cognishift.core.rca.sensor_resolution import (
    resolve_sensor_for_equipment,
    EQUIPMENT_SENSOR_REGISTRY,
)


def test_authoritative_equipment_sensor_registry_contents():
    assert "K-101" in EQUIPMENT_SENSOR_REGISTRY
    assert "P-101A" in EQUIPMENT_SENSOR_REGISTRY

    k101_sensors = EQUIPMENT_SENSOR_REGISTRY["K-101"]
    sensor_ids = [s["sensor_id"] for s in k101_sensors["temperature"]]
    assert "TT-204" in sensor_ids
    assert "TT-205" in sensor_ids

    p_sensor_ids = [s["sensor_id"] for s in k101_sensors["pressure"]]
    assert "PT-100" in p_sensor_ids
    assert "PT-102" in p_sensor_ids

    p101a_sensors = EQUIPMENT_SENSOR_REGISTRY["P-101A"]
    p101a_p_ids = [s["sensor_id"] for s in p101a_sensors["pressure"]]
    assert "PT-101" in p101a_p_ids
    assert "PT-101-SUC" in p101a_p_ids


@pytest.mark.asyncio
async def test_resolve_sensor_unambiguous():
    # P-101A has single vibration sensor VT-201
    sensor = await resolve_sensor_for_equipment(workspace_id=1, equipment_id="P-101A", measurement_type="vibration")
    assert sensor == "VT-201"

    # P-101A has single temperature sensor TT-101
    temp_sensor = await resolve_sensor_for_equipment(workspace_id=1, equipment_id="P-101A", measurement_type="temperature")
    assert temp_sensor == "TT-101"


@pytest.mark.asyncio
async def test_resolve_sensor_with_location_hint():
    # K-101 has two temperature sensors; location_hint resolves ambiguity
    de_sensor = await resolve_sensor_for_equipment(
        workspace_id=1, equipment_id="K-101", measurement_type="temperature", location_hint="drive_end"
    )
    assert de_sensor == "TT-204"

    nde_sensor = await resolve_sensor_for_equipment(
        workspace_id=1, equipment_id="K-101", measurement_type="temperature", location_hint="non_drive_end"
    )
    assert nde_sensor == "TT-205"

    # K-101 suction pressure
    suc_sensor = await resolve_sensor_for_equipment(
        workspace_id=1, equipment_id="K-101", measurement_type="pressure", location_hint="suction"
    )
    assert suc_sensor == "PT-100"


@pytest.mark.asyncio
async def test_resolve_sensor_ambiguous_without_hint_fails_safe():
    # Ambiguous resolution with multiple sensors and no location hint returns None
    sensor = await resolve_sensor_for_equipment(workspace_id=1, equipment_id="K-101", measurement_type="temperature")
    assert sensor is None


@pytest.mark.asyncio
async def test_resolve_sensor_unregistered_equipment_fails_safe():
    sensor = await resolve_sensor_for_equipment(workspace_id=1, equipment_id="NONEXISTENT-999", measurement_type="temperature")
    assert sensor is None
