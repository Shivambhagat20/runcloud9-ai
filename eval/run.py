"""Run offline eval against golden post-mortem outputs and compare to baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.models import AIContext, PostmortemLLMOutput

from eval.score import aggregate_metrics, load_labels, score_fixture

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"
LABELS_PATH = Path(__file__).resolve().parent / "labels.json"
BASELINE_PATH = Path(__file__).resolve().parent / "baseline.json"
DEFAULT_GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def load_fixture(fixture_id: str) -> AIContext:
    path = FIXTURES_DIR / f"{fixture_id}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return AIContext.model_validate(raw)


def load_golden(golden_dir: Path, fixture_id: str) -> PostmortemLLMOutput:
    path = golden_dir / f"{fixture_id}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return PostmortemLLMOutput.model_validate(raw)


def compare_baseline(metrics: dict[str, float], baseline: dict[str, Any], tolerance: float) -> list[str]:
    expected = baseline.get("metrics", {})
    failures: list[str] = []
    for key, base_val in expected.items():
        if key not in metrics:
            failures.append(f"missing metric {key}")
            continue
        got = metrics[key]
        if got + tolerance < float(base_val):
            failures.append(f"{key} regressed: {got:.4f} < baseline {base_val:.4f}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score runcloud9-ai fixtures against golden outputs.")
    parser.add_argument("--golden-dir", type=Path, default=DEFAULT_GOLDEN_DIR)
    parser.add_argument("--labels", type=Path, default=LABELS_PATH)
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument("--report", type=Path, default=REPO_ROOT / "eval" / "report.json")
    parser.add_argument("--tolerance", type=float, default=0.001)
    args = parser.parse_args(argv)

    labels_raw = json.loads(args.labels.read_text(encoding="utf-8"))
    labels = load_labels(labels_raw)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))

    scores = []
    per_fixture: dict[str, dict[str, object]] = {}
    for fixture_id in sorted(labels.keys()):
        context = load_fixture(fixture_id)
        golden = load_golden(args.golden_dir, fixture_id)
        scored = score_fixture(fixture_id, context, golden, labels[fixture_id])
        scores.append(scored)
        per_fixture[fixture_id] = {
            "root_cause_hit": scored.root_cause_hit,
            "citation_valid": scored.citation_valid,
            "hallucinated_refs": scored.hallucinated_refs,
            "total_refs": scored.total_refs,
            "negative_abstained": scored.negative_abstained,
            "cross_scope_hit": scored.cross_scope_hit,
        }

    metrics = aggregate_metrics(scores, labels)
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
