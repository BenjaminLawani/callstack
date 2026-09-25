from enum import StrEnum

class LoginMethod(StrEnum):
    LOCAL = "local"
    GOOGLE = "google"

class PipelineNodeType(StrEnum):
    LLM = "llm"
    VOICE = "voice"
    ASSERT = "assert"
    FAIL = "fail"