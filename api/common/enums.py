from enum import StrEnum

class LoginMethod(StrEnum):
    LOCAL = "local"
    GOOGLE = "google"

class NodeType(StrEnum):
    LLM = "llm"
    VOICE = "voice"
    ASSERT = "assert"
    FAIL = "fail"