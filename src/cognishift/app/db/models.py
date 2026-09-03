from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from datetime import datetime

class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    operating_mode: str = 'local'

class WorkspaceResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    operating_mode: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AgentCreate(BaseModel):
    workspace_id: int
    name: str
    description: Optional[str] = None
    system_instructions: Optional[str] = None
    model_name: str = 'llama3.2:3b'
    allowed_tool_ids: List[int] = []
    approval_required: bool = False
    knowledge_source_ids: List[int] = []

class AgentResponse(BaseModel):
    id: int
    workspace_id: int
    name: str
    description: Optional[str] = None
    system_instructions: Optional[str] = None
    model_name: str
    status: str
    allowed_tool_ids: List[int]
    approval_required: bool
    knowledge_source_ids: List[int]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_instructions: Optional[str] = None
    model_name: Optional[str] = None
    allowed_tool_ids: Optional[List[int]] = None
    approval_required: Optional[bool] = None
    knowledge_source_ids: Optional[List[int]] = None
    status: Optional[str] = None

class ToolDefinitionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    risk_level: str = 'read_only'
    requires_approval: bool = False
    enabled: bool = True
    implementation_key: str
    input_schema: str = '{}'

class ToolDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    risk_level: Optional[str] = None
    requires_approval: Optional[bool] = None
    enabled: Optional[bool] = None
    implementation_key: Optional[str] = None
    input_schema: Optional[str] = None

class ToolDefinitionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    risk_level: str
    requires_approval: bool
    enabled: bool
    implementation_key: str
    input_schema: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class RunCreate(BaseModel):
    workspace_id: int
    agent_id: int
    input_text: Optional[str] = None
    input_type: str = 'text'
    input_image_path: Optional[str] = None
    user_id: str = 'operator'

class RunResponse(BaseModel):
    id: int
    workspace_id: int
    agent_id: int
    user_id: str
    input_text: Optional[str] = None
    input_type: str
    input_image_path: Optional[str] = None
    status: str
    model_name: Optional[str] = None
    operating_mode: Optional[str] = None
    result_text: Optional[str] = None
    sources_used: Optional[str] = None
    confidence: Optional[float] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class RunEventResponse(BaseModel):
    id: int
    run_id: int
    event_type: str
    message: Optional[str] = None
    structured_data: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ApprovalResponse(BaseModel):
    id: int
    run_id: int
    tool_id: int
    status: str
    request_reason: Optional[str] = None
    parameters: Optional[str] = None
    risk_level: Optional[str] = None
    requested_at: datetime
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class AuditEventResponse(BaseModel):
    id: int
    workspace_id: Optional[int] = None
    actor_id: str
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    details: Optional[str] = None
    result: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class KnowledgeSourceResponse(BaseModel):
    id: int
    workspace_id: int
    name: str
    source_type: str
    original_filename: Optional[str] = None
    local_path: Optional[str] = None
    processing_status: str
    checksum: Optional[str] = None
    chunk_count: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ArtifactResponse(BaseModel):
    id: int
    workspace_id: int
    run_id: Optional[int] = None
    filename: str
    relative_path: str
    artifact_type: str
    title: Optional[str] = None
    description: Optional[str] = None
    file_size: int
    sha256_hash: str
    metadata: Optional[str] = "{}"
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ArtifactListResponse(BaseModel):
    total: int
    artifacts: List[ArtifactResponse]
