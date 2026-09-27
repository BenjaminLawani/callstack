from datetime import datetime
from typing import (
    Optional,
    List
)

from pydantic import (
    BaseModel,
    UUID4,
    ConfigDict,
    Field,
)

from api.common.enums import PipelineNodeType, RunStatus

class PipelineNodeCreate(BaseModel):
    name: str
    node_type: PipelineNodeType
    config: dict

class PipelineNodeCreateResponse(BaseModel):
    id: UUID4
    pipeline_id: UUID4
    name: str
    config: dict
    node_type: PipelineNodeType
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class PipelineNodeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=16)
    config: Optional[dict] = None

class PipelineNodeResponse(BaseModel):
    id: UUID4
    name: str
    config: dict
    node_type: PipelineNodeType
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ListPipelineNodeResponse(BaseModel):
    nodes: List[PipelineNodeResponse]

class PipelineCreate(BaseModel):
    name: str

class PipelineResponse(BaseModel):
    id: UUID4
    project_id: UUID4
    name: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ListPipelineResponse(BaseModel):
    pipelines: List[PipelineResponse]

class PipelineRunResponse(BaseModel):
    id: UUID4
    pipeline_id: UUID4
    status: RunStatus
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    output: Optional[str] = None
    node_results: List[dict]
    error: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ListPipelineRunResponse(BaseModel):
    runs: List[PipelineRunResponse]