"""Inspector chat generation from AIContext plus prior turns."""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from app.catalog import RulesCatalogClient
from app.llm import DEFAULT_MODEL, complete_json_with_usage
from app.models import AIContext, ChatLLMOutput, ChatResponse, ChatTurn, TokenUsage

PROMPT_VERSION = "chat-v1"


def generate_chat(
    context: AIContext,
    messages: list[ChatTurn],
    catalog_client: RulesCatalogClient,
    *,
    complete_fn: Callable[..., Any] | None = None,
    model: str | None = None,
) -> ChatResponse:
    """Answer one inspector chat turn; skips the LLM when no API key is configured."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return ChatResponse(
            status="skipped",
            reply="Chat requires ANTHROPIC_API_KEY in this environment.",
            claims=[],
            usage=TokenUsage(),
            prompt_version=PROMPT_VERSION,
            model="none",
        )

    catalog = catalog_client.fetch()
    catalog_version = str(catalog.get("catalogVersion") or context.catalog_version)
    prompt_messages = build_messages(context, messages, catalog)
    model_id = model or DEFAULT_MODEL
    complete = complete_fn or complete_json_with_usage
    raw, usage = complete(messages=prompt_messages, model=model_id)
    parsed = parse_llm_payload(raw)
    return ChatResponse(
        status="ok",
        reply=parsed.reply,
        claims=parsed.claims,
        usage=TokenUsage.model_validate(usage),
        prompt_version=PROMPT_VERSION,
        model=model_id,
        catalog_version=catalog_version,
        schema_version=context.schema_version,
    )


def build_messages(
    context: AIContext,
    history: list[ChatTurn],
    rules_catalog: dict[str, Any],
) -> list[dict[str, str]]:
    context_json = context.model_dump_json(by_alias=True, exclude_none=True)
    rules_json = json.dumps(rules_catalog, separators=(",", ":"))
    system = _SYSTEM_PROMPT
    turns: list[dict[str, str]] = [{"role": "system", "content": system}]
    turns.append(
        {
            "role": "user",
            "content": (
                "Session AIContext (refreshed for this turn):\n"
                f"{context_json}\n\n"
                "Rules catalog:\n"
                f"{rules_json}\n\n"
                "Use only facts from the AIContext. Respond with JSON only."
            ),
        }
    )
    for msg in history:
        role = msg.role if msg.role in ("user", "assistant") else "user"
        turns.append({"role": role, "content": msg.content})
    turns.append(
        {
            "role": "user",
            "content": (
                "Reply to the latest student question. Return JSON with keys "
                '"reply" (student-facing prose) and "claims" (structured claims, may be empty).'
            ),
        }
    )
    return turns


def parse_llm_payload(raw: Any) -> ChatLLMOutput:
    if isinstance(raw, str):
        data = json.loads(raw)
    elif isinstance(raw, dict):
        data = raw
    else:
        raise TypeError(f"unexpected LLM payload type: {type(raw)!r}")
    return ChatLLMOutput.model_validate(data)


_SYSTEM_PROMPT = """You are runcloud9-ai, a teaching assistant during a live Cloud9 lab session.

You receive a fresh AIContext each turn: design config, fact ledger, descriptors, violations, mechanism priors, and timeline events.
Answer the student's question using only evidence in that context. Prefer citing RuleID facts and config facts.
When you assert causation, attach structured claims with fact_refs and grounding (authored or inferred).
Keep replies concise and student-readable. If evidence is insufficient, say so in the reply and return no speculative claims.

Respond with JSON: {"reply": "...", "claims": [...]} using the same claim shape as post-mortem output."""
