from uuid import UUID
from sqlalchemy.exc import IntegrityError
from fastapi import (
    APIRouter,
    status,
    HTTPException,
    Depends,
    Request
)
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_sso.sso.base import SSOLoginError

from .schemas import (
    UserCreate,
    UserCreateResponse,
    UserProfileCreate,
    UserProfileResponse,
    UserProfileUpdate,
    PasswordUpdate,
    Token,
)

from .models import (
    User,
    UserProfile
)

from .sso import GoogleSSODep

from api.common.enums import LoginMethod

from api.common.exceptions import (
    InvalidCredentialsException,
    ResourceNotFoundException,
    ResourceConflictEzception,
    InternalServerErrorException
)

from api.common.security import (
    hash_password,
    verify_password,
    normalize_email,
    DbSession,
    CurrentUser,
    issue_token_pair
)

auth_router = APIRouter(
    prefix="/auth",
    tags=["AUTHENTICATION"]
)

profile_router = APIRouter(
    prefix="/profiles",
    tags=["PROFILES"]
)

@auth_router.post("/login", response_model=Token)
def login(
    request: Request,
    db: DbSession,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    email = normalize_email(form_data.username)
    db_user = db.query(User).filter(User.email == email).one_or_none()
    if (
        not db_user
        or not db_user.password
        or not verify_password(form_data.password, db_user.password)
    ):
        raise InvalidCredentialsException()
    tokens = issue_token_pair(str(db_user.id), db_user.email)
    return Token(**tokens)


@auth_router.get("/google-login")
async def google_login(sso: GoogleSSODep):
    async with sso:
        return await sso.get_login_redirect()

@auth_router.get("/google-callback", response_model=Token)
async def google_callback(
    request: Request,
    db: DbSession,
    sso: GoogleSSODep,
):
    try:
        async with sso:
            openid = await sso.verify_and_process(request)
    except SSOLoginError:
        raise InvalidCredentialsException()
    if openid is None or not openid.email:
        raise InvalidCredentialsException()
    
    email = normalize_email(openid.email)
    db_user = db.query(User).filter(User.email == email).one_or_none()
    if db_user is None:
        db_user = User(email=email, login_method=LoginMethod.GOOGLE)
        db.add(db_user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ResourceConflictEzception("User")
        db.refresh(db_user)

    tokens = issue_token_pair(str(db_user.id), db_user.email)
    return Token(**tokens)

@auth_router.post("/get-started", response_model=UserCreateResponse)
def get_started(
    request: Request,
    data: UserCreate,
    db: DbSession
):
    try:
        email = normalize_email(data.email)
        existing_user = db.query(User).filter(User.email == email).one_or_none()
        if existing_user:
            raise ResourceConflictEzception("User")
        new_user = User(
            email=email,
            password=hash_password(data.password),
            login_method=LoginMethod.LOCAL,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return UserCreateResponse.model_validate(new_user)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as e:
        db.rollback()
        raise ResourceConflictEzception(f"{e.orig}")
    except Exception as e:
        db.rollback()
        raise InternalServerErrorException()


@auth_router.get("/", response_model=UserCreateResponse)
def get_me(
    request: Request,
    db: DbSession,
    user: CurrentUser,
):
    return UserCreateResponse.model_validate(user)

@profile_router.post("/", response_model=UserProfileResponse)
def create_user_profile(
    request: Request,
    data: UserProfileCreate,
    db: DbSession,
    user: CurrentUser
):
    try:
        exising_profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).one_or_none()
        if exising_profile:
            raise ResourceConflictEzception("Profile")
        new_profile = UserProfile(**data.model_dump(exclude_unset=True))
        new_profile.user_id = user.id

        db.add(new_profile)
        db.commit()
        db.refresh(new_profile)

        return UserProfileResponse.model_validate(new_profile)
    except IntegrityError as e:
        db.rollback()
        raise ResourceConflictEzception(f"{e.orig}")
    except Exception as e:
        db.rollback()
        raise InternalServerErrorException()

@profile_router.get("/", response_model=UserProfileResponse)
def get_my_profile(
    request: Request,
    db: DbSession,
    user: CurrentUser
):
    profile = db.query(UserProfile).filter_by(user_id = user.id).one_or_none()
    if not profile:
        raise ResourceNotFoundException("Profile")
    return profile

@profile_router.patch("/", response_model=dict)
def update_profile(
    data: UserProfileUpdate,
    db: DbSession,
    user: CurrentUser,
):
    profile = (
        db.query(UserProfile)
        .filter_by(user_id=user.id)
        .one_or_none()
    ) 
    if not profile:
        raise ResourceNotFoundException("Profile")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)

    db.commit()
    db.refresh(profile)

    return {"message": "Profile updated"}

