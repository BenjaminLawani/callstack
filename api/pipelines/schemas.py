from datetime import datetime
from typing import Optional

from pydantic import (
    BaseModel,
    UUID4,
    ConfigDict,
)

class PipelineResponse(BaseModel):
    id: UUID4
    project_id: UUID4
    name: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
