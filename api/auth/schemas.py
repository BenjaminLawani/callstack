from datetime import datetime
from pydantic import (
    BaseModel,
    UUID4,
    Field,
    EmailStr,
    ConfigDict
)

from typing import (
    List,
    Optional,
)

from api.common.enums import LoginMethod

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

class UserCreateResponse(BaseModel):
    id: UUID4
    email: EmailStr
    created_at: datetime
    deleted_at: Optional[datetime] = None
    login_method: LoginMethod

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class UserProfileCreate(BaseModel):
    username: str
    preferences: Optional[dict] = None
    avatar_url: Optional[str] = None

class UserProfileResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    username: str
    preferences: Optional[dict] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UserProfileUpdate(BaseModel):
    preferences: Optional[dict] = None
    avatar_url: Optional[str] = None

class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str

