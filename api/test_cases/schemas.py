from datetime import datetime
from pydantic import (
    BaseModel,
    UUID4,
    Field,
    ConfigDict
)
from typing import (
    List,
    Optional,
)

from api.common.enums import RunStatus

class TestCaseNodeCreate(BaseModel):
    name: str = Field(max_length=16)
    description: Optional[str] = Field(default=None, max_length=32)
    assertions: dict
    should_fail: bool = False

class TestCaseNodeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=16)
    description: Optional[str] = Field(default=None, max_length=32)
    assertions: Optional[dict] = None
    should_fail: Optional[bool] = None
    position: Optional[int] = None

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

    model_config = ConfigDict(from_attributes=True)

class TestCaseNodeResponse(BaseModel):
    id: UUID4
    test_case_id: UUID4
    name: str
    description: Optional[str] = None
    assertions: dict
    should_fail: bool
    position: int

    model_config = ConfigDict(from_attributes=True)

class TestCaseCreate(BaseModel):
    name: str = Field(max_length=32)

class TestCaseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=32)

class TestCaseResponse(BaseModel):
    id: UUID4
    name: str
    pipeline_id: UUID4
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class TestCaseDetailResponse(TestCaseResponse):
    nodes: List[TestCaseNodeResponse]

class ListTestCaseResponse(BaseModel):
    test_cases: List[TestCaseResponse]

class ListTestCaseNodes(BaseModel):
    nodes: List[TestCaseNodeResponse]

class TestCaseRunResponse(BaseModel):
    id: UUID4
    test_case_id: UUID4
    pipeline_run_id: Optional[UUID4] = None
    status: RunStatus
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    output: Optional[str] = None
    results: List[dict]
    error: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ListTestCaseRunResponse(BaseModel):
    runs: List[TestCaseRunResponse]
