"""Transform AIContext payloads for offline ablation eval."""

from __future__ import annotations

from typing import Any

from app.models import AIContext, Mechanism


def find_mechanism(context: AIContext, mechanism_id: str) -> Mechanism | None:
    for run in context.runs:
        if not run.mechanisms:
            continue
        for mechanism in run.mechanisms:
            if mechanism.id == mechanism_id:
                return mechanism
    return None


def strip_mechanism(context: AIContext, mechanism_id: str) -> AIContext:
    data = context.model_dump(by_alias=True)
    for run in data.get("runs", []):
        mechanisms = run.get("mechanisms")
        if mechanisms:
            run["mechanisms"] = [m for m in mechanisms if m.get("id") != mechanism_id]
    return AIContext.model_validate(data)


def _event_is_chaos_anchor(event: dict[str, Any], chaos_scenario: str | None) -> bool:
    if event.get("kind") == "chaos_inject":
        return True
    detail = event.get("detail")
    if isinstance(detail, dict):
        scenario = detail.get("scenario")
        if chaos_scenario and scenario == chaos_scenario:
            return True
    scenario = event.get("scenario")
    if chaos_scenario and scenario == chaos_scenario:
        return True
    return False


def _fact_is_chaos_anchor(fact: dict[str, Any], chaos_scenario: str | None) -> bool:
    value = fact.get("value")
    if not isinstance(value, dict):
        return False
    if value.get("kind") == "chaos_inject":
        return True
    detail = value.get("detail")
    if isinstance(detail, dict):
        scenario = detail.get("scenario")
        if chaos_scenario and scenario == chaos_scenario:
            return True
    scenario = value.get("scenario")
    if chaos_scenario and scenario == chaos_scenario:
        return True
    return False


def strip_chaos_anchor(context: AIContext, chaos_scenario: str | None) -> tuple[AIContext, int]:
    """Remove chaos-inject facts and matching session events. Returns (context, removed_count)."""
    data = context.model_dump(by_alias=True)
    removed = 0
    for run in data.get("runs", []):
        facts = run.get("facts", [])
        kept_facts: list[dict[str, Any]] = []
        for fact in facts:
            if _fact_is_chaos_anchor(fact, chaos_scenario):
                removed += 1
                continue
            kept_facts.append(fact)
        run["facts"] = kept_facts

        events = run.get("events", [])
        kept_events: list[dict[str, Any]] = []
        for event in events:
            if _event_is_chaos_anchor(event, chaos_scenario):
                removed += 1
                continue
            kept_events.append(event)
        run["events"] = kept_events

    return AIContext.model_validate(data), removed


def format_config_precondition(mechanism: Mechanism) -> str | None:
    pre = mechanism.precondition
    if not pre.key:
        return None
    if pre.any_of:
        values = ", ".join(pre.any_of)
        role = pre.role or ""
        prefix = f"{role}." if role else ""
        return f"{prefix}{pre.key} in ({values})"
    return f"{pre.key}"
