"""Contract tests: fixtures must parse as AIContext."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import AIContext

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE_PATHS = sorted(FIXTURES_DIR.glob("*.json"))


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("fixture_path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_fixture_parses_as_aicontext(fixture_path: Path) -> None:
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    ctx = AIContext.model_validate(raw)
    assert ctx.session_id == fixture_path.stem
    assert ctx.schema_version == 1
    assert len(ctx.runs) >= 1


def test_models_ignores_unknown_fields() -> None:
    raw = json.loads(FIXTURE_PATHS[0].read_text(encoding="utf-8"))
    raw["futureField"] = {"nested": True}
    raw["runs"][0]["futureRunField"] = 42

    ctx = AIContext.model_validate(raw)
    assert ctx.session_id
    assert ctx.schema_version == 1
    # Unknown fields are retained in extras without breaking typed fields.
    assert ctx.__pydantic_extra__ is not None
    assert ctx.__pydantic_extra__.get("futureField") == {"nested": True}


@pytest.mark.parametrize("fixture_path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_postmortem_stub_accepts_fixture(fixture_path: Path, client: TestClient) -> None:
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    response = client.post("/postmortem", json=raw)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "stub"
    assert body["claims"] == []
    assert body["schemaVersion"] == raw["schemaVersion"]
    assert body["catalogVersion"] == raw["catalogVersion"]
