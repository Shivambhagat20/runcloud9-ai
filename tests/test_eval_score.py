"""Unit tests for offline post-mortem eval scoring."""

from __future__ import annotations

import json
from pathlib import Path

from app.models import AIContext, Claim, PostmortemLLMOutput
from eval.score import FixtureLabel, aggregate_metrics, load_labels, score_fixture

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
LABELS_PATH = Path(__file__).resolve().parent.parent / "eval" / "labels.json"


def _load_context(name: str) -> AIContext:
    raw = json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return AIContext.model_validate(raw)


def test_score_fixture_detects_hallucinated_ref() -> None:
    ctx = _load_context("cache_flush")
    label = FixtureLabel(
        negative=False,
        primary_rule="cascade_cache_db",
        mechanism_id="cascade_cache_db_fallthrough",
        expects_cross_scope=True,
    )
    output = PostmortemLLMOutput(
        claims=[
            Claim(
                scope="pair",
                aspect="why",
                text="Bad cite",
                fact_refs=["fact:missing:ref"],
                grounding="inferred",
            )
        ],
        summary="x",
    )
    scored = score_fixture("cache_flush", ctx, output, label)
    assert scored.citation_valid is False
    assert scored.hallucinated_refs == 1


def test_aggregate_metrics_from_golden_dir() -> None:
    labels = load_labels(json.loads(LABELS_PATH.read_text(encoding="utf-8")))
    golden_dir = Path(__file__).resolve().parent.parent / "eval" / "golden"
    scores = []
    for fixture_id in labels:
        ctx = _load_context(fixture_id)
        golden = json.loads((golden_dir / f"{fixture_id}.json").read_text(encoding="utf-8"))
        output = PostmortemLLMOutput.model_validate(golden)
        scores.append(score_fixture(fixture_id, ctx, output, labels[fixture_id]))
    metrics = aggregate_metrics(scores, labels)
    assert metrics["root_cause_accuracy"] == 1.0
    assert metrics["citation_validity"] == 1.0
    assert metrics["hallucinated_fact_rate"] == 0.0
    assert metrics["negative_abstention"] == 1.0
    assert metrics["cross_scope_coverage"] == 1.0


def test_clean_negative_abstention() -> None:
    ctx = _load_context("clean")
    label = FixtureLabel(negative=True, primary_rule=None, mechanism_id=None, expects_cross_scope=False)
    output = PostmortemLLMOutput(claims=[], summary="steady")
    scored = score_fixture("clean", ctx, output, label)
    assert scored.negative_abstained is True
