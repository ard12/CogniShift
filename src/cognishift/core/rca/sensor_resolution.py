"""Plant Topology Instrument & Equipment Sensor Resolution Subsystem."""
import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from cognishift.app.db.database import get_db

logger = logging.getLogger(__name__)

# Authoritative refinery equipment-to-sensor topology registry
EQUIPMENT_SENSOR_REGISTRY: Dict[str, Dict[str, List[Dict[str, str]]]] = {
    "K-101": {
        "temperature": [
            {"sensor_id": "TT-204", "location": "drive_end", "description": "Outboard Journal Bearing Thermocouple (DE)"},
            {"sensor_id": "TT-205", "location": "non_drive_end", "description": "Inboard Journal Bearing Thermocouple (NDE)"},
        ],
        "vibration": [
            {"sensor_id": "VT-101-DE", "location": "drive_end", "description": "Drive End Radial Vibration Probe"},
            {"sensor_id": "VT-101-NDE", "location": "non_drive_end", "description": "Non-Drive End Radial Vibration Probe"},
        ],
        "pressure": [
            {"sensor_id": "PT-100", "location": "suction", "description": "Suction Pressure Transmitter"},
            {"sensor_id": "PT-102", "location": "discharge", "description": "Discharge Pressure Transmitter"},
        ]
    },
    "P-101A": {
        "pressure": [
            {"sensor_id": "PT-101", "location": "discharge", "description": "Discharge Header Pressure Transmitter"},
            {"sensor_id": "PT-101-SUC", "location": "suction", "description": "Suction Manifold Pressure Transmitter"},
        ],
        "vibration": [
            {"sensor_id": "VT-201", "location": "drive_end", "description": "DE Bearing Vibration Sensor"},
        ],
        "temperature": [
            {"sensor_id": "TT-101", "location": "bearing", "description": "Pump Bearing Housing Temperature"},
        ]
    },
    "P-101B": {
        "pressure": [
            {"sensor_id": "PT-101B", "location": "discharge", "description": "Pump B Discharge Pressure Transmitter"},
        ],
        "vibration": [
            {"sensor_id": "VT-202", "location": "drive_end", "description": "Pump B DE Bearing Vibration Sensor"},
        ]
    },
    "REACTOR-B": {
        "pressure": [
            {"sensor_id": "PT-101", "location": "vessel", "description": "Reactor Vessel Pressure Transmitter"},
        ],
        "temperature": [
            {"sensor_id": "TT-301", "location": "bed_inlet", "description": "Catalyst Bed Inlet Thermocouple"},
        ]
    }
}


async def resolve_sensor_for_equipment(
    workspace_id: int,
    equipment_id: str,
    measurement_type: str,
    location_hint: Optional[str] = None,
    db: Optional[Any] = None,
    return_source: bool = False
) -> Any:
    """
    Authoritative resolution of equipment (e.g. K-101, P-101A) to valid sensor IDs.
    Does NOT blindly convert equipment IDs into sensor IDs.
    
    Resolution Priority:
      1. Workspace topology / asset graph (graph_nodes and graph_edges) -> 'TOPOLOGY'
      2. Authoritative local plant registry (EQUIPMENT_SENSOR_REGISTRY) -> 'PLANT_REGISTRY'
      3. Prototype static mapping fallback -> 'STATIC_PROTOTYPE'
    
    Returns:
        sensor_id (str) if an unambiguous sensor is resolved (or (sensor_id, source) if return_source=True).
        None if zero sensors exist or if multiple exist without a clarifying location hint.
    """
    if not equipment_id:
        return (None, "NONE") if return_source else None

    clean_eq = equipment_id.strip().upper()
    clean_meas = measurement_type.strip().lower()
    clean_loc = (location_hint or "").strip().lower()
    resolution_source = "NONE"
    resolved_sensor = None

    # 1. Priority 1: Query Workspace Knowledge Graph (Topology Authority)
    try:
        if db is None:
            async with get_db() as conn:
                graph_sensor = await _query_graph_sensors(conn, workspace_id, clean_eq, clean_meas, clean_loc)
        else:
            graph_sensor = await _query_graph_sensors(db, workspace_id, clean_eq, clean_meas, clean_loc)
        
        if graph_sensor:
            resolved_sensor = graph_sensor
            resolution_source = "TOPOLOGY"
            logger.info(f"Resolved sensor for {clean_eq} ({clean_meas}): {resolved_sensor} [Source: TOPOLOGY]")
            return (resolved_sensor, resolution_source) if return_source else resolved_sensor
    except Exception as e:
        logger.warning(f"Error querying graph sensors for {clean_eq}: {e}")

    # 2. Priority 2: Authoritative Local Plant Registry
    if clean_eq in EQUIPMENT_SENSOR_REGISTRY:
        meas_map = EQUIPMENT_SENSOR_REGISTRY[clean_eq]
        sensors = meas_map.get(clean_meas, [])
        if len(sensors) == 1:
            resolved_sensor = sensors[0]["sensor_id"]
            resolution_source = "PLANT_REGISTRY"
        elif len(sensors) > 1:
            if clean_loc:
                for s in sensors:
                    if clean_loc in s["location"] or clean_loc in s["description"].lower():
                        resolved_sensor = s["sensor_id"]
                        resolution_source = "PLANT_REGISTRY"
                        break
                    if clean_loc in ("de", "drive end", "outboard") and s["location"] == "drive_end":
                        resolved_sensor = s["sensor_id"]
                        resolution_source = "PLANT_REGISTRY"
                        break
                    if clean_loc in ("nde", "non drive end", "inboard") and s["location"] == "non_drive_end":
                        resolved_sensor = s["sensor_id"]
                        resolution_source = "PLANT_REGISTRY"
                        break
                    if clean_loc in ("suction", "inlet") and s["location"] == "suction":
                        resolved_sensor = s["sensor_id"]
                        resolution_source = "PLANT_REGISTRY"
                        break
                    if clean_loc in ("discharge", "outlet") and s["location"] == "discharge":
                        resolved_sensor = s["sensor_id"]
                        resolution_source = "PLANT_REGISTRY"
                        break
            if resolved_sensor is None:
                logger.info(f"Ambiguous sensors for {clean_eq} ({clean_meas}) in registry without matching location hint")

    if resolved_sensor:
        logger.info(f"Resolved sensor for {clean_eq} ({clean_meas}): {resolved_sensor} [Source: {resolution_source}]")
        return (resolved_sensor, resolution_source) if return_source else resolved_sensor

    logger.warning(f"Unable to resolve sensor for {clean_eq} ({clean_meas}) across topology and registry [Source: NONE]")
    return (None, "NONE") if return_source else None


async def _query_graph_sensors(
    db: Any,
    workspace_id: int,
    clean_eq: str,
    clean_meas: str,
    clean_loc: str
) -> Optional[str]:
    cursor = await db.execute(
        """
        SELECT n.name, n.entity_type, n.properties
        FROM graph_nodes n
        JOIN graph_edges e ON e.target_node_id = n.id
        JOIN graph_nodes src ON e.source_node_id = src.id
        WHERE e.workspace_id = ?
          AND UPPER(src.name) = ?
          AND e.relation_type IN ('HAS_SENSOR', 'MONITORED_BY', 'MEASURED_BY')
        """,
        (workspace_id, clean_eq)
    )
    rows = await cursor.fetchall()
    if not rows:
        return None

    type_prefixes = {
        "temperature": "TT-",
        "pressure": "PT-",
        "vibration": "VT-"
    }
    prefix = type_prefixes.get(clean_meas)

    matched = []
    for r in rows:
        name = r["name"]
        if prefix and name.upper().startswith(prefix):
            matched.append(name)
        elif clean_meas in str(r.get("properties", "")).lower():
            matched.append(name)

    if len(matched) == 1:
        return matched[0]
    elif len(matched) > 1 and clean_loc:
        for m in matched:
            if clean_loc in m.lower():
                return m
    return None
