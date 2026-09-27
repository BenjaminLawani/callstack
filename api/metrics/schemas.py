from datetime import datetime
from typing import List, Optional

from pydantic import (
    BaseModel,
    UUID4,
    ConfigDict,
    Field,
)

from api.common.enums import TranscriptionMode


class TranscribeRequest(BaseModel):
    """Run a one-off transcription and (optionally) validate its transcript.

    This is the standalone tester: point it at an uploaded audio file, say what
    the transcript must contain, and get back the transcript, the latency metrics
    (including time to first token) and a pass/fail verdict.
    """

    audio_url: str
    mode: TranscriptionMode = TranscriptionMode.STREAMING
    speech_model: Optional[str] = None
    realtime: bool = True
    max_audio_seconds: int = Field(default=300, ge=1, le=3600)
    # An assertion spec (see api.common.assertions). Omit to skip validation.
    assertions: Optional[dict] = None


class TranscriptionMetricResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    pipeline_run_id: Optional[UUID4] = None
    node_id: Optional[UUID4] = None
    provider: str
    mode: str
    speech_model: Optional[str] = None
    audio_url: Optional[str] = None
    transcript: Optional[str] = None
    ttft_ms: Optional[int] = None
    total_ms: Optional[int] = None
    audio_duration_ms: Optional[int] = None
    real_time_factor: Optional[float] = None
    word_count: Optional[int] = None
    confidence: Optional[float] = None
    valid: Optional[bool] = None
    checks: List[dict]
    error: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ListTranscriptionMetricResponse(BaseModel):
    metrics: List[TranscriptionMetricResponse]


class AudioUploadRequest(BaseModel):
    content_type: str


class AudioUploadResponse(BaseModel):
    upload_url: str
    key: str
    public_url: str
    expires_in: int
