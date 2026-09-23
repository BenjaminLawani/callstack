from datetime import datetime
from pydantic import (
    BaseModel,
    Field,
    UUID4,
    ConfigDict
)
from typing import (
    List,
    Optional,
)

class ProjectCreate(BaseModel):
    name: str
    avatar_url: Optional[str] = None

class ProjectCreateRessponse(BaseModel):
    id: UUID4
    user_id: UUID4
    name: str
    slug: str
    avatar_url: Optional[str] = None
    created_at: datetime
    deleted_at: Optional[datetime] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None

class ProjectRessponse(BaseModel):
    id: UUID4
    name: str
    slug: str
    avatar_url: Optional[str] = None
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ListProjectResponse(BaseModel):
    projects: List[ProjectCreateRessponse]