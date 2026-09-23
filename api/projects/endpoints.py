from uuid import UUID
from datetime import (
    datetime,
    UTC
)
from sqlalchemy.orm import selectinload
import random
from sqlalchemy.exc import IntegrityError
from slugify import slugify
from fastapi import (
    APIRouter,
    status,
    Depends,
    HTTPException,
    Request
)
from .models import Project
from .schemas import (
    ProjectCreateRessponse,
    ProjectCreate,
    ProjectRessponse,
    ProjectUpdateRequest,
    ListProjectResponse,
    ProjectDetailResponse,
    AvatarUploadRequest,
    AvatarUploadResponse,
)

from api.common.security import (
    CurrentUser,
    DbSession,
)

from api.common.storage import create_image_upload

from api.common.exceptions import (
    InternalServerErrorException,
    InvalidCredentialsException,
    ResourceConflictEzception,
    ResourceNotFoundException
)

project_router = APIRouter(
    prefix="/projects",
    tags=["PROJECTS"]
)

@project_router.post("/", response_model=ProjectCreateRessponse)
def create_project(
    request: Request,
    data: ProjectCreate,
    db: DbSession,
    user: CurrentUser,
):
    slug = slugify(data.name)
    try:
        new_project = Project(**data.model_dump(exclude_unset=True))
        new_project.slug = f"{slug}{random.randint(100000, 999999)}"
        new_project.user_id = user.id
        db.add(new_project)
        db.commit()
        db.refresh(new_project)

        return ProjectCreateRessponse.model_validate(new_project)
    except IntegrityError as e:
        raise ResourceConflictEzception(f"{e}")
    except Exception as e:
        raise InternalServerErrorException()

@project_router.get("/", response_model=ListProjectResponse)
def list_user_projects(
    request: Request,
    db: DbSession,
    user: CurrentUser
):
    projects = db.query(Project).filter(Project.user_id == user.id, Project.deleted_at.is_(None)).all()
    return {
        "projects": projects
    }

@project_router.delete("/{id}", response_model=dict)
def delete_a_project(
    request: Request,
    id: UUID,
    db: DbSession,
    user: CurrentUser
):
    try:
        project = (
            db.query(Project)
            .filter(
                Project.id == id,
                Project.user_id == user.id,
                Project.deleted_at.is_(None)
            )
            .one_or_none()
        )

        if not project:
            raise ResourceNotFoundException("Project")

        project.deleted_at = datetime.now(UTC)

        db.commit()

        return {
            "message": f"{project.name} has been deleted"
        }
    
    except Exception:
        db.rollback()
        raise

@project_router.get("/{id}", response_model=ProjectDetailResponse)
def get_project_details(
    request: Request,
    id: UUID,
    db: DbSession,
    user: CurrentUser
):
    project = (
        db.query(Project)
        .options(selectinload(Project.pipelines))
        .filter(
            Project.id == id,
            Project.user_id == user.id,
            Project.deleted_at.is_(None)
        )
        .one_or_none()
    )
    if not project:
        raise ResourceNotFoundException("project")
    return {
        "project": project,
        "pipelines": [p for p in project.pipelines if p.deleted_at is None],
    }

@project_router.patch("/{id}", response_model=dict)
def update_project_details(
    request: Request,
    data: ProjectUpdateRequest,
    id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    project = (
        db.query(Project)
        .filter(
            Project.id == id,
            Project.user_id == user.id,
            Project.deleted_at.is_(None),
        )
        .one_or_none()
    )
    if not project:
        raise ResourceNotFoundException("Project")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(project, key, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ResourceConflictEzception("Project")
    db.refresh(project)

    return {"message": "Project updated"}


@project_router.post("/{id}/avatar", response_model=AvatarUploadResponse)
def create_project_avatar_upload_url(
    request: Request,
    data: AvatarUploadRequest,
    id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    # Record the avatar URL and hand back a presigned PUT URL; the browser
    # uploads the file straight to R2 with it.
    project = (
        db.query(Project)
        .filter(
            Project.id == id,
            Project.user_id == user.id,
            Project.deleted_at.is_(None),
        )
        .one_or_none()
    )
    if not project:
        raise ResourceNotFoundException("Project")

    upload = create_image_upload(data.content_type, folder="projects")
    project.avatar_url = upload["public_url"]

    db.commit()
    db.refresh(project)

    return AvatarUploadResponse(
        upload_url=upload["upload_url"],
        avatar_url=project.avatar_url,
        expires_in=upload["expires_in"],
    )