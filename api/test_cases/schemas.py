from datetime import datetime
from pydantic import (
    BaseModel,
    UUID4,
    Field,
)
from typing import (
    List,
    Optional,
)

class TestCaseNodeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    assertions: dict

class TestCaseNodeCreateResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    test_case_id: UUID4
    name: str
    description: Optional[str] = None
    assertions: dict
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    should_fail: bool
    position: int
