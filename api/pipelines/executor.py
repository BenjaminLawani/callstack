from datetime import datetime, UTC

from api.common.enums import PipelineNodeType, RunStatus
from api.common.assertions import evaluate_assertions
from api.common.llm_gateway import chat_completion, LLMGatewayError
from api.common.transcription import (
    TranscriptionError,
    transcribe,
    transcribe_kwargs_from_config,
)
from api.metrics.models import TranscriptionMetric

from .models import Pipeline, PipelineNode, PipelineRuns


class PipelineExecutionError(RuntimeError):
    """A node failed in a way that aborts the run (bad config, gateway error)."""


def _ordered_nodes(db, pipeline_id):
    return (
        db.query(PipelineNode)
        .filter(
            PipelineNode.pipeline_id == pipeline_id,
            PipelineNode.deleted_at.is_(None),
        )
        .order_by(PipelineNode.created_at)
        .all()
    )


async def _run_llm_node(node: PipelineNode, current_output: str) -> str:
    config = node.config or {}
    model = config.get("model")
    if not model:
        raise PipelineExecutionError(f"node '{node.name}' is missing config.model")

    prompt_template = config.get("prompt", "{input}")
    prompt = prompt_template.replace("{input}", current_output)

    messages = []
    if config.get("system"):
        messages.append({"role": "system", "content": config["system"]})
    messages.append({"role": "user", "content": prompt})

    return await chat_completion(
        model,
        messages,
        temperature=config.get("temperature"),
        max_tokens=config.get("max_tokens"),
    )


async def _run_voice_node(db, run, node: PipelineNode, user_id) -> tuple[str, dict]:
    """Transcribe the node's audio, persist a metric row, return (text, metrics).

    A ``voice`` node's ``config`` holds the ``audio_url`` (and optional ``mode``,
    ``speech_model``, ``realtime``, ``max_audio_seconds``). The transcript becomes
    the pipeline's running output so downstream ``assert``/``llm`` nodes see it.
    """
    config = node.config or {}
    audio_url = config.get("audio_url")
    if not audio_url:
        raise PipelineExecutionError(f"voice node '{node.name}' is missing config.audio_url")

    metric = TranscriptionMetric(
        user_id=user_id,
        pipeline_run_id=run.id,
        node_id=node.id,
        mode=config.get("mode", "streaming"),
        speech_model=config.get("speech_model"),
        audio_url=audio_url,
    )

    try:
        result = await transcribe(audio_url, **transcribe_kwargs_from_config(config))
    except TranscriptionError as exc:
        metric.error = str(exc)
        db.add(metric)
        db.commit()
        raise PipelineExecutionError(f"voice node '{node.name}' failed: {exc}") from exc

    metric.mode = result.mode
    metric.transcript = result.text
    metric.ttft_ms = result.ttft_ms
    metric.total_ms = result.total_ms
    metric.audio_duration_ms = result.audio_duration_ms
    metric.real_time_factor = result.real_time_factor
    metric.word_count = result.word_count
    metric.confidence = result.confidence
    metric.raw = result.raw
    db.add(metric)
    db.commit()

    return result.text, result.metrics()


async def run_pipeline(db, run: PipelineRuns, pipeline_id) -> PipelineRuns:
    run.status = RunStatus.RUNNING
    run.started_at = datetime.now(UTC)
    db.commit()

    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).one_or_none()
    user_id = pipeline.user_id if pipeline else None

    node_results: list[dict] = []
    current_output = ""

    try:
        for node in _ordered_nodes(db, pipeline_id):
            entry = {
                "node_id": str(node.id),
                "name": node.name,
                "node_type": node.node_type.value,
            }

            if node.node_type == PipelineNodeType.LLM:
                current_output = await _run_llm_node(node, current_output)
                entry["output"] = current_output

            elif node.node_type == PipelineNodeType.ASSERT:
                passed, checks = evaluate_assertions(node.config or {}, current_output)
                entry["passed"] = passed
                entry["checks"] = checks
                if not passed:
                    node_results.append(entry)
                    run.node_results = node_results
                    run.output = current_output
                    run.status = RunStatus.FAILED
                    run.finished_at = datetime.now(UTC)
                    db.commit()
                    return run

            elif node.node_type == PipelineNodeType.VOICE:
                current_output, metrics = await _run_voice_node(db, run, node, user_id)
                entry["output"] = current_output
                entry["metrics"] = metrics

            else:  # FAIL — stubbed for this slice
                entry["skipped"] = True
                entry["detail"] = f"'{node.node_type.value}' nodes are not executed yet"

            node_results.append(entry)

        run.node_results = node_results
        run.output = current_output
        run.status = RunStatus.PASSED
        run.finished_at = datetime.now(UTC)
        db.commit()
        return run

    except (PipelineExecutionError, LLMGatewayError) as exc:
        run.node_results = node_results
        run.output = current_output
        run.status = RunStatus.ERROR
        run.error = str(exc)
        run.finished_at = datetime.now(UTC)
        db.commit()
        return run
