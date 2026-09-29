"""Seed the demo accounts, pipelines and test cases for local/dev use.

Creates (idempotently) a self-contained demo that exercises every part of the
product, for each demo account:

    Project ("Demo project")
      └─ Pipeline ("Voice Demo")
           Voice ("transcribe")  ->  LLM ("summarize")  ->  Assert ("not empty")
           Test case "Produces a summary"  (positive: output must be non-empty)
           Test case "Rejects sentinel"    (negative: should_fail guard)

The voice node uses an AssemblyAI speech model (``universal-2``) on a public
sample clip; the LLM node summarises the transcript; the assert node checks the
result is non-empty. Two test cases sit on top of the pipeline — one ordinary
assertion and one ``should_fail`` guard — so the test-case runner has both a
green and an inverted case to show.

This writes straight to the database (no running server or auth needed) and is
safe to re-run: users, profiles and projects are reused, while the pipeline's
nodes and the demo test cases are rebuilt from scratch each time so you always
get a single clean copy.

Run from the project root (loads DATABASE_URL etc. from .env like the app does)::

    python scripts/seed_demo.py                       # seed both demo accounts
    python scripts/seed_demo.py --emails a@x.test     # seed just one account
    python scripts/seed_demo.py --no-reset-password   # leave existing pwds alone
    python scripts/seed_demo.py --pipeline-name "QA"   # custom pipeline name
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
from api.test_cases.models import TestCase, TestCaseNode

# The accounts the demo is shown from. Both are throwaway local dev logins.
DEFAULT_EMAILS = ["la.benjamib@gmail.com", "user@example.com"]
DEFAULT_PASSWORD = "callstack-demo-123"  # nosec - throwaway credential for demo users
DEFAULT_PIPELINE_NAME = "Voice Demo"  # pipeline names are capped at 16 chars

# AssemblyAI's public sample clip — reachable by both the batch API and ffmpeg.
SAMPLE_AUDIO_URL = "https://assembly.ai/wildfires.mp3"

# The pipeline nodes, in execution order (the executor orders by created_at,
# which we set explicitly below so the order is deterministic regardless of
# insert timing). Each config uses the keys the executor reads for that type.
DEMO_NODES: list[dict] = [
    {
        "name": "transcribe",
        "node_type": PipelineNodeType.VOICE,
        "config": {
            "audio_url": SAMPLE_AUDIO_URL,
            "speech_model": "universal-2",  # AssemblyAI multilingual model
            "mode": "batch",  # robust + fast; needs no ffmpeg or realtime wait
        },
    },
    {
        "name": "summarize",
        "node_type": PipelineNodeType.LLM,
        "config": {
            "model": "qwen3.5-4b-32k-fast",  # the one model AVAILABLE_MODELS allows
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
        # is a check. min_length keeps the run green as long as there's output.
        "config": {"min_length": 10},
    },
]

# Test cases layered on the pipeline. Each runs the pipeline, then checks its
# final output. ``should_fail`` inverts a node's verdict, so a guard node passes
# precisely when its assertions do NOT hold — a deterministic green regardless
# of what the model returns.
DEMO_TEST_CASES: list[dict] = [
    {
        "name": "Produces a summary",
        "nodes": [
            {
                "name": "non-empty",
                "description": "summary is not empty",
                "assertions": {"min_length": 10},
                "should_fail": False,
            },
        ],
    },
    {
        "name": "Rejects sentinel",
        "nodes": [
            {
                "name": "neg-guard",
                "description": "must not equal sentinel",
                "assertions": {"equals": "__never_matches__"},
                "should_fail": True,
            },
        ],
    },
]

# Test-case names owned by this seed. Only these are torn down on a re-run, so
# any hand-made test cases on the pipeline are left untouched.
_DEMO_TEST_CASE_NAMES = [tc["name"] for tc in DEMO_TEST_CASES]


def _get_or_create_user(db, email: str, password: str, reset_password: bool) -> tuple[User, str]:
    """Return the demo user, creating it if missing. Returns (user, note)."""
    user = db.query(User).filter(User.email == email).one_or_none()
    if user:
        if reset_password:
            user.password = hash_password(password)
            user.login_method = LoginMethod.LOCAL
            return user, "existing account, password reset to demo password"
        return user, "existing account, password left unchanged"
    user = User(
        email=email,
        password=hash_password(password),
        login_method=LoginMethod.LOCAL,
    )
    db.add(user)
    db.flush()
    return user, "new account created"


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


def _rebuild_test_cases(db, user: User, pipeline: Pipeline) -> list[TestCase]:
    # Tear down only the test cases this seed owns (by name); leave any others.
    existing = (
        db.query(TestCase)
        .filter(
            TestCase.pipeline_id == pipeline.id,
            TestCase.name.in_(_DEMO_TEST_CASE_NAMES),
        )
        .all()
    )
    for tc in existing:
        db.delete(tc)  # cascade="all, delete-orphan" removes the child nodes too
    db.flush()

    created: list[TestCase] = []
    for spec in DEMO_TEST_CASES:
        test_case = TestCase(
            name=spec["name"],
            user_id=user.id,
            pipeline_id=pipeline.id,
        )
        db.add(test_case)
        db.flush()
        for position, node_spec in enumerate(spec["nodes"]):
            db.add(
                TestCaseNode(
                    user_id=user.id,
                    test_case_id=test_case.id,
                    name=node_spec["name"],
                    description=node_spec.get("description"),
                    assertions=node_spec["assertions"],
                    should_fail=node_spec["should_fail"],
                    position=position,
                )
            )
        created.append(test_case)
    db.flush()
    return created


def seed_account(db, email: str, password: str, pipeline_name: str, reset_password: bool) -> None:
    user, note = _get_or_create_user(db, email, password, reset_password)
    _ensure_profile(db, user)
    project = _get_or_create_project(db, user)
    pipeline = _upsert_pipeline(db, user, project, pipeline_name)
    nodes = _rebuild_nodes(db, pipeline)
    test_cases = _rebuild_test_cases(db, user, pipeline)

    can_login = reset_password or note == "new account created"
    print(f"\n{email}  ({note})")
    print(f"  project   : {project.name} (/{project.slug})")
    print(f"  pipeline  : {pipeline.name} ({pipeline.id})")
    print("  nodes     :")
    for node in nodes:
        print(f"    - {node.node_type.value:<7} {node.name}  {node.config}")
    print("  test cases:")
    for tc in test_cases:
        for tcn in tc.nodes:
            flag = " [should_fail]" if tcn.should_fail else ""
            print(f"    - {tc.name!r} :: {tcn.name}{flag}  {tcn.assertions}")
    if can_login:
        print(f"  login     : {email} / {password}")
    else:
        print(f"  login     : {email} / (unchanged — use --reset-password to set it)")


def seed(emails: list[str], password: str, pipeline_name: str, reset_password: bool) -> None:
    db = SessionLocal()
    try:
        for email in emails:
            seed_account(db, email.strip().lower(), password, pipeline_name, reset_password)
        db.commit()
        print("\nSeeded. Open /login, sign in, then visit /pipelines, /test-cases and /transcribe.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the demo accounts and pipelines.")
    parser.add_argument(
        "--emails",
        nargs="+",
        default=DEFAULT_EMAILS,
        help="demo account email(s) to seed (default: both demo accounts)",
    )
    parser.add_argument(
        "--password", default=DEFAULT_PASSWORD, help="demo password for the accounts"
    )
    parser.add_argument(
        "--pipeline-name",
        default=DEFAULT_PIPELINE_NAME,
        help="pipeline name (max 16 chars)",
    )
    parser.add_argument(
        "--no-reset-password",
        dest="reset_password",
        action="store_false",
        help="do not reset the password of accounts that already exist",
    )
    parser.set_defaults(reset_password=True)
    args = parser.parse_args()
    if len(args.pipeline_name) > 16:
        parser.error("pipeline name must be at most 16 characters")
    seed(args.emails, args.password, args.pipeline_name, args.reset_password)


if __name__ == "__main__":
    main()
