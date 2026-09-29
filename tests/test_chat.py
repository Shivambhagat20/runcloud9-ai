"""Chat API contract tests."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE_PATH = FIXTURES_DIR / "clean.json"


def test_chat_skipped_without_api_key() -> None:
    c = TestClient(app)
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    response = c.post(
        "/chat",
        json={
            "context": raw,
            "messages": [{"role": "user", "content": "Why is latency high?"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "skipped"
    assert body["claims"] == []
    assert body["promptVersion"] == "chat-v1"
