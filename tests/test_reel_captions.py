"""Reel caption route and generator (no live LLM)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import AIContext
from app.reel.generator import generate_reel_captions

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _context() -> AIContext:
    raw = json.loads((FIXTURES_DIR / "cache_flush.json").read_text(encoding="utf-8"))
    return AIContext.model_validate(raw)


def test_reel_captions_empty_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    highlights = [{"ruleId": "cascade_cache_db", "title": "Cache miss storm"}]
    out = generate_reel_captions(_context(), highlights)
    assert out["captions"] == []
    assert out["throughline"] == ""
    assert out["usage"]["totalTokens"] == 0


def test_reel_captions_keeps_only_selected_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def fake_complete(**_kwargs: object) -> tuple[str, dict[str, int]]:
        payload = {
            "throughline": "Flushing the cache pushed reads onto Postgres.",
            "captions": [
                {
                    "ruleId": "cascade_cache_db",
                    "claim": {
                        "scope": "pair",
                        "components": ["cache", "db"],
                        "aspect": "why",
                        "text": "The flush forced reads through to the database.",
                        "factRefs": ["fact:rule:cascade_cache_db"],
                        "grounding": "authored",
                        "mechanismId": "cascade_cache_db_fallthrough",
                    },
                },
                {
                    "ruleId": "not_selected",
                    "claim": {
                        "scope": "component",
                        "aspect": "what",
                        "text": "Ignore me",
                        "factRefs": [],
                        "grounding": "inferred",
                    },
                },
            ],
        }
        return json.dumps(payload), {
            "promptTokens": 10,
            "completionTokens": 4,
            "totalTokens": 14,
        }

    out = generate_reel_captions(
        _context(),
        [{"ruleId": "cascade_cache_db"}],
        complete_fn=fake_complete,
    )
    assert out["throughline"].startswith("Flushing")
    assert len(out["captions"]) == 1
    claim = out["captions"][0]["claim"]
    assert claim["fact_refs"] == ["fact:rule:cascade_cache_db"]
    assert claim["mechanism_id"] == "cascade_cache_db_fallthrough"
    assert "factRefs" not in claim
    assert out["usage"]["totalTokens"] == 14


def test_post_reel_captions_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    raw = json.loads((FIXTURES_DIR / "cache_flush.json").read_text(encoding="utf-8"))
    client = TestClient(app)
    response = client.post(
        "/reel/captions",
        json={"context": raw, "highlights": [{"ruleId": "cascade_cache_db"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["captions"] == []
    assert body["usage"]["promptTokens"] == 0
