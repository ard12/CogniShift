import json
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from cognishift.app.db.database import get_db
from cognishift.app.db.models import AgentCreate, AgentResponse, AgentUpdate

router = APIRouter(prefix='/api/v1/agents', tags=['Agents'])

def row_to_agent(row) -> dict:
    d = dict(row)
    if 'allowed_tool_ids' in d and isinstance(d['allowed_tool_ids'], str):
        try:
            d['allowed_tool_ids'] = json.loads(d['allowed_tool_ids'])
        except json.JSONDecodeError:
            d['allowed_tool_ids'] = []
    if 'knowledge_source_ids' in d and isinstance(d['knowledge_source_ids'], str):
        try:
            d['knowledge_source_ids'] = json.loads(d['knowledge_source_ids'])
        except json.JSONDecodeError:
            d['knowledge_source_ids'] = []
    d['approval_required'] = bool(d.get('approval_required', 0))
    return d

@router.post('', response_model=AgentResponse)
async def create_agent(agent: AgentCreate):
    """Create a new agent definition."""
    allowed_tools_json = json.dumps(agent.allowed_tool_ids)
    knowledge_sources_json = json.dumps(agent.knowledge_source_ids)
    async with get_db() as db:
        cursor = await db.execute(
            '''INSERT INTO agent_definitions 
               (workspace_id, name, description, system_instructions, model_name, allowed_tool_ids, approval_required, knowledge_source_ids)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING *''',
            (agent.workspace_id, agent.name, agent.description, agent.system_instructions, 
             agent.model_name, allowed_tools_json, int(agent.approval_required), knowledge_sources_json)
        )
        row = await cursor.fetchone()
        await db.commit()
        return row_to_agent(row)

@router.get('', response_model=List[AgentResponse])
async def list_agents(workspace_id: Optional[int] = Query(None)):
    """List all agents, optionally filtered by workspace_id."""
    async with get_db() as db:
        if workspace_id is not None:
            cursor = await db.execute('SELECT * FROM agent_definitions WHERE workspace_id = ?', (workspace_id,))
        else:
            cursor = await db.execute('SELECT * FROM agent_definitions')
        rows = await cursor.fetchall()
        return [row_to_agent(row) for row in rows]

@router.get('/{agent_id}', response_model=AgentResponse)
async def get_agent(agent_id: int):
    """Get a specific agent by ID."""
    async with get_db() as db:
        cursor = await db.execute('SELECT * FROM agent_definitions WHERE id = ?', (agent_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Agent not found')
        return row_to_agent(row)

@router.patch('/{agent_id}', response_model=AgentResponse)
async def update_agent(agent_id: int, agent: AgentUpdate):
    """Update agent fields."""
    update_data = agent.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    if 'allowed_tool_ids' in update_data:
        update_data['allowed_tool_ids'] = json.dumps(update_data['allowed_tool_ids'])
    if 'knowledge_source_ids' in update_data:
        update_data['knowledge_source_ids'] = json.dumps(update_data['knowledge_source_ids'])
    if 'approval_required' in update_data:
        update_data['approval_required'] = int(update_data['approval_required'])

    set_clauses = []
    values = []
    for k, v in update_data.items():
        set_clauses.append(f"{k} = ?")
        values.append(v)
    
    values.append(agent_id)
    query = f"UPDATE agent_definitions SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP WHERE id = ? RETURNING *"
    
    async with get_db() as db:
        cursor = await db.execute(query, tuple(values))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Agent not found')
        await db.commit()
        return row_to_agent(row)
