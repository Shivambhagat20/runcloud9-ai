"""Offline scoring for post-mortem claims against labelled fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import AIContext, Claim, PostmortemLLMOutput


@dataclass(frozen=True)
class FixtureLabel:
    negative: bool
    primary_rule: str | None
    mechanism_id: str | None
    expects_cross_scope: bool


@dataclass(frozen=True)
class FixtureScore:
    fixture_id: str
    root_cause_hit: bool | None
    citation_valid: bool
    hallucinated_refs: int
    total_refs: int
    negative_abstained: bool | None
    cross_scope_hit: bool | None


def ledger_refs(context: AIContext) -> set[str]:
    refs: set[str] = set()
    for run in context.runs:
        for fact in run.facts:
            refs.add(fact.ref)
    return refs


def fired_rule_ids(context: AIContext) -> set[str]:
    out: set[str] = set()
    for run in context.runs:
        for ev in run.events:
            if not isinstance(ev, dict):
                continue
            rid = ev.get("ruleId") or ev.get("rule_id")
            if isinstance(rid, str) and rid:
                out.add(rid)
    return out


def _rule_cited(claim: Claim, rule_id: str) -> bool:
    target = f"fact:rule:{rule_id}"
    return any(ref == target or ref.endswith(f":{rule_id}") for ref in claim.fact_refs)


def _root_cause_hit(claims: list[Claim], label: FixtureLabel) -> bool:
    if label.primary_rule is None:
        return False
    for claim in claims:
        if claim.mechanism_id == label.mechanism_id:
            return True
        if _rule_cited(claim, label.primary_rule):
            return True
    return False


def _negative_abstained(claims: list[Claim]) -> bool:
    if not claims:
        return True
    for claim in claims:
        if claim.aspect == "insufficient_evidence":
            continue
        if claim.grounding == "abstained":
            continue
        if claim.aspect == "why" and claim.fact_refs:
            return False
        if any(ref.startswith("fact:rule:") for ref in claim.fact_refs):
            return False
    return True


def _cross_scope_hit(claims: list[Claim]) -> bool:
    for claim in claims:
        if claim.scope in ("pair", "topology"):
            return True
    return False


def score_fixture(
    fixture_id: str,
    context: AIContext,
    output: PostmortemLLMOutput,
    label: FixtureLabel,
) -> FixtureScore:
    claims = output.claims
    valid_refs = ledger_refs(context)
    hallucinated = 0
    total_refs = 0
    for claim in claims:
        for ref in claim.fact_refs:
            total_refs += 1
            if ref not in valid_refs:
                hallucinated += 1
    citation_valid = hallucinated == 0

    root_hit: bool | None = None
    neg_abstain: bool | None = None
    cross_hit: bool | None = None

    if label.negative:
        neg_abstain = _negative_abstained(claims)
    else:
        root_hit = _root_cause_hit(claims, label)
        if label.expects_cross_scope:
            cross_hit = _cross_scope_hit(claims)

    return FixtureScore(
        fixture_id=fixture_id,
        root_cause_hit=root_hit,
        citation_valid=citation_valid,
        hallucinated_refs=hallucinated,
        total_refs=total_refs,
        negative_abstained=neg_abstain,
        cross_scope_hit=cross_hit,
    )


def aggregate_metrics(scores: list[FixtureScore], labels: dict[str, FixtureLabel]) -> dict[str, float]:
    positive = [s for s in scores if not labels[s.fixture_id].negative]
    negative = [s for s in scores if labels[s.fixture_id].negative]
    cross_scope = [s for s in scores if labels[s.fixture_id].expects_cross_scope]

    root_acc = 0.0
    if positive:
        hits = sum(1 for s in positive if s.root_cause_hit)
        root_acc = hits / len(positive)

    total_refs = sum(s.total_refs for s in scores)
    hallucinated = sum(s.hallucinated_refs for s in scores)
    hallucinated_rate = (hallucinated / total_refs) if total_refs else 0.0

    citation_validity = 0.0
    if scores:
        citation_validity = sum(1 for s in scores if s.citation_valid) / len(scores)

    negative_abstention = 0.0
    if negative:
        negative_abstention = sum(1 for s in negative if s.negative_abstained) / len(negative)

    cross_scope_coverage = 0.0
    if cross_scope:
        cross_scope_coverage = sum(1 for s in cross_scope if s.cross_scope_hit) / len(cross_scope)

    return {
        "root_cause_accuracy": root_acc,
        "citation_validity": citation_validity,
        "hallucinated_fact_rate": hallucinated_rate,
        "negative_abstention": negative_abstention,
        "cross_scope_coverage": cross_scope_coverage,
    }


def load_labels(raw: dict[str, Any]) -> dict[str, FixtureLabel]:
    fixtures = raw.get("fixtures", {})
    out: dict[str, FixtureLabel] = {}
    for fixture_id, spec in fixtures.items():
        out[fixture_id] = FixtureLabel(
            negative=bool(spec.get("negative")),
            primary_rule=spec.get("primary_rule"),
            mechanism_id=spec.get("mechanism_id"),
            expects_cross_scope=bool(spec.get("expects_cross_scope")),
        )
    return out
