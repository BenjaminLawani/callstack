"""Thin async client for the AssemblyAI LLM gateway.

The gateway is OpenAI-compatible; the model list already read from it in
``api/pipelines/endpoints.py`` shares this base URL. Here we call the chat
completions endpoint to actually run an ``llm`` node.
"""

import httpx

from .config import settings

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)

# Chat models the product currently offers. The gateway lists many more, but
# every other model is surfaced as "coming soon" and refused when a node tries
# to run it. Add a name here to turn a model on across the API and frontend.
AVAILABLE_MODELS = {"qwen3.5-4b-32k-fast"}


def is_model_available(model: str) -> bool:
    """True if ``model`` is one the product currently lets pipelines run."""
    return model in AVAILABLE_MODELS


class LLMGatewayError(RuntimeError):
    """Raised when the gateway returns an error or an unexpected payload."""


async def chat_completion(
    model: str,
    messages: list[dict],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """Call the gateway's chat completions endpoint and return the reply text.

    ``messages`` is the OpenAI-style list, e.g.
    ``[{"role": "system", "content": ...}, {"role": "user", "content": ...}]``.
    Raises ``LLMGatewayError`` on transport, HTTP, or shape problems so callers
    can record a clean run error.
    """
    payload: dict = {"model": model, "messages": messages}
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    url = f"{settings.LLM_GATEWAY_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.ASSEMBLYAI_API_KEY}"}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPStatusError as exc:
        raise LLMGatewayError(
            f"gateway returned {exc.response.status_code}: {exc.response.text[:200]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise LLMGatewayError(f"gateway request failed: {exc}") from exc

    try:
        return body["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMGatewayError(f"unexpected gateway response: {body!r}") from exc
