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
