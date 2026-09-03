import asyncio
import json
from cognishift.app.db.database import init_db, get_db

async def seed_data():
    """Seed the database with initial data."""
    await init_db()
    
    async with get_db() as db:
        # Seed Workspace
        await db.execute('''
            INSERT INTO workspaces (id, name, description, operating_mode)
            VALUES (1, 'MRPL Refinery Operations', 'Mangalore Refinery and Petrochemicals Limited - Industrial Operations Workspace', 'local')
            ON CONFLICT DO NOTHING
        ''')
        
        # Seed Agents
        await db.execute('''
            INSERT INTO agent_definitions (id, workspace_id, name, description, system_instructions, model_name, approval_required, allowed_tool_ids)
            VALUES (1, 1, 'Maintenance Assistant', 'Assists with industrial equipment maintenance', 'System instructions for industrial equipment maintenance', 'llama3.2:3b', 0, '[1, 2, 3, 4, 5]')
            ON CONFLICT(id) DO UPDATE SET allowed_tool_ids = excluded.allowed_tool_ids, approval_required = excluded.approval_required
        ''')
        
        await db.execute('''
            INSERT INTO agent_definitions (id, workspace_id, name, description, system_instructions, model_name, approval_required, allowed_tool_ids)
            VALUES (2, 1, 'IT Helpdesk Agent', 'Assists with IT support', 'System instructions for IT support', 'llama3.2:3b', 0, '[6, 7]')
            ON CONFLICT(id) DO UPDATE SET allowed_tool_ids = excluded.allowed_tool_ids, approval_required = excluded.approval_required
        ''')
        
        # Seed Tools
        tools = [
            (1, 'check_pressure', 'Check Pressure Reading', 'read_only', 0, 'check_pressure'),
            (2, 'check_temperature', 'Check Temperature Reading', 'read_only', 0, 'check_temperature'),
            (3, 'run_diagnostic', 'Run Equipment Diagnostic', 'low_risk', 0, 'run_diagnostic'),
            (4, 'emergency_pressure_relief', 'Emergency Pressure Relief', 'service_interrupting', 1, 'emergency_pressure_relief'),
            (5, 'restart_component', 'Restart System Component', 'sensitive', 1, 'restart_component'),
            (6, 'check_network', 'Check Network Status', 'read_only', 0, 'check_network'),
            (7, 'restart_service', 'Restart Network Service', 'low_risk', 1, 'restart_service')
        ]
        
        for t in tools:
            await db.execute('''
                INSERT INTO tool_definitions (id, name, description, risk_level, requires_approval, implementation_key)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO NOTHING
            ''', t)

        # Seed Plant Topology Graph Memory (MRPL Unit 1)
        nodes = [
            (1, "Pump-101A", "equipment", '{"role": "Crude Feed Pump", "standard": "API 610", "type": "Centrifugal"}'),
            (1, "PT-101", "sensor", '{"role": "Pressure Transmitter", "normal_min": 80, "normal_max": 120, "critical_high": 450, "unit": "PSI"}'),
            (1, "TT-204", "sensor", '{"role": "Thermocouple Temperature", "normal_min": 60, "normal_max": 85, "trip_threshold": 95.0, "unit": "C"}'),
            (1, "Reactor-B", "equipment", '{"role": "Catalytic Hydrotreater", "design_pressure": 500, "design_temp": 450}'),
            (1, "SV-402", "valve", '{"role": "Emergency Pressure Safety Valve", "set_pressure": 450, "flange": "4-inch ANSI 600#"}'),
            (1, "Flare-Header", "equipment", '{"role": "High-Pressure Acid Gas Flare Header", "destination": "Thermal Oxidizer"}'),
            (1, "SCADA-Gateway-01", "equipment", '{"role": "Telemetry Gateway", "ip": "192.168.40.10", "vlan": 40}'),
            (1, "telemetry-bridge", "service", '{"role": "Modbus Collector Service", "port": 502, "protocol": "Modbus/TCP"}')
        ]
        for n in nodes:
            await db.execute('''
                INSERT INTO graph_nodes (workspace_id, name, entity_type, properties)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(workspace_id, name) DO UPDATE SET
                    entity_type = excluded.entity_type,
                    properties = excluded.properties
            ''', n)

        # Edges
        # Fetch node IDs by name
        cursor = await db.execute("SELECT id, name FROM graph_nodes WHERE workspace_id = 1")
        node_ids = {r["name"]: r["id"] for r in await cursor.fetchall()}

        edges = [
            ("Pump-101A", "HAS_SENSOR", "PT-101", '{"location": "Discharge Flange"}'),
            ("Pump-101A", "HAS_SENSOR", "TT-204", '{"location": "Inboard Bearing Housing"}'),
            ("Pump-101A", "FEEDS_INTO", "Reactor-B", '{"pipe_line": "12-CDU-401-HC"}'),
            ("Reactor-B", "HAS_SENSOR", "PT-101", '{"purpose": "Inlet Overpressure Monitoring"}'),
            ("Reactor-B", "PROTECTED_BY", "SV-402", '{"trip_condition": "P > 450 PSI"}'),
            ("SV-402", "DISCHARGES_TO", "Flare-Header", '{"flow_type": "Emergency Blowdown"}'),
            ("SCADA-Gateway-01", "RUNS_SERVICE", "telemetry-bridge", '{"daemon": "systemd"}')
        ]

        for src, rel, tgt, props in edges:
            src_id = node_ids.get(src)
            tgt_id = node_ids.get(tgt)
            if src_id and tgt_id:
                # Check if edge already exists
                c = await db.execute(
                    "SELECT id FROM graph_edges WHERE workspace_id = 1 AND source_node_id = ? AND relation_type = ? AND target_node_id = ?",
                    (src_id, rel, tgt_id)
                )
                if not await c.fetchone():
                    await db.execute(
                        "INSERT INTO graph_edges (workspace_id, source_node_id, relation_type, target_node_id, properties) VALUES (1, ?, ?, ?, ?)",
                        (src_id, rel, tgt_id, props)
                    )

        await db.commit()
        print("Database & Plant Topology Graph Memory seeded successfully.")

if __name__ == "__main__":
    asyncio.run(seed_data())
