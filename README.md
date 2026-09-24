# runcloud9-ai

Python inference layer for Runcloud9.

## Layout

```
app/
  main.py              FastAPI on :5000, GET /health
  models.py            Pydantic mirror of Go AIContext (extra fields allowed)
  llm.py               LiteLLM wrapper (Claude default, model from env)
  routes/postmortem.py POST /postmortem structured claims
  catalog.py           GET /meta/rules client with ETag cache
  postmortem/          prompt + structured LLM output
fixtures/              AIContext eval corpus (chaos scenarios)
tests/test_contract.py Fixture parse + API smoke tests
```

## CI

GitHub Actions runs `pytest` on pull requests and pushes to `main`. No API keys; tests do not call the LLM.

## Local dev

```powershell
cd runcloud9-ai
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest
uvicorn app.main:app --host 0.0.0.0 --port 5000
```

## Docker

```powershell
docker build -t runcloud9-ai .
docker run --rm -p 5000:5000 runcloud9-ai
```

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `BRAIN_MODEL` | `anthropic/claude-sonnet-4-20250514` | LiteLLM model id (not used in CI) |
| `ANTHROPIC_API_KEY` | — | Required for real LLM calls; CI omits it so `/postmortem` returns `skipped` |
| `CLOUD9_API_URL` | `http://localhost:8080` | Base URL for `GET /meta/rules` when generating claims |

Fixtures regenerate from the Go API repo: `go run scripts/gen_aicontext_fixtures.go` (run from `ganymede/`).
