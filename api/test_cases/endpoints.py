from uuid import UUID
from datetime import datetime, UTC
from sqlalchemy.exc import IntegrityError
from fastapi import (
    APIRouter,
    Request,
    Query,
)

from .models import (
    TestCase,
    TestCaseNode,
    TestCaseRun,
)

from .executor import run_test_case

from .schemas import (
    TestCaseCreate,
    TestCaseUpdate,
    TestCaseResponse,
    TestCaseDetailResponse,
    TestCaseNodeCreate,
    TestCaseNodeUpdate,
    TestCaseNodeCreateResponse,
    TestCaseNodeResponse,
    ListTestCaseNodes,
    ListTestCaseResponse,
    TestCaseRunResponse,
    ListTestCaseRunResponse,
)

from api.pipelines.models import Pipeline

from api.common.exceptions import (
    ResourceConflictEzception,
    ResourceNotFoundException,
)

from api.common.security import (
    DbSession,
    CurrentUser,
)

test_cases_router = APIRouter(
    prefix="/test-cases",
    tags=["TEST CASES"]
)


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


def _get_owned_test_case(db, pipeline_id: UUID, test_case_id: UUID, user):
    _get_owned_pipeline(db, pipeline_id, user)
    test_case = (
        db.query(TestCase)
        .filter(
            TestCase.id == test_case_id,
            TestCase.pipeline_id == pipeline_id,
            TestCase.deleted_at.is_(None),
        )
        .one_or_none()
    )
    if not test_case:
        raise ResourceNotFoundException("Test case")
    return test_case


def _get_owned_node(db, test_case_id: UUID, node_id: UUID, user):
    node = (
        db.query(TestCaseNode)
        .filter(
            TestCaseNode.id == node_id,
            TestCaseNode.test_case_id == test_case_id,
            TestCaseNode.user_id == user.id,
            TestCaseNode.deleted_at.is_(None),
        )
        .one_or_none()
    )
    if not node:
        raise ResourceNotFoundException("Test case node")
    return node


@test_cases_router.post("/{pipeline_id}", response_model=TestCaseResponse)
def create_test_case(
    request: Request,
    pipeline_id: UUID,
    data: TestCaseCreate,
    db: DbSession,
    user: CurrentUser,
):
    _get_owned_pipeline(db, pipeline_id, user)
    try:
        test_case = TestCase(**data.model_dump(exclude_unset=True))
        test_case.pipeline_id = pipeline_id
        test_case.user_id = user.id

        db.add(test_case)
        db.commit()
        db.refresh(test_case)

        return TestCaseResponse.model_validate(test_case)
    except IntegrityError:
        db.rollback()
        raise ResourceConflictEzception("Test case")
    except Exception:
        db.rollback()
        raise


@test_cases_router.get("/", response_model=ListTestCaseResponse)
def list_all_test_cases(
    request: Request,
    db: DbSession,
    user: CurrentUser,
):
    test_cases = (
        db.query(TestCase)
        .filter(TestCase.user_id == user.id, TestCase.deleted_at.is_(None))
        .all()
    )
    return {"test_cases": test_cases}


@test_cases_router.get("/{pipeline_id}/", response_model=ListTestCaseResponse)
def get_test_cases_for_pipeline(
    request: Request,
    pipeline_id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    _get_owned_pipeline(db, pipeline_id, user)
    test_cases = (
        db.query(TestCase)
        .filter(
            TestCase.pipeline_id == pipeline_id,
            TestCase.deleted_at.is_(None),
        )
        .all()
    )
    return {"test_cases": test_cases}


@test_cases_router.get("/{pipeline_id}/{test_case_id}", response_model=TestCaseDetailResponse)
def get_test_case(
    request: Request,
    pipeline_id: UUID,
    test_case_id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    return _get_owned_test_case(db, pipeline_id, test_case_id, user)


@test_cases_router.patch("/{pipeline_id}/{test_case_id}", response_model=TestCaseResponse)
def update_test_case(
    request: Request,
    pipeline_id: UUID,
    test_case_id: UUID,
    data: TestCaseUpdate,
    db: DbSession,
    user: CurrentUser,
):
    test_case = _get_owned_test_case(db, pipeline_id, test_case_id, user)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(test_case, key, value)
    try:
        db.commit()
        db.refresh(test_case)
        return TestCaseResponse.model_validate(test_case)
    except IntegrityError:
        db.rollback()
        raise ResourceConflictEzception("Test case")
    except Exception:
        db.rollback()
        raise


@test_cases_router.delete("/{pipeline_id}/{test_case_id}", response_model=dict)
def delete_test_case(
    request: Request,
    pipeline_id: UUID,
    test_case_id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    test_case = _get_owned_test_case(db, pipeline_id, test_case_id, user)
    test_case.deleted_at = datetime.now(UTC)
    db.commit()
    return {"message": f"{test_case.name} has been deleted"}


@test_cases_router.post("/{pipeline_id}/{test_case_id}/", response_model=TestCaseNodeCreateResponse)
def create_test_case_node(
    request: Request,
    pipeline_id: UUID,
    test_case_id: UUID,
    data: TestCaseNodeCreate,
    db: DbSession,
    user: CurrentUser,
):
    _get_owned_test_case(db, pipeline_id, test_case_id, user)

    next_position = (
        db.query(TestCaseNode)
        .filter(
            TestCaseNode.test_case_id == test_case_id,
            TestCaseNode.deleted_at.is_(None),
        )
        .count()
    )
    try:
        node = TestCaseNode(**data.model_dump(exclude_unset=True))
        node.test_case_id = test_case_id
        node.user_id = user.id
        node.position = next_position

        db.add(node)
        db.commit()
        db.refresh(node)

        return TestCaseNodeCreateResponse.model_validate(node)
    except IntegrityError:
        db.rollback()
        raise ResourceConflictEzception("Test case node")
    except Exception:
        db.rollback()
        raise


@test_cases_router.get("/{pipeline_id}/{test_case_id}/nodes", response_model=ListTestCaseNodes)
def get_test_case_nodes(
    request: Request,
    pipeline_id: UUID,
    test_case_id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    _get_owned_test_case(db, pipeline_id, test_case_id, user)
    nodes = (
        db.query(TestCaseNode)
        .filter(
            TestCaseNode.test_case_id == test_case_id,
            TestCaseNode.deleted_at.is_(None),
        )
        .order_by(TestCaseNode.position)
        .all()
    )
    return {"nodes": nodes}


@test_cases_router.get("/{pipeline_id}/{test_case_id}/nodes/{node_id}", response_model=TestCaseNodeResponse)
def get_test_case_node(
    request: Request,
    pipeline_id: UUID,
    test_case_id: UUID,
    node_id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    _get_owned_test_case(db, pipeline_id, test_case_id, user)
    return _get_owned_node(db, test_case_id, node_id, user)


@test_cases_router.patch("/{pipeline_id}/{test_case_id}/nodes/{node_id}", response_model=TestCaseNodeResponse)
def update_test_case_node(
    request: Request,
    pipeline_id: UUID,
    test_case_id: UUID,
    node_id: UUID,
    data: TestCaseNodeUpdate,
    db: DbSession,
    user: CurrentUser,
):
    _get_owned_test_case(db, pipeline_id, test_case_id, user)
    node = _get_owned_node(db, test_case_id, node_id, user)

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(node, key, value)

    db.commit()
    db.refresh(node)
    return node


@test_cases_router.delete("/{pipeline_id}/{test_case_id}/nodes/{node_id}", response_model=dict)
def delete_test_case_node(
    request: Request,
    pipeline_id: UUID,
    test_case_id: UUID,
    node_id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    _get_owned_test_case(db, pipeline_id, test_case_id, user)
    node = _get_owned_node(db, test_case_id, node_id, user)
    node.deleted_at = datetime.now(UTC)
    db.commit()
    return {"message": "Node deleted"}


@test_cases_router.post(
    "/{pipeline_id}/{test_case_id}/runs", response_model=TestCaseRunResponse
)
async def run_test_case_endpoint(
    request: Request,
    pipeline_id: UUID,
    test_case_id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    """Run the pipeline and evaluate this test case's assertions against it."""
    test_case = _get_owned_test_case(db, pipeline_id, test_case_id, user)

    run = TestCaseRun(test_case_id=test_case.id)
    db.add(run)
    db.commit()
    db.refresh(run)

    run = await run_test_case(db, run, test_case)
    return TestCaseRunResponse.model_validate(run)


@test_cases_router.get(
    "/{pipeline_id}/{test_case_id}/runs", response_model=ListTestCaseRunResponse
)
def list_test_case_runs(
    request: Request,
    pipeline_id: UUID,
    test_case_id: UUID,
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(20, ge=1, le=100),
):
    _get_owned_test_case(db, pipeline_id, test_case_id, user)
    runs = (
        db.query(TestCaseRun)
        .filter(TestCaseRun.test_case_id == test_case_id)
        .order_by(TestCaseRun.created_at.desc())
        .limit(limit)
        .all()
    )
    return {"runs": runs}


@test_cases_router.get(
    "/{pipeline_id}/{test_case_id}/runs/{run_id}", response_model=TestCaseRunResponse
)
def get_test_case_run(
    request: Request,
    pipeline_id: UUID,
    test_case_id: UUID,
    run_id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    _get_owned_test_case(db, pipeline_id, test_case_id, user)
    run = (
        db.query(TestCaseRun)
        .filter(
            TestCaseRun.id == run_id,
            TestCaseRun.test_case_id == test_case_id,
        )
        .one_or_none()
    )
    if not run:
        raise ResourceNotFoundException("Test case run")
    return run
