"""Test case execution: run the pipeline, then evaluate assertions.

A test case belongs to a pipeline. Running it:
  1. Executes the pipeline (via ``api.pipelines.executor.run_pipeline``),
     producing a text output.
  2. Evaluates each ordered ``TestCaseNode``'s ``assertions`` against that
     output. ``should_fail`` inverts the node's verdict (an expected-failure
     node passes precisely when its assertions do NOT hold).
  3. The test case passes only if every node passes.

If the pipeline itself errors, the test case run is recorded as ERROR and no
assertions are evaluated.
"""

from datetime import datetime, UTC

from api.common.enums import RunStatus
from api.common.assertions import evaluate_assertions
from api.pipelines.models import PipelineRuns
from api.pipelines.executor import run_pipeline

from .models import TestCase, TestCaseNode, TestCaseRun


async def run_test_case(db, run: TestCaseRun, test_case: TestCase) -> TestCaseRun:
    """Execute ``test_case`` and update ``run`` in place with the verdict."""
    run.status = RunStatus.RUNNING
    run.started_at = datetime.now(UTC)
    db.commit()

    # 1. Run the pipeline the test case targets.
    pipeline_run = PipelineRuns(pipeline_id=test_case.pipeline_id)
    db.add(pipeline_run)
    db.commit()
    db.refresh(pipeline_run)

    pipeline_run = await run_pipeline(db, pipeline_run, test_case.pipeline_id)

    run.pipeline_run_id = pipeline_run.id
    run.output = pipeline_run.output

    if pipeline_run.status == RunStatus.ERROR:
        run.status = RunStatus.ERROR
        run.error = f"pipeline run errored: {pipeline_run.error}"
        run.finished_at = datetime.now(UTC)
        db.commit()
        return run

    # 2. Evaluate each test node against the pipeline output.
    nodes = (
        db.query(TestCaseNode)
        .filter(
            TestCaseNode.test_case_id == test_case.id,
            TestCaseNode.deleted_at.is_(None),
        )
        .order_by(TestCaseNode.position)
        .all()
    )

    results: list[dict] = []
    all_passed = True
    for node in nodes:
        raw_passed, checks = evaluate_assertions(node.assertions or {}, run.output or "")
        # should_fail flips the verdict: the node is expected to NOT satisfy its
        # assertions, so it passes when raw_passed is False.
        passed = raw_passed != node.should_fail
        results.append({
            "node_id": str(node.id),
            "name": node.name,
            "should_fail": node.should_fail,
            "assertions_held": raw_passed,
            "passed": passed,
            "checks": checks,
        })
        all_passed = all_passed and passed

    # 3. Record the verdict.
    run.results = results
    run.status = RunStatus.PASSED if all_passed else RunStatus.FAILED
    run.finished_at = datetime.now(UTC)
    db.commit()
    return run
