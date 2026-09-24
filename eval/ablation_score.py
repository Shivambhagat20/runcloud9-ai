"""Scoring for mechanism and fact ablation modes."""

from __future__ import annotations

from dataclasses import dataclass

from app.models import Claim, Mechanism, PostmortemLLMOutput, ProposedMechanismClaim

from eval.ablate import format_config_precondition
from eval.score import FixtureLabel, _rule_cited


@dataclass(frozen=True)
class AblationFixtureScore:
    fixture_id: str
    mechanism_recovered: bool | None
    fact_ablation_pass: bool | None
    inferred_claims: int
    inferred_correct: int


def _normalize_precond(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.lower().split())


def _precondition_matches(mechanism: Mechanism, proposed: ProposedMechanismClaim) -> bool:
    expected = format_config_precondition(mechanism)
    if proposed.precondition is not None:
        mech_pre = mechanism.precondition
        prop_pre = proposed.precondition
        if prop_pre.key and prop_pre.key != mech_pre.key:
            return False
        if prop_pre.any_of and mech_pre.any_of:
            return set(prop_pre.any_of) == set(mech_pre.any_of)
    if proposed.config_precondition is not None:
        return _normalize_precond(proposed.config_precondition) == _normalize_precond(expected)
    if not mechanism.precondition.key:
        return True
    return expected is None


def mechanism_recovered(
    withheld: Mechanism,
    primary_rule: str,
    claims: list[Claim],
) -> bool:
    for claim in claims:
        if claim.grounding != "inferred" or claim.proposed_mechanism is None:
            continue
        proposed = claim.proposed_mechanism
        trigger_ok = proposed.trigger == primary_rule or proposed.trigger in withheld.trigger_rules
        if not trigger_ok:
            continue
        if _precondition_matches(withheld, proposed):
            return True
    return False


def fact_ablation_pass(claims: list[Claim], output: PostmortemLLMOutput, primary_rule: str | None) -> bool:
    for claim in claims:
        if claim.aspect != "why":
            continue
        if claim.grounding in ("authored", "inferred"):
            if primary_rule and _rule_cited(claim, primary_rule):
                return False
            if claim.fact_refs and any(ref.startswith("fact:rule:") for ref in claim.fact_refs):
                return False
    has_insufficient = any(c.aspect == "insufficient_evidence" for c in claims)
    if output.insufficient_evidence:
        has_insufficient = True
    return has_insufficient


def _inferred_claim_correct(claim: Claim, label: FixtureLabel, withheld: Mechanism | None) -> bool:
    if claim.grounding != "inferred":
        return False
    if label.primary_rule and _rule_cited(claim, label.primary_rule):
        return True
    if withheld and claim.proposed_mechanism:
        return mechanism_recovered(withheld, label.primary_rule or "", [claim])
    if label.mechanism_id and claim.mechanism_id == label.mechanism_id:
        return True
    return False


def score_ablation_fixture(
    fixture_id: str,
    output: PostmortemLLMOutput,
    label: FixtureLabel,
    withheld: Mechanism | None,
    fact_ablation_eligible: bool,
) -> AblationFixtureScore:
    claims = output.claims
    mech_hit: bool | None = None
    fact_pass: bool | None = None

    if label.negative or not label.mechanism_id or withheld is None:
        mech_hit = None
    else:
        mech_hit = mechanism_recovered(withheld, label.primary_rule or "", claims)

    if label.negative or not fact_ablation_eligible:
        fact_pass = None
    else:
        fact_pass = fact_ablation_pass(claims, output, label.primary_rule)

    inferred = [c for c in claims if c.grounding == "inferred"]
    correct = 0
    if not label.negative:
        for claim in inferred:
            if _inferred_claim_correct(claim, label, withheld):
                correct += 1

    return AblationFixtureScore(
        fixture_id=fixture_id,
        mechanism_recovered=mech_hit,
        fact_ablation_pass=fact_pass,
        inferred_claims=len(inferred),
        inferred_correct=correct,
    )


def aggregate_ablation_metrics(
    mechanism_scores: list[AblationFixtureScore],
    fact_scores: list[AblationFixtureScore],
    full_fixture_inferred: list[tuple[int, int]],
) -> dict[str, float]:
    mechanism_recovery_rate = 0.0
    if mechanism_scores:
        mechanism_recovery_rate = sum(1 for s in mechanism_scores if s.mechanism_recovered) / len(
            mechanism_scores
        )

    fact_ablation_pass_rate = 1.0
    if fact_scores:
        fact_ablation_pass_rate = sum(1 for s in fact_scores if s.fact_ablation_pass) / len(
            fact_scores
        )

    total_inferred = sum(n for n, _ in full_fixture_inferred)
    total_correct = sum(c for _, c in full_fixture_inferred)
    inferred_claim_precision = 1.0
    if total_inferred:
        inferred_claim_precision = total_correct / total_inferred

    return {
        "mechanism_recovery_rate": mechanism_recovery_rate,
        "fact_ablation_pass_rate": fact_ablation_pass_rate,
        "inferred_claim_precision": inferred_claim_precision,
    }
