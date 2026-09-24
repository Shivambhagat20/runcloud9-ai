# ganymede-ai

Python inference layer for Runcloud9 (`ganymede-brain`).

## Layout

```
app/
  main.py              FastAPI on :5000, GET /health
  models.py            Pydantic mirror of Go AIContext (extra fields allowed)
  llm.py               LiteLLM wrapper (Claude default, model from env)
  routes/postmortem.py POST /postmortem stub
fixtures/              AIContext eval corpus (chaos scenarios)
tests/test_contract.py Fixture parse + API smoke tests
```

## CI

GitHub Actions runs `pytest` on pull requests and pushes to `main`. No API keys; tests do not call the LLM.

## Local dev

```powershell
cd ganymede-ai
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest
uvicorn app.main:app --host 0.0.0.0 --port 5000
```

## Docker

```powershell
docker build -t ganymede-brain .
docker run --rm -p 5000:5000 ganymede-brain
```

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `BRAIN_MODEL` | `anthropic/claude-sonnet-4-20250514` | LiteLLM model id (not used in CI) |
| `ANTHROPIC_API_KEY` | — | Required for real LLM calls (PR-21+) |

Fixtures regenerate from `ganymede`: `go run scripts/gen_aicontext_fixtures.go`
