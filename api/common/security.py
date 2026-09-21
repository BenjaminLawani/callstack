import random
from typing import Annotated
from jwt import (
    encode,
    decode,
    PyJWTError
)

from datetime import (
    datetime,
    timedelta,
    UTC
)

from sqlalchemy.orm import Session

from fastapi import (
    Depends,
    HTTPException,
    Request,
    status
)

from fastapi.security import OAuth2PasswordBearer
from .config import settings

from .db import get_db

from argon2 import PasswordHasher
from argon2.exceptions import (
    VerifyMismatchError,
    VerificationError,
    InvalidHashError
)

from api.auth.models import User

ph = PasswordHasher()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def normalize_email(email: str) -> str:
    return email.strip().lower()

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False

def jwt_encode(data: dict) -> str:
    return encode(
        data,
        key=settings.JWT_KEY,
        algorithm="HS256"
    )

def jwt_decode(token: str) -> dict:
    return decode(
        token,
        settings.JWT_KEY,
        algorithms=["HS256"]
    )

def generate_otp() -> int:
    return random.randint(100000, 999999)

def create_access_token(data: dict):
    to_encode = data.copy()
    to_encode.setdefault("type", "access")
    expires = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRES)
    to_encode.update({"exp": expires})
    encoded = jwt_encode(to_encode)
    return encoded

def create_refresh_token(data: dict):
    to_encode = data.copy()
    to_encode.setdefault("type", "refresh")
    expires = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRES)
    to_encode.update({"exp": expires})
    encoded = jwt_encode(to_encode)
    return encoded

def issue_token_pair(user_id: str, email: str) -> dict:
    access_token = create_access_token({"sub": user_id, "email": email})
    refresh_token = create_refresh_token({"sub": user_id, "email": email})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
    }

def get_current_user(
        token: str = Depends(oauth2_scheme), 
        db: Session = Depends(get_db)
    ):

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}    
        )
    try:
        payload = jwt_decode(token)
        user_id : str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception
    user = db.query(User).filter((User.id) == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_418_IM_A_TEAPOT
        )
    return user

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]