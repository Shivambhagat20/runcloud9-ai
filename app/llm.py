"""LiteLLM wrapper for runcloud9-ai."""

from __future__ import annotations

import os
from typing import Any

from litellm import completion

DEFAULT_MODEL = os.getenv("BRAIN_MODEL", "anthropic/claude-sonnet-4-20250514")


def complete(messages: list[dict[str, str]], **kwargs: Any) -> Any:
    """Call the configured LLM via LiteLLM. Not used in CI contract tests."""
    model = kwargs.pop("model", DEFAULT_MODEL)
    return completion(model=model, messages=messages, **kwargs)


def complete_json(messages: list[dict[str, str]], **kwargs: Any) -> str:
    """Return the assistant message content as a JSON string."""
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
    return content
