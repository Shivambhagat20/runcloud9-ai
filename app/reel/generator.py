"""Caption pre-selected highlight rows. Selection stays in Go."""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from app.llm import DEFAULT_MODEL, complete_json_with_usage
from app.models import AIContext, Claim

PROMPT_VERSION = "reel-captions-v1"


def generate_reel_captions(
    context: AIContext,
    highlights: list[dict[str, Any]],
    *,
    complete_fn: Callable[..., Any] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Return Go-shaped reel caption JSON. Empty captions when no API key is set."""
    empty_usage = {"promptTokens": 0, "completionTokens": 0, "totalTokens": 0}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"throughline": "", "captions": [], "usage": empty_usage}

    model_id = model or DEFAULT_MODEL
    complete = complete_fn or complete_json_with_usage
    raw = complete(messages=build_messages(context, highlights), model=model_id)
    content, usage = _split_completion(raw)
    parsed = _parse_payload(content)
    allowed = _highlight_rule_ids(highlights)
    captions = []
    for item in parsed.get("captions") or []:
        if not isinstance(item, dict):
            continue
        rule_id = item.get("ruleId") or item.get("rule_id")
        if not isinstance(rule_id, str) or rule_id not in allowed:
            continue
        claim_raw = item.get("claim")
        if not isinstance(claim_raw, dict):
            continue
        claim = Claim.model_validate(claim_raw)
        captions.append({"ruleId": rule_id, "claim": claim_for_go(claim)})

    throughline = parsed.get("throughline")
    if not isinstance(throughline, str):
        throughline = ""
    return {"throughline": throughline, "captions": captions, "usage": usage}


def build_messages(context: AIContext, highlights: list[dict[str, Any]]) -> list[dict[str, str]]:
    context_json = context.model_dump_json(by_alias=True, exclude_none=True)
    highlights_json = json.dumps(highlights, separators=(",", ":"))
    user = (
        "Session AIContext:\n"
        f"{context_json}\n\n"
        "Highlights already selected (do not add or drop rows; caption these rule ids only):\n"
        f"{highlights_json}\n\n"
        "Respond with JSON only."
    )
    return [{"role": "system", "content": _SYSTEM_PROMPT}, {"role": "user", "content": user}]


def claim_for_go(claim: Claim) -> dict[str, Any]:
    """Serialize a claim with the field names pkg/rules.Claim expects."""
    out: dict[str, Any] = {
        "scope": claim.scope,
        "components": claim.components,
        "aspect": claim.aspect,
        "text": claim.text,
        "fact_refs": claim.fact_refs,
        "grounding": claim.grounding,
    }
    if claim.mechanism_id:
        out["mechanism_id"] = claim.mechanism_id
    if claim.proposed_mechanism is not None:
        pm = claim.proposed_mechanism
        proposed: dict[str, Any] = {
            "trigger": pm.trigger,
            "causal_chain": pm.causal_chain,
        }
        if pm.config_precondition:
            proposed["config_precondition"] = pm.config_precondition
        if pm.precondition is not None:
            proposed["precondition"] = pm.precondition.model_dump(by_alias=True, exclude_none=True)
        out["proposed_mechanism"] = proposed
    if claim.confidence:
        out["confidence"] = claim.confidence
    if claim.observed_gap_seconds is not None:
        out["observed_gap_seconds"] = claim.observed_gap_seconds
    return out


def _highlight_rule_ids(highlights: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for row in highlights:
        rule_id = row.get("ruleId") or row.get("rule_id") or row.get("rule")
        if isinstance(rule_id, str) and rule_id:
            out.add(rule_id)
    return out


def _parse_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        data = json.loads(raw)
    elif isinstance(raw, dict):
        data = raw
    else:
        raise TypeError(f"unexpected LLM payload type: {type(raw)!r}")
    if not isinstance(data, dict):
        raise TypeError("reel caption payload must be an object")
    return data


def _split_completion(raw: Any) -> tuple[Any, dict[str, int]]:
    usage = {"promptTokens": 0, "completionTokens": 0, "totalTokens": 0}
    if isinstance(raw, tuple) and len(raw) == 2:
        content, reported = raw
        if isinstance(reported, dict):
            usage = {
                "promptTokens": int(reported.get("promptTokens") or 0),
                "completionTokens": int(reported.get("completionTokens") or 0),
                "totalTokens": int(reported.get("totalTokens") or 0),
            }
        return content, usage
    return raw, usage


_SYSTEM_PROMPT = """You write short highlight captions for a distributed systems lab session.

Go already chose the highlights. Caption only those rule ids. Do not invent extra highlights.

Output JSON:
{
  "throughline": "one sentence tying the session together",
  "captions": [
    {
      "ruleId": "the highlight ruleId",
      "claim": {
        "scope": "component" | "pair" | "topology",
        "components": ["cache"],
        "aspect": "why",
        "text": "one or two sentences a student can read on a card",
        "factRefs": ["fact refs that exist in the context"],
        "grounding": "authored" | "inferred",
        "mechanismId": "library id when grounding is authored"
      }
    }
  ]
}

Prefer a library mechanism from the context when its trigger fired. Otherwise grounding inferred needs proposedMechanism with trigger, config_precondition, and causalChain.
Every number in text must match a cited fact. If you cannot ground a highlight, omit that caption.
"""
