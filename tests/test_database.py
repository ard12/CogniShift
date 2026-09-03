import pytest
import os
import tempfile
from pathlib import Path
import json

# Setup mock for config settings before importing app modules
@pytest.fixture(autouse=True)
def mock_db_path(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix='.sqlite3', delete=False) as f:
        db_path = Path(f.name)
    
    # We patch settings so the database code uses this temp DB
    from cognishift.app.config import settings
    monkeypatch.setattr(settings, 'database_path', db_path)
    
    yield db_path
    
    if db_path.exists():
        os.remove(db_path)

@pytest.mark.asyncio
async def test_init_db(mock_db_path):
    from cognishift.app.db.database import init_db, get_db
    await init_db()
    async with get_db() as db:
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row['name'] for row in await cursor.fetchall()]
        expected_tables = ['workspaces', 'agent_definitions', 'knowledge_sources', 'tool_definitions', 'agent_runs', 'run_events', 'approval_requests', 'audit_events']
        for table in expected_tables:
            assert table in tables

@pytest.mark.asyncio
async def test_create_workspace(mock_db_path):
    from cognishift.app.db.database import init_db, get_db
    await init_db()
    async with get_db() as db:
        await db.execute("INSERT INTO workspaces (name) VALUES ('Test Workspace')")
        await db.commit()
        
        cursor = await db.execute("SELECT * FROM workspaces WHERE name='Test Workspace'")
        row = await cursor.fetchone()
        assert row is not None
        assert row['name'] == 'Test Workspace'

@pytest.mark.asyncio
async def test_create_agent(mock_db_path):
    from cognishift.app.db.database import init_db, get_db
    await init_db()
    async with get_db() as db:
        await db.execute("INSERT INTO workspaces (id, name) VALUES (1, 'Test Workspace')")
        await db.execute("INSERT INTO agent_definitions (workspace_id, name, allowed_tool_ids) VALUES (1, 'Test Agent', '[1, 2]')")
        await db.commit()
        
        cursor = await db.execute("SELECT * FROM agent_definitions WHERE name='Test Agent'")
        row = await cursor.fetchone()
        assert row is not None
        assert row['name'] == 'Test Agent'
        assert json.loads(row['allowed_tool_ids']) == [1, 2]

@pytest.mark.asyncio
async def test_seed_data(mock_db_path):
    from scripts.seed import seed_data
    from cognishift.app.db.database import get_db
    
    await seed_data()
    
    async with get_db() as db:
        # Verify workspaces
        cursor = await db.execute("SELECT COUNT(*) as count FROM workspaces")
        row = await cursor.fetchone()
        assert row['count'] == 1
        
        # Verify agents
        cursor = await db.execute("SELECT COUNT(*) as count FROM agent_definitions")
        row = await cursor.fetchone()
        assert row['count'] == 2
        
        # Verify tools
        cursor = await db.execute("SELECT COUNT(*) as count FROM tool_definitions")
        row = await cursor.fetchone()
        assert row['count'] == 14
