from enum import StrEnum

class LoginMethod(StrEnum):
    LOCAL = "local"
    GOOGLE = "google"

class PipelineNodeType(StrEnum):
    LLM = "llm"
    VOICE = "voice"
    ASSERT = "assert"
    FAIL = "fail"

class RunStatus(StrEnum):
    PENDING = "pending"    # created, not started
    RUNNING = "running"    # execution in progress
    PASSED = "passed"      # pipeline completed / test case assertions all held
    FAILED = "failed"      # a test case assertion (or assert node) did not hold
    ERROR = "error"        # execution blew up (gateway error, bad config, ...)

class TranscriptionMode(StrEnum):
    # Real-time streaming transcription. The only mode that yields a genuine
    # time-to-first-token (the latency from first audio frame sent to the first
    # partial transcript received).
    STREAMING = "streaming"
    # Batch (pre-recorded) transcription. Robust throughput metrics
    # (audio duration, confidence, total latency) but no first-token concept.
    BATCH = "batch"