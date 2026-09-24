"""Offline ablation eval: mechanism withholding and chaos-anchor removal."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.models import PostmortemLLMOutput

from eval.ablate import find_mechanism, strip_chaos_anchor, strip_mechanism
from eval.ablation_score import AblationFixtureScore, aggregate_ablation_metrics, score_ablation_fixture
from eval.run import compare_baseline, load_fixture, load_golden
from eval.score import load_labels

REPO_ROOT = Path(__file__).resolve().parent.parent
LABELS_PATH = Path(__file__).resolve().parent / "labels.json"
BASELINE_PATH = Path(__file__).resolve().parent / "ablation_baseline.json"
GOLDEN_MECHANISM = Path(__file__).resolve().parent / "golden_ablation" / "mechanism"
GOLDEN_FACT = Path(__file__).resolve().parent / "golden_ablation" / "fact"
FULL_GOLDEN = Path(__file__).resolve().parent / "golden"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score ablation modes against golden outputs.")
    parser.add_argument("--labels", type=Path, default=LABELS_PATH)
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument("--report", type=Path, default=REPO_ROOT / "eval" / "ablation_report.json")
    parser.add_argument("--tolerance", type=float, default=0.001)
    args = parser.parse_args(argv)

    labels_raw = json.loads(args.labels.read_text(encoding="utf-8"))
    labels = load_labels(labels_raw)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))

    mechanism_scores: list[AblationFixtureScore] = []
    fact_scores: list[AblationFixtureScore] = []
    full_inferred: list[tuple[int, int]] = []
    per_fixture: dict[str, dict[str, object]] = {}

    for fixture_id in sorted(labels.keys()):
        label = labels[fixture_id]
        context = load_fixture(fixture_id)
        withheld = find_mechanism(context, label.mechanism_id) if label.mechanism_id else None

        full_output = load_golden(FULL_GOLDEN, fixture_id)
        full_scored = score_ablation_fixture(
            fixture_id, full_output, label, withheld, fact_ablation_eligible=False
        )
        full_inferred.append((full_scored.inferred_claims, full_scored.inferred_correct))

        mech_recovered: bool | None = None
        fact_pass: bool | None = None
        removed = 0

        if not label.negative and label.mechanism_id and withheld is not None:
            strip_mechanism(context, label.mechanism_id)
            mech_output = PostmortemLLMOutput.model_validate(
                json.loads((GOLDEN_MECHANISM / f"{fixture_id}.json").read_text(encoding="utf-8"))
            )
            mech_scored = score_ablation_fixture(
                fixture_id, mech_output, label, withheld, fact_ablation_eligible=False
            )
            mechanism_scores.append(mech_scored)
            mech_recovered = mech_scored.mechanism_recovered

        if not label.negative:
            _, removed = strip_chaos_anchor(context, fixture_id)
            if removed > 0:
                fact_output = PostmortemLLMOutput.model_validate(
                    json.loads((GOLDEN_FACT / f"{fixture_id}.json").read_text(encoding="utf-8"))
                )
                fact_scored = score_ablation_fixture(
                    fixture_id, fact_output, label, withheld, fact_ablation_eligible=True
                )
                fact_scores.append(fact_scored)
                fact_pass = fact_scored.fact_ablation_pass

        per_fixture[fixture_id] = {
            "mechanism_recovered": mech_recovered,
            "fact_ablation_pass": fact_pass,
            "chaos_anchor_removed": removed,
        }

    metrics = aggregate_ablation_metrics(mechanism_scores, fact_scores, full_inferred)
    report = {
        "version": baseline.get("version", 1),
        "prompt_version": baseline.get("prompt_version", "postmortem-v1"),
        "metrics": metrics,
        "fixtures": per_fixture,
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    failures = compare_baseline(metrics, baseline, args.tolerance)
    if failures:
        for line in failures:
            print(line, file=sys.stderr)
        return 1
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
