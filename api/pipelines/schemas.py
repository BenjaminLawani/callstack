from datetime import datetime
from typing import (
    Optional,
    List
)

from pydantic import (
    BaseModel,
    UUID4,
    ConfigDict,
)

from api.common.enums import PipelineNodeType

class PipelineNodeCreate(BaseModel):
    node_type: PipelineNodeType

class PipelineNodeCreateResponse(BaseModel):
    id: UUID4
    pipeline_id: UUID4
    node_type: PipelineNodeType
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class PipelineNodeResponse(BaseModel):
    id: UUID4
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