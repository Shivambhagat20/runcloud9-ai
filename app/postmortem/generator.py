"""Build prompts and parse structured post-mortem output."""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from app.catalog import RulesCatalogClient
from app.llm import DEFAULT_MODEL, complete_json
from app.models import AIContext, PostmortemLLMOutput, PostmortemResponse

PROMPT_VERSION = "postmortem-v1"


def generate_postmortem(
    context: AIContext,
    catalog_client: RulesCatalogClient,
    *,
    complete_fn: Callable[..., Any] | None = None,
    model: str | None = None,
) -> PostmortemResponse:
    """Run post-mortem generation; skips the LLM when no API key is configured."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return PostmortemResponse(
            status="skipped",
            claims=[],
            summary="Post-mortem generation requires ANTHROPIC_API_KEY.",
            schema_version=context.schema_version,
            catalog_version=context.catalog_version,
            prompt_version=PROMPT_VERSION,
            model="none",
        )

    catalog = catalog_client.fetch()
    catalog_version = str(catalog.get("catalogVersion") or context.catalog_version)
    messages = build_messages(context, catalog)
    model_id = model or DEFAULT_MODEL
    complete = complete_fn or complete_json
    raw = complete(messages=messages, model=model_id)
    parsed = parse_llm_payload(raw)
    return PostmortemResponse(
        status="ok",
        claims=parsed.claims,
        summary=parsed.summary,
        insufficient_evidence=parsed.insufficient_evidence,
        schema_version=context.schema_version,
        catalog_version=catalog_version,
        prompt_version=PROMPT_VERSION,
        model=model_id,
    )


def build_messages(context: AIContext, rules_catalog: dict[str, Any]) -> list[dict[str, str]]:
    context_json = context.model_dump_json(by_alias=True, exclude_none=True)
    rules_json = json.dumps(rules_catalog, separators=(",", ":"))
    system = _SYSTEM_PROMPT
    user = (
        "Session AIContext (facts, mechanisms, events):\n"
        f"{context_json}\n\n"
        "Rules catalog (cite only rules that appear in this session's facts/events):\n"
        f"{rules_json}\n\n"
        "Respond with JSON only."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_llm_payload(raw: Any) -> PostmortemLLMOutput:
    if isinstance(raw, str):
        data = json.loads(raw)
    elif isinstance(raw, dict):
        data = raw
    else:
        raise TypeError(f"unexpected LLM payload type: {type(raw)!r}")
    return PostmortemLLMOutput.model_validate(data)


_SYSTEM_PROMPT = """You are runcloud9-ai, a post-mortem analyst for distributed systems lab sessions.

You receive a session AIContext: design config, fact ledger, signal descriptors, violations, optional library mechanisms, and timeline events.

Output JSON with this shape:
{
  "claims": [ ... ],
  "summary": "short session through-line for the student",
  "insufficient_evidence": [ "optional notes on what evidence would settle open questions" ]
}

Each claim object:
- scope: "component" | "pair" | "topology"
- components: string array of component roles
- aspect: "what" | "why" | "how" | "insufficient_evidence"
- text: grounded prose; every number must match a cited fact
- fact_refs: array of fact ref strings from the ledger (required unless aspect is insufficient_evidence)
- grounding: "authored" | "inferred" | "abstained"
- mechanism_id: set when grounding is authored and a library mechanism fits
- proposed_mechanism: required when grounding is inferred (trigger, config_precondition, causal_chain)
- confidence: "high" | "medium" | "low" (optional)
- observed_gap_seconds: optional float when asserting timing between events

Rules:
1. Prefer library mechanisms from AIContext.mechanisms when their trigger rules fired and preconditions match the design. Set grounding to authored and mechanism_id to that library id.
2. When no library mechanism fits but the facts support a causal story, use grounding inferred with proposed_mechanism. Do not invent fact_refs; only cite refs present in the context.
3. When evidence is too weak, emit aspect insufficient_evidence or grounding abstained rather than guessing.
4. insufficient_evidence in the top-level array names signals or facts that would settle ambiguity.
5. Do not cite rules that did not fire in this session.
"""
