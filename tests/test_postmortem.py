"""Post-mortem generator and rules catalog tests (no real LLM)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.catalog import RulesCatalogClient
from app.models import AIContext
from app.postmortem.generator import PROMPT_VERSION, build_messages, generate_postmortem, parse_llm_payload

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_rules_catalog_etag_cache() -> None:
    calls: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers.get("if-none-match"))
        if len(calls) == 1:
            return httpx.Response(
                200,
                json={"catalogVersion": "2", "rules": [{"id": "cache_hit_low"}]},
                headers={"ETag": '"deadbeef"'},
            )
        return httpx.Response(304)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="http://api.test")
    catalog = RulesCatalogClient(base_url="http://api.test", client=client)

    first = catalog.fetch()
    second = catalog.fetch()

    assert first["catalogVersion"] == "2"
    assert second == first
    assert len(calls) == 2
    assert calls[1] == '"deadbeef"'


def test_build_messages_prefers_library_mechanisms() -> None:
    raw = json.loads((FIXTURES_DIR / "clean.json").read_text(encoding="utf-8"))
    ctx = AIContext.model_validate(raw)
    messages = build_messages(ctx, {"catalogVersion": "2", "rules": []})
    system = messages[0]["content"]
    assert "Prefer library mechanisms" in system
    assert "insufficient_evidence" in system


def test_parse_llm_payload_accepts_insufficient_evidence_claim() -> None:
    payload = {
        "claims": [
            {
                "scope": "component",
                "components": ["db"],
                "aspect": "insufficient_evidence",
                "text": "Cannot explain failover without promotion events.",
                "factRefs": [],
                "grounding": "abstained",
            }
        ],
        "summary": "Inconclusive",
        "insufficientEvidence": ["failover timeline"],
    }
    out = parse_llm_payload(payload)
    assert out.claims[0].aspect == "insufficient_evidence"
    assert out.insufficient_evidence == ["failover timeline"]


def test_generate_postmortem_skipped_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    raw = json.loads((FIXTURES_DIR / "clean.json").read_text(encoding="utf-8"))
    ctx = AIContext.model_validate(raw)
    catalog = RulesCatalogClient(base_url="http://unused")

    response = generate_postmortem(ctx, catalog)

    assert response.status == "skipped"
    assert response.claims == []
    assert response.schema_version == ctx.schema_version
    assert response.catalog_version == ctx.catalog_version
    assert response.prompt_version == PROMPT_VERSION
    assert response.model == "none"


def test_generate_postmortem_with_mocked_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"catalogVersion": "2", "rules": []},
            headers={"ETag": '"etag1"'},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="http://api.test")
    catalog = RulesCatalogClient(base_url="http://api.test", client=client)

    raw = json.loads((FIXTURES_DIR / "clean.json").read_text(encoding="utf-8"))
    ctx = AIContext.model_validate(raw)

    def fake_complete(**_kwargs: object) -> str:
        return json.dumps(
            {
                "claims": [
                    {
                        "scope": "component",
                        "components": ["app-server"],
                        "aspect": "what",
                        "text": "Error rate stayed low.",
                        "factRefs": ["fact:metric:app-server.errorRate.last"],
                        "grounding": "inferred",
                        "proposedMechanism": {
                            "trigger": "stable error rate",
                            "config_precondition": "healthy baseline",
                            "causalChain": ["no fault injected"],
                        },
                    }
                ],
                "summary": "Clean run.",
                "insufficientEvidence": [],
            }
        )

    response = generate_postmortem(ctx, catalog, complete_fn=fake_complete, model="test/model")

    assert response.status == "ok"
    assert response.prompt_version == PROMPT_VERSION
    assert response.model == "test/model"
    assert response.catalog_version == "2"
    assert len(response.claims) == 1
    assert response.claims[0].grounding == "inferred"
    assert response.claims[0].proposed_mechanism is not None
