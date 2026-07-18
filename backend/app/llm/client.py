"""Ollama client. All extraction goes through `structured()` — JSON-schema
constrained decoding with one validation/repair retry — so mid-size local
models return parseable output reliably. Free-text generation (`draft()`)
is reserved for human-reviewed drafting."""

from __future__ import annotations

import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from ..config import settings

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


def _chat(model: str, messages: list[dict], fmt: dict | None = None,
          temperature: float = 0.1) -> str:
    body: dict = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if fmt is not None:
        body["format"] = fmt
    try:
        r = httpx.post(f"{settings.ollama_url}/api/chat", json=body,
                       timeout=settings.llm_timeout_s)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise LLMError(f"Ollama request failed: {e}") from e
    return r.json()["message"]["content"]


def structured(schema: type[T], system: str, user: str,
               model: str | None = None) -> T:
    model = model or settings.model_primary
    fmt = schema.model_json_schema()
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
    raw = _chat(model, messages, fmt=fmt)
    for attempt in range(2):
        try:
            return schema.model_validate_json(raw)
        except ValidationError as e:
            if attempt == 1:
                raise LLMError(f"schema validation failed twice: {e}") from e
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content":
                    f"That JSON failed validation: {e}. Return corrected JSON only."},
            ]
            raw = _chat(model, messages, fmt=fmt)
    raise LLMError("unreachable")


def draft(system: str, user: str, model: str | None = None,
          temperature: float = 0.4) -> str:
    return _chat(model or settings.model_primary,
                 [{"role": "system", "content": system},
                  {"role": "user", "content": user}],
                 temperature=temperature)


def embed(texts: list[str]) -> list[list[float]]:
    r = httpx.post(f"{settings.ollama_url}/api/embed",
                   json={"model": settings.model_embed, "input": texts},
                   timeout=settings.llm_timeout_s)
    r.raise_for_status()
    return r.json()["embeddings"]


def status() -> dict:
    """Health info: is Ollama up, which required models are present."""
    required = {settings.model_primary, settings.model_fast, settings.model_embed}
    try:
        r = httpx.get(f"{settings.ollama_url}/api/tags", timeout=5)
        r.raise_for_status()
        have = {m["name"] for m in r.json().get("models", [])}
        have |= {n.split(":")[0] for n in have}
        missing = [m for m in required
                   if m not in have and m.split(":")[0] not in have]
        return {"ollama": "up", "missing_models": missing}
    except httpx.HTTPError:
        return {"ollama": "down", "missing_models": sorted(required)}


def json_dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
