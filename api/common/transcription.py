"""AssemblyAI transcription with latency metrics.

This is the engine behind ``voice`` pipeline nodes and the standalone
transcription tester. Two modes:

``streaming``
    Decodes the audio to 16 kHz mono PCM (via ffmpeg) and feeds it to the
    AssemblyAI v3 streaming API. This is the only mode that produces a genuine
    **time to first token** (``ttft_ms``): the wall-clock latency from the first
    audio frame we send to the first non-empty partial transcript we receive —
    the number that matters when you are benchmarking a voice agent.

``batch``
    Submits the audio URL to AssemblyAI's pre-recorded transcript API and polls
    to completion. No first-token concept (the transcript arrives all at once),
    but it reports audio duration, confidence and total latency, and is the
    robust choice for long files.

Both return a :class:`TranscriptionResult`. Failures raise
:class:`TranscriptionError` so callers can record a clean run error.

Audio is referenced by URL. ffmpeg (streaming) and AssemblyAI (batch) both fetch
it directly, so the URL must be publicly reachable — the R2 public URLs minted by
``api.common.storage`` are.
"""

import asyncio
import time
from dataclasses import dataclass, field

import httpx

from .config import settings
from .enums import TranscriptionMode

# 16 kHz mono signed 16-bit little-endian PCM: what the streaming API expects and
# what we ask ffmpeg to produce. 2 bytes/sample * 16000 samples/s = 32000 B/s.
_SAMPLE_RATE = 16000
_BYTES_PER_SECOND = _SAMPLE_RATE * 2
_FRAME_MS = 50
_FRAME_BYTES = int(_BYTES_PER_SECOND * _FRAME_MS / 1000)  # 1600 bytes / 50 ms

_DEFAULT_MAX_AUDIO_SECONDS = 300

_AAI_BASE_URL = "https://api.assemblyai.com/v2"
_BATCH_POLL_INTERVAL = 1.0  # seconds between transcript status polls
_BATCH_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_BATCH_MAX_WAIT = 600.0  # give up polling after 10 minutes


# Curated catalogue of AssemblyAI speech ("voice") models a voice node can use as
# its ``speech_model``. Unlike the LLM gateway (``/v1/models``), AssemblyAI has no
# REST endpoint that enumerates its speech-to-text models, so this list is the
# single source of truth — edit it here when AssemblyAI changes its lineup and the
# voice-node dropdown updates automatically.
# Docs: https://www.assemblyai.com/docs/getting-started/models
VOICE_MODELS: list[dict] = [
    {
        "name": "universal-3.5-pro",
        "label": "Universal 3.5 Pro",
        "description": "Highest accuracy and fastest; 18 languages with native code-switching.",
        "languages": "18 languages",
    },
    {
        "name": "universal-2",
        "label": "Universal 2",
        "description": "Accurate, cost-effective transcription across 99 languages.",
        "languages": "99 languages",
    },
    {
        "name": "slam-1",
        "label": "Slam-1",
        "description": "Prompt-based speech language model; English only, most steerable.",
        "languages": "English",
    },
]


class TranscriptionError(RuntimeError):
    """Transcription could not be produced (decode, network, or provider error)."""


@dataclass
class TranscriptionResult:
    """The transcript plus the metrics a voice pipeline cares about."""

    text: str
    mode: str
    total_ms: int
    ttft_ms: int | None = None
    audio_duration_ms: int | None = None
    real_time_factor: float | None = None
    word_count: int = 0
    confidence: float | None = None
    raw: dict = field(default_factory=dict)

    def metrics(self) -> dict:
        """A JSON-serialisable metrics dict for run results / API responses."""
        return {
            "mode": self.mode,
            "ttft_ms": self.ttft_ms,
            "total_ms": self.total_ms,
            "audio_duration_ms": self.audio_duration_ms,
            "real_time_factor": self.real_time_factor,
            "word_count": self.word_count,
            "confidence": self.confidence,
        }


async def transcribe(
    audio_url: str,
    *,
    mode: TranscriptionMode | str = TranscriptionMode.STREAMING,
    speech_model: str | None = None,
    realtime: bool = True,
    max_audio_seconds: int = _DEFAULT_MAX_AUDIO_SECONDS,
) -> TranscriptionResult:
    """Transcribe ``audio_url`` and return the transcript with latency metrics."""
    if not audio_url:
        raise TranscriptionError("no audio_url provided")

    mode = TranscriptionMode(mode)
    if mode is TranscriptionMode.STREAMING:
        return await _transcribe_streaming(
            audio_url,
            speech_model=speech_model,
            realtime=realtime,
            max_audio_seconds=max_audio_seconds,
        )
    return await _transcribe_batch(audio_url, speech_model=speech_model)


def transcribe_kwargs_from_config(config: dict) -> dict:
    """Extract transcription kwargs from a ``voice`` node's config dict."""
    config = config or {}
    kwargs: dict = {
        "mode": config.get("mode", TranscriptionMode.STREAMING),
        "speech_model": config.get("speech_model"),
    }
    if "realtime" in config:
        kwargs["realtime"] = bool(config["realtime"])
    if "max_audio_seconds" in config:
        kwargs["max_audio_seconds"] = int(config["max_audio_seconds"])
    return kwargs


# --------------------------------------------------------------------------- #
# Streaming (true time-to-first-token)
# --------------------------------------------------------------------------- #


async def _decode_to_pcm(audio_url: str, max_audio_seconds: int) -> bytes:
    """Decode any audio at ``audio_url`` to raw 16 kHz mono PCM via ffmpeg.

    ffmpeg fetches the URL itself. The output is capped at ``max_audio_seconds``
    so a huge file can't make a streaming run take forever.
    """
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel", "error",
        "-i", audio_url,
        "-t", str(max_audio_seconds),
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "-ar", str(_SAMPLE_RATE),
        "-ac", "1",
        "pipe:1",
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise TranscriptionError(
            "ffmpeg is required for streaming transcription but was not found"
        ) from exc

    pcm, stderr = await proc.communicate()
    if proc.returncode != 0:
        detail = stderr.decode("utf-8", "replace").strip()[:300]
        raise TranscriptionError(f"could not decode audio: {detail or 'ffmpeg failed'}")
    if not pcm:
        raise TranscriptionError("decoded audio was empty")
    return pcm


async def _transcribe_streaming(
    audio_url: str,
    *,
    speech_model: str | None,
    realtime: bool,
    max_audio_seconds: int,
) -> TranscriptionResult:
    # Imported lazily: the SDK pulls in websockets and is only needed here.
    from assemblyai.streaming.v3 import (
        AsyncStreamingClient,
        Encoding,
        StreamingClientOptions,
        StreamingError,
        StreamingEvents,
        StreamingParameters,
        TurnEvent,
    )

    pcm = await _decode_to_pcm(audio_url, max_audio_seconds)
    audio_duration_ms = round(len(pcm) / _BYTES_PER_SECOND * 1000)

    # Shared, mutable state written by the read task's handlers and read here.
    state: dict = {
        "t0": None,          # perf_counter at first frame sent
        "ttft": None,        # seconds to first non-empty transcript
        "turns": {},         # turn_order -> best transcript so far
        "confidences": {},   # turn_order -> end_of_turn_confidence (deduped)
        "error": None,
    }

    def _on_turn(_client, event: TurnEvent) -> None:
        transcript = (event.transcript or "").strip()
        if transcript and state["ttft"] is None and state["t0"] is not None:
            state["ttft"] = time.perf_counter() - state["t0"]
        if event.end_of_turn and transcript:
            # A later formatted event for the same turn supersedes the raw one.
            existing = state["turns"].get(event.turn_order)
            if existing is None or event.turn_is_formatted:
                state["turns"][event.turn_order] = transcript
            # One confidence per turn, whichever end-of-turn event carries it.
            state["confidences"].setdefault(
                event.turn_order, event.end_of_turn_confidence
            )

    def _on_error(_client, error: "StreamingError") -> None:
        state["error"] = str(error)

    client = AsyncStreamingClient(
        StreamingClientOptions(api_key=settings.ASSEMBLYAI_API_KEY)
    )
    client.on(StreamingEvents.Turn, _on_turn)
    client.on(StreamingEvents.Error, _on_error)

    params = StreamingParameters(
        sample_rate=_SAMPLE_RATE,
        encoding=Encoding.pcm_s16le,
        format_turns=True,
    )
    if speech_model:
        params.speech_model = speech_model

    async def _frames():
        for offset in range(0, len(pcm), _FRAME_BYTES):
            if state["t0"] is None:
                state["t0"] = time.perf_counter()
            yield pcm[offset:offset + _FRAME_BYTES]
            if realtime:
                await asyncio.sleep(_FRAME_MS / 1000)

    try:
        await client.connect(params)
    except Exception as exc:  # noqa: BLE001 - surface any connect failure cleanly
        raise TranscriptionError(f"could not connect to streaming API: {exc}") from exc

    try:
        await client.stream(_frames())
    finally:
        try:
            await client.disconnect(terminate=True)
        except Exception:  # noqa: BLE001 - disconnect best-effort; keep results
            pass

    total_ms = (
        round((time.perf_counter() - state["t0"]) * 1000)
        if state["t0"] is not None
        else 0
    )

    text = " ".join(state["turns"][k] for k in sorted(state["turns"]))
    if not text and state["error"]:
        raise TranscriptionError(f"streaming transcription failed: {state['error']}")

    confidences = list(state["confidences"].values())
    confidence = round(sum(confidences) / len(confidences), 4) if confidences else None
    ttft_ms = round(state["ttft"] * 1000) if state["ttft"] is not None else None
    rtf = round(total_ms / audio_duration_ms, 3) if audio_duration_ms else None

    return TranscriptionResult(
        text=text,
        mode=TranscriptionMode.STREAMING.value,
        total_ms=total_ms,
        ttft_ms=ttft_ms,
        audio_duration_ms=audio_duration_ms,
        real_time_factor=rtf,
        word_count=len(text.split()),
        confidence=confidence,
        raw={"turns": len(state["turns"]), "streaming_error": state["error"]},
    )


# --------------------------------------------------------------------------- #
# Batch (pre-recorded)
# --------------------------------------------------------------------------- #


async def _transcribe_batch(
    audio_url: str,
    *,
    speech_model: str | None,
) -> TranscriptionResult:
    headers = {"Authorization": settings.ASSEMBLYAI_API_KEY}
    payload: dict = {"audio_url": audio_url}
    if speech_model:
        payload["speech_model"] = speech_model

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=_BATCH_TIMEOUT) as client:
            create = await client.post(
                f"{_AAI_BASE_URL}/transcript", json=payload, headers=headers
            )
            create.raise_for_status()
            transcript_id = create.json()["id"]

            body = await _poll_batch(client, transcript_id, headers)
    except httpx.HTTPStatusError as exc:
        raise TranscriptionError(
            f"AssemblyAI returned {exc.response.status_code}: {exc.response.text[:200]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise TranscriptionError(f"AssemblyAI request failed: {exc}") from exc
    except (KeyError, TypeError) as exc:
        raise TranscriptionError("unexpected AssemblyAI response shape") from exc

    total_ms = round((time.perf_counter() - started) * 1000)

    if body.get("status") == "error":
        raise TranscriptionError(f"transcription failed: {body.get('error')}")

    text = (body.get("text") or "").strip()
    duration_s = body.get("audio_duration")
    audio_duration_ms = round(duration_s * 1000) if duration_s else None
    rtf = round(total_ms / audio_duration_ms, 3) if audio_duration_ms else None
    words = body.get("words") or []

    return TranscriptionResult(
        text=text,
        mode=TranscriptionMode.BATCH.value,
        total_ms=total_ms,
        ttft_ms=None,  # batch has no streaming first-token
        audio_duration_ms=audio_duration_ms,
        real_time_factor=rtf,
        word_count=len(words) if words else len(text.split()),
        confidence=body.get("confidence"),
        raw={"transcript_id": body.get("id")},
    )


async def _poll_batch(client: httpx.AsyncClient, transcript_id: str, headers: dict) -> dict:
    deadline = time.monotonic() + _BATCH_MAX_WAIT
    url = f"{_AAI_BASE_URL}/transcript/{transcript_id}"
    while True:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        body = response.json()
        if body.get("status") in ("completed", "error"):
            return body
        if time.monotonic() > deadline:
            raise TranscriptionError("transcription timed out")
        await asyncio.sleep(_BATCH_POLL_INTERVAL)
