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
            VALUES (1, 1, 'Maintenance Assistant', 'Assists with industrial equipment maintenance', 'System instructions for industrial equipment maintenance', 'llama3.2:3b', 1, '[]')
            ON CONFLICT DO NOTHING
        ''')
        
        await db.execute('''
            INSERT INTO agent_definitions (id, workspace_id, name, description, system_instructions, model_name, approval_required, allowed_tool_ids)
            VALUES (2, 1, 'IT Helpdesk Agent', 'Assists with IT support', 'System instructions for IT support', 'llama3.2:3b', 0, '[]')
            ON CONFLICT DO NOTHING
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

        await db.commit()
        print("Database seeded successfully.")

if __name__ == "__main__":
    asyncio.run(seed_data())
