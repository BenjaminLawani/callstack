from uuid import UUID

from fastapi import (
    APIRouter,
    Query,
    Request,
)

from .models import TranscriptionMetric
from .schemas import (
    AudioUploadRequest,
    AudioUploadResponse,
    ListTranscriptionMetricResponse,
    TranscribeRequest,
    TranscriptionMetricResponse,
)

from api.common.assertions import evaluate_assertions
from api.common.exceptions import ResourceNotFoundException
from api.common.security import CurrentUser, DbSession
from api.common.storage import create_audio_upload
from api.common.transcription import TranscriptionError, transcribe

transcription_router = APIRouter(
    prefix="/transcriptions",
    tags=["TRANSCRIPTIONS"],
)


@transcription_router.post("/audio-upload", response_model=AudioUploadResponse)
def create_audio_upload_url(
    request: Request,
    data: AudioUploadRequest,
    user: CurrentUser,
):
    """Presigned URL for the browser to upload an audio file straight to R2."""
    return create_audio_upload(data.content_type, folder=f"audio/{user.id}")


@transcription_router.post("/", response_model=TranscriptionMetricResponse)
async def run_transcription(
    request: Request,
    data: TranscribeRequest,
    db: DbSession,
    user: CurrentUser,
):
    """Transcribe an audio file, optionally validate it, and record the metrics.

    Returns a persisted metric row: the transcript, latency metrics (time to
    first token, total latency, real-time factor) and, when ``assertions`` were
    given, the pass/fail verdict. A provider/decoding failure is captured on the
    row's ``error`` field rather than raised, so the caller always gets a record.
    """
    metric = TranscriptionMetric(
        user_id=user.id,
        mode=data.mode.value,
        speech_model=data.speech_model,
        audio_url=data.audio_url,
    )

    try:
        result = await transcribe(
            data.audio_url,
            mode=data.mode,
            speech_model=data.speech_model,
            realtime=data.realtime,
            max_audio_seconds=data.max_audio_seconds,
        )
    except TranscriptionError as exc:
        metric.error = str(exc)
        db.add(metric)
        db.commit()
        db.refresh(metric)
        return metric

    metric.transcript = result.text
    metric.ttft_ms = result.ttft_ms
    metric.total_ms = result.total_ms
    metric.audio_duration_ms = result.audio_duration_ms
    metric.real_time_factor = result.real_time_factor
    metric.word_count = result.word_count
    metric.confidence = result.confidence
    metric.raw = result.raw

    if data.assertions is not None:
        passed, checks = evaluate_assertions(data.assertions, result.text)
        metric.valid = passed
        metric.checks = checks

    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric


@transcription_router.get("/", response_model=ListTranscriptionMetricResponse)
def list_transcription_metrics(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
):
    metrics = (
        db.query(TranscriptionMetric)
        .filter(TranscriptionMetric.user_id == user.id)
        .order_by(TranscriptionMetric.created_at.desc())
        .limit(limit)
        .all()
    )
    return {"metrics": metrics}


@transcription_router.get("/{metric_id}", response_model=TranscriptionMetricResponse)
def get_transcription_metric(
    request: Request,
    metric_id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    metric = (
        db.query(TranscriptionMetric)
        .filter(
            TranscriptionMetric.id == metric_id,
            TranscriptionMetric.user_id == user.id,
        )
        .one_or_none()
    )
    if not metric:
        raise ResourceNotFoundException("Transcription metric")
    return metric
