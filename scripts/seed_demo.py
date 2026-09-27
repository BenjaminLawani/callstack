"""Seed a demo pipeline for local/dev use.

Creates (idempotently) a self-contained demo the whole product can be shown with:

    Voice ("transcribe")  ->  LLM ("summarize")  ->  Assert ("not empty")

The voice node uses an AssemblyAI speech model (``universal-2``) on a public
sample clip; the LLM node summarises the transcript; the assert node checks the
result is non-empty. It attaches to a dedicated demo user so it never touches a
real account, and it is safe to re-run: the demo user, profile and project are
reused, and the pipeline's nodes are rebuilt from scratch each time.

Run from the project root (loads DATABASE_URL etc. from .env like the app does)::

    python scripts/seed_demo.py
    python scripts/seed_demo.py --email demo@acme.test --password hunter2
    python scripts/seed_demo.py --pipeline-name "Voice Demo"
"""

import argparse
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Allow `python scripts/seed_demo.py` from anywhere by putting the project root
# (this file's parent's parent) on the import path before importing the app.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.common.registry  # noqa: F401  (registers every ORM model on Base)
from api.auth.models import User, UserProfile
from api.common.db import SessionLocal
from api.common.enums import LoginMethod, PipelineNodeType
from api.common.security import hash_password
from api.pipelines.models import Pipeline, PipelineNode
from api.projects.models import Project

DEFAULT_EMAIL = "seed-demo@example.com"
DEFAULT_PASSWORD = "demo-pass-123"  # nosec - a throwaway credential for a demo user
DEFAULT_PIPELINE_NAME = "Voice Demo"  # pipeline names are capped at 16 chars

# AssemblyAI's public sample clip — reachable by both the batch API and ffmpeg.
SAMPLE_AUDIO_URL = "https://assembly.ai/wildfires.mp3"

# The nodes, in execution order (the executor orders by created_at, which we set
# explicitly below so the order is deterministic regardless of insert timing).
# Each config uses the keys the executor actually reads for that node type.
DEMO_NODES: list[dict] = [
    {
        "name": "transcribe",
        "node_type": PipelineNodeType.VOICE,
        "config": {
            "audio_url": SAMPLE_AUDIO_URL,
            "speech_model": "universal-2",  # AssemblyAI multilingual model
            "mode": "batch",
        },
    },
    {
        "name": "summarize",
        "node_type": PipelineNodeType.LLM,
        "config": {
            "model": "qwen3.5-4b-32k-fast",
            "system": "You are a concise assistant.",
            "prompt": "Summarize this transcript in one sentence:\n\n{input}",
            "temperature": 0.3,
            "max_tokens": 120,
        },
    },
    {
        "name": "not empty",
        "node_type": PipelineNodeType.ASSERT,
        # Assert nodes are evaluated with api.common.assertions: each config key
        # is a check. min_length keeps the demo green as long as there's output.
        "config": {"min_length": 1},
    },
]


def _get_or_create_user(db, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email).one_or_none()
    if user:
        return user
    user = User(
        email=email,
        password=hash_password(password),
        login_method=LoginMethod.LOCAL,
    )
    db.add(user)
    db.flush()
    return user


def _ensure_profile(db, user: User) -> None:
    if db.query(UserProfile).filter_by(user_id=user.id).one_or_none():
        return
    base = (user.email.split("@", 1)[0] or "demo").replace(".", "_")[:56]
    username = base
    while db.query(UserProfile).filter_by(username=username).one_or_none():
        username = f"{base}-{uuid.uuid4().hex[:6]}"
    db.add(UserProfile(user_id=user.id, username=username, preferences={}))
    db.flush()


def _get_or_create_project(db, user: User) -> Project:
    project = (
        db.query(Project)
        .filter(Project.user_id == user.id, Project.name == "Demo project")
        .one_or_none()
    )
    if project:
        project.deleted_at = None
        return project
    # slug is globally unique — start stable, fall back to a suffixed slug.
    slug = "seed-demo-project"
    while db.query(Project).filter(Project.slug == slug).one_or_none():
        slug = f"seed-demo-project-{uuid.uuid4().hex[:6]}"
    project = Project(user_id=user.id, name="Demo project", slug=slug)
    db.add(project)
    db.flush()
    return project


def _upsert_pipeline(db, user: User, project: Project, name: str) -> Pipeline:
    # (user_id, name) is unique and the row survives a soft delete, so match on
    # both and reuse the row rather than risk a constraint violation.
    pipeline = (
        db.query(Pipeline)
        .filter(Pipeline.user_id == user.id, Pipeline.name == name)
        .one_or_none()
    )
    if pipeline:
        pipeline.deleted_at = None
        pipeline.project_id = project.id
    else:
        pipeline = Pipeline(user_id=user.id, project_id=project.id, name=name)
        db.add(pipeline)
    db.flush()
    return pipeline


def _rebuild_nodes(db, pipeline: Pipeline) -> list[PipelineNode]:
    # Hard-delete any existing nodes so re-running gives a clean, single copy.
    db.query(PipelineNode).filter(PipelineNode.pipeline_id == pipeline.id).delete(
        synchronize_session=False
    )
    base_time = datetime.now(UTC)
    created: list[PipelineNode] = []
    for i, spec in enumerate(DEMO_NODES):
        node = PipelineNode(
            pipeline_id=pipeline.id,
            name=spec["name"],
            node_type=spec["node_type"],
            config=spec["config"],
            # Explicit, strictly increasing timestamps → deterministic run order.
            created_at=base_time + timedelta(seconds=i),
        )
        db.add(node)
        created.append(node)
    db.flush()
    return created


def seed(email: str, password: str, pipeline_name: str) -> None:
    db = SessionLocal()
    try:
        user = _get_or_create_user(db, email, password)
        _ensure_profile(db, user)
        project = _get_or_create_project(db, user)
        pipeline = _upsert_pipeline(db, user, project, pipeline_name)
        nodes = _rebuild_nodes(db, pipeline)
        db.commit()

        print("Seeded demo pipeline:")
        print(f"  pipeline : {pipeline.name} ({pipeline.id})")
        print(f"  project  : {project.name} (/{project.slug})")
        print(f"  owner    : {user.email}")
        print("  nodes    :")
        for node in nodes:
            print(f"    - {node.node_type.value:<7} {node.name}  {node.config}")
        print("\nSign in to view it:")
        print(f"  email    : {email}")
        print(f"  password : {password}")
        print("  page     : /pipelines")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a demo pipeline.")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="demo user's email")
    parser.add_argument(
        "--password", default=DEFAULT_PASSWORD, help="demo user's password (if created)"
    )
    parser.add_argument(
        "--pipeline-name",
        default=DEFAULT_PIPELINE_NAME,
        help="pipeline name (max 16 chars)",
    )
    args = parser.parse_args()
    if len(args.pipeline_name) > 16:
        parser.error("pipeline name must be at most 16 characters")
    seed(args.email, args.password, args.pipeline_name)


if __name__ == "__main__":
    main()
