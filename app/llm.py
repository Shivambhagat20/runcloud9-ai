"""LiteLLM wrapper for runcloud9-ai."""

from __future__ import annotations

import os
from typing import Any

from litellm import completion

DEFAULT_MODEL = os.getenv("BRAIN_MODEL", "anthropic/claude-sonnet-4-20250514")


def _usage_count(usage: Any, name: str) -> int:
    if usage is None:
        return 0
    if isinstance(usage, dict):
        return int(usage.get(name) or 0)
    return int(getattr(usage, name, 0) or 0)


def complete(messages: list[dict[str, str]], **kwargs: Any) -> Any:
    """Call the configured LLM via LiteLLM. Not used in CI contract tests."""
    model = kwargs.pop("model", DEFAULT_MODEL)
    return completion(model=model, messages=messages, **kwargs)


def complete_json(messages: list[dict[str, str]], **kwargs: Any) -> str:
    """Return the assistant message content as a JSON string."""
    content, _usage = complete_json_with_usage(messages, **kwargs)
    return content


def complete_json_with_usage(
    messages: list[dict[str, str]], **kwargs: Any
) -> tuple[str, dict[str, int]]:
    """Return assistant JSON plus token counts for the Go session budget."""
    model = kwargs.pop("model", DEFAULT_MODEL)
    response = completion(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        **kwargs,
    )
    message = response.choices[0].message
    content = message.content
    if content is None:
        raise ValueError("LLM returned empty content")
    usage = getattr(response, "usage", None)
    prompt = _usage_count(usage, "prompt_tokens")
    completion_tokens = _usage_count(usage, "completion_tokens")
    total = _usage_count(usage, "total_tokens")
    if total <= 0:
        total = prompt + completion_tokens
    return content, {
        "promptTokens": prompt,
        "completionTokens": completion_tokens,
        "totalTokens": total,
    }
