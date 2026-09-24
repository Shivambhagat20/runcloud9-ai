"""Unit tests for ablation scoring and context transforms."""

from __future__ import annotations

import json
from pathlib import Path

from app.models import Claim, PostmortemLLMOutput, ProposedMechanismClaim
from eval.ablate import find_mechanism, strip_chaos_anchor, strip_mechanism
from eval.ablation_score import fact_ablation_pass, mechanism_recovered
from eval.run import load_fixture
from eval.score import FixtureLabel, load_labels

LABELS_PATH = Path(__file__).resolve().parent.parent / "eval" / "labels.json"
GOLDEN_MECH = Path(__file__).resolve().parent.parent / "eval" / "golden_ablation" / "mechanism"


def test_strip_mechanism_removes_library_row() -> None:
    ctx = load_fixture("cache_flush")
    stripped = strip_mechanism(ctx, "cascade_cache_db_fallthrough")
    mech = find_mechanism(stripped, "cascade_cache_db_fallthrough")
    assert mech is None
    assert find_mechanism(ctx, "cascade_cache_db_fallthrough") is not None


def test_strip_chaos_anchor_promote_lagging() -> None:
    ctx = load_fixture("promote_lagging_replica")
    stripped, removed = strip_chaos_anchor(ctx, "promote_lagging_replica")
    assert removed >= 1
    refs = {f.ref for run in stripped.runs for f in run.facts}
    assert not any("promote_lagging_replica" in str(f.value) for run in stripped.runs for f in run.facts)


def test_mechanism_golden_recover_all_positive() -> None:
    labels = load_labels(json.loads(LABELS_PATH.read_text(encoding="utf-8")))
    for fixture_id, label in labels.items():
        if label.negative or not label.mechanism_id:
            continue
        ctx = load_fixture(fixture_id)
        withheld = find_mechanism(ctx, label.mechanism_id)
        assert withheld is not None
        raw = json.loads((GOLDEN_MECH / f"{fixture_id}.json").read_text(encoding="utf-8"))
        output = PostmortemLLMOutput.model_validate(raw)
        assert mechanism_recovered(withheld, label.primary_rule or "", output.claims)


def test_fact_ablation_rejects_confident_why() -> None:
    output = PostmortemLLMOutput(
        claims=[
            Claim(
                scope="component",
                aspect="why",
                text="Sure it was failover.",
                fact_refs=["fact:rule:failover_write_loss"],
                grounding="inferred",
            )
        ],
        summary="x",
    )
    assert fact_ablation_pass(output.claims, output, "failover_write_loss") is False


def test_fact_ablation_accepts_insufficient_evidence() -> None:
    output = PostmortemLLMOutput(
        claims=[
            Claim(
                scope="topology",
                aspect="insufficient_evidence",
                text="Need chaos timing.",
                fact_refs=[],
                grounding="abstained",
            )
        ],
        summary="x",
        insufficient_evidence=["chaos_inject"],
    )
    assert fact_ablation_pass(output.claims, output, "failover_write_loss") is True
