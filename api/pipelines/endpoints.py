import time
import asyncio
import httpx
from uuid import UUID
from datetime import datetime, UTC
from sqlalchemy.exc import IntegrityError
from fastapi import (
    APIRouter,
    Depends,
    status,
    HTTPException,
    Request,
    Query
)

from .models import (
    Pipeline,
    PipelineNode,
    PipelineRuns,
)

from .executor import run_pipeline

from .schemas import (
    PipelineResponse,
    PipelineNodeResponse,
    PipelineCreate,
    PipelineNodeCreate,
    PipelineNodeCreateResponse,
    PipelineNodeUpdate,
    ListPipelineNodeResponse,
    ListPipelineResponse,
    PipelineRunResponse,
    ListPipelineRunResponse,
)

from api.common.security import (
    DbSession,
    CurrentUser,
)

from api.common.enums import PipelineNodeType
from api.common.storage import *
from api.common.transcription import VOICE_MODELS
from api.common.exceptions import (
    InternalServerErrorException,
    ResourceConflictEzception,
    ResourceNotFoundException
)

runs_router = APIRouter(
    prefix="/runs",
    tags=["RUNS"]
)

pipeline_router = APIRouter(
    prefix="/pipelines",
    tags=["PIPELINES"]
)

node_router = APIRouter(
    prefix="/nodes",
    tags=["PIPELINE NODES"]
)

model_router = APIRouter(
    prefix="/models",
    tags=["MODELS"]
)


_MODELS_URL = "https://llm-gateway.assemblyai.com/v1/models"
_MODELS_TTL = 300  # seconds
_models_cache = {"data": None, "at": 0.0}
_models_lock = asyncio.Lock()


async def _get_models_cached():
    def fresh():
        return (
            _models_cache["data"] is not None
            and (time.monotonic() - _models_cache["at"]) < _MODELS_TTL
        )

    if fresh():
        return _models_cache["data"]

    async with _models_lock:
        if fresh():  # another request may have refreshed while we waited
            return _models_cache["data"]
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(_MODELS_URL)
                response.raise_for_status()
            _models_cache["data"] = response.json()["data"]
            _models_cache["at"] = time.monotonic()
        except Exception:
            if _models_cache["data"] is not None:
                return _models_cache["data"]  # serve stale rather than fail
            raise
        return _models_cache["data"]


def _get_owned_pipeline(db, pipeline_id: UUID, user):
    pipeline = (
        db.query(Pipeline)
        .filter(
            Pipeline.id == pipeline_id,
            Pipeline.user_id == user.id,
            Pipeline.deleted_at.is_(None),
        )
        .one_or_none()
    )
    if not pipeline:
        raise ResourceNotFoundException("Pipeline")
    return pipeline


@model_router.get("/")
async def get_models(
    request: Request,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    models = await _get_models_cached()

    total = len(models)
    start = (page - 1) * limit
    end = start + limit

    paginated_models = models[start:end]

    return {
        "data": [
            {
                "name": model["name"],
                "context_length": model["context_length"],
                "price": {
                    "input": model["pricing"]["global"]["prompt"],
                    "output": model["pricing"]["global"]["completions"],
                },
                "available_regions": model["available_regions"],
            }
            for model in paginated_models
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
        },
    }


@model_router.get("/voice")
def get_voice_models(request: Request, user: CurrentUser):
    """AssemblyAI speech models a ``voice`` node can pick as its ``speech_model``.

    AssemblyAI exposes no endpoint that lists speech-to-text models (only the LLM
    gateway lists chat models), so this serves the curated ``VOICE_MODELS`` list.
    """
    return {"data": VOICE_MODELS}


@pipeline_router.post("/{project_id}", response_model=PipelineResponse)
def create_pipeline(
    request: Request,
    project_id: UUID,
    data: PipelineCreate,
    db: DbSession,
    user: CurrentUser
):
    try:
        new_pipeline = Pipeline(**data.model_dump(exclude_unset=True))
        new_pipeline.user_id = user.id
        new_pipeline.project_id = project_id

        db.add(new_pipeline)
        db.commit()
        db.refresh(new_pipeline)

        return PipelineResponse.model_validate(new_pipeline)
    except IntegrityError:
        db.rollback()
        raise ResourceConflictEzception("Pipeline")
    except Exception:
        db.rollback()
        raise

@pipeline_router.get("/", response_model=ListPipelineResponse)
def get_all_user_pipelines(
    request: Request,
    db: DbSession,
    user: CurrentUser
):
    pipelines = (
        db.query(Pipeline)
        .filter(Pipeline.user_id == user.id, Pipeline.deleted_at.is_(None))
        .all()
    )
    return {
        "pipelines": pipelines
    }

@pipeline_router.delete("/{id}", response_model=dict)
def delete_pipeline(
    request: Request,
    id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    pipeline = _get_owned_pipeline(db, id, user)
    pipeline.deleted_at = datetime.now(UTC)
    db.commit()
    return {"message": f"{pipeline.name} has been deleted"}

@pipeline_router.get("/{project_id}/{id}", response_model=PipelineResponse)
def get_pipeline_details(
    request: Request,
    project_id: UUID,
    id: UUID,
    db: DbSession,
    user: CurrentUser
):
    pipeline = db.query(Pipeline).filter(Pipeline.id == id, Pipeline.user_id==user.id, Pipeline.deleted_at.is_(None)).one_or_none()
    if not pipeline:
        raise ResourceNotFoundException("Pipeline")
    return PipelineResponse.model_validate(pipeline)

@node_router.post("/{pipeline_id}/", response_model=PipelineNodeCreateResponse)
def create_node_in_pipeline(
    request: Request,
    data: PipelineNodeCreate,
    pipeline_id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    _get_owned_pipeline(db, pipeline_id, user)
    try:
        new_node = PipelineNode(**data.model_dump(exclude_unset=True))
        new_node.pipeline_id = pipeline_id

        db.add(new_node)
        db.commit()
        db.refresh(new_node)

        return PipelineNodeCreateResponse.model_validate(new_node)
    except IntegrityError:
        db.rollback()
        raise ResourceConflictEzception("Pipeline")
    except Exception:
        db.rollback()
        raise

@node_router.get("/{pipeline_id}/", response_model=ListPipelineNodeResponse)
def list_pipeline_nodes(
    request: Request,
    pipeline_id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    _get_owned_pipeline(db, pipeline_id, user)
    nodes = (
        db.query(PipelineNode)
        .filter(
            PipelineNode.pipeline_id == pipeline_id,
            PipelineNode.deleted_at.is_(None),
        )
        .all()
    )
    return {"nodes": nodes}

@node_router.get("/{pipeline_id}/{id}", response_model=PipelineNodeResponse)
def get_pipeline_node_details(
    request: Request,
    pipeline_id: UUID,
    id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    _get_owned_pipeline(db, pipeline_id, user)
    node = (
        db.query(PipelineNode)
        .filter(
            PipelineNode.id == id,
            PipelineNode.pipeline_id == pipeline_id,
            PipelineNode.deleted_at.is_(None),
        ).one_or_none()
    )
    if not node:
        raise ResourceNotFoundException("node")
    return node

@node_router.patch("/{pipeline_id}/{id}", response_model=PipelineNodeResponse)
def update_pipeline_node(
    request: Request,
    data: PipelineNodeUpdate,
    pipeline_id: UUID,
    id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    _get_owned_pipeline(db, pipeline_id, user)
    node = (
        db.query(PipelineNode)
        .filter(
            PipelineNode.id == id,
            PipelineNode.pipeline_id == pipeline_id,
            PipelineNode.deleted_at.is_(None),
        ).one_or_none()
    )
    if not node:
        raise ResourceNotFoundException("node")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(node, key, value)

    db.commit()
    db.refresh(node)
    return node

@node_router.delete("/{pipeline_id}/{id}", response_model=dict)
def delete_pipeline_node(
    request: Request,
    pipeline_id: UUID,
    id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    _get_owned_pipeline(db, pipeline_id, user)
    node = (
        db.query(PipelineNode)
        .filter(
            PipelineNode.id == id,
            PipelineNode.pipeline_id == pipeline_id,
            PipelineNode.deleted_at.is_(None),
        ).one_or_none()
    )
    if not node:
        raise ResourceNotFoundException("node")

    node.deleted_at = datetime.now(UTC)
    db.commit()
    return {"message": "Node deleted"}


@runs_router.post("/pipelines/{pipeline_id}", response_model=PipelineRunResponse)
async def run_pipeline_endpoint(
    request: Request,
    pipeline_id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    """Execute a pipeline synchronously and return the completed run."""
    _get_owned_pipeline(db, pipeline_id, user)

    run = PipelineRuns(pipeline_id=pipeline_id)
    db.add(run)
    db.commit()
    db.refresh(run)

    run = await run_pipeline(db, run, pipeline_id)
    return PipelineRunResponse.model_validate(run)


@runs_router.get("/pipelines/{pipeline_id}", response_model=ListPipelineRunResponse)
def list_pipeline_runs(
    request: Request,
    pipeline_id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    _get_owned_pipeline(db, pipeline_id, user)
    runs = (
        db.query(PipelineRuns)
        .filter(PipelineRuns.pipeline_id == pipeline_id)
        .order_by(PipelineRuns.created_at.desc())
        .all()
    )
    return {"runs": runs}


@runs_router.get("/pipelines/{pipeline_id}/{run_id}", response_model=PipelineRunResponse)
def get_pipeline_run(
    request: Request,
    pipeline_id: UUID,
    run_id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    _get_owned_pipeline(db, pipeline_id, user)
    run = (
        db.query(PipelineRuns)
        .filter(
            PipelineRuns.id == run_id,
            PipelineRuns.pipeline_id == pipeline_id,
        )
        .one_or_none()
    )
    if not run:
        raise ResourceNotFoundException("Pipeline run")
    return run

