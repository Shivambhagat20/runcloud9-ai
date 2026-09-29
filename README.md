# runcloud9-ai

Python inference layer for Runcloud9.

## Layout

```
app/
  main.py              FastAPI on :5000, GET /health
  models.py            Pydantic mirror of Go AIContext (extra fields allowed)
  llm.py               LiteLLM wrapper (Claude default, model from env)
  routes/postmortem.py POST /postmortem structured claims
  routes/reel.py       POST /reel/captions for Go-selected highlights
  catalog.py           GET /meta/rules client with ETag cache
  postmortem/          prompt + structured LLM output
fixtures/              AIContext eval corpus (chaos scenarios)
tests/test_contract.py Fixture parse + API smoke tests
```

## CI

GitHub Actions runs `pytest` and the offline eval harness on pull requests and pushes to `main`. No API keys; tests do not call the LLM.

On push to `main`, after `test` passes, the **deploy** job builds the Docker image, pushes to `us-central1-docker.pkg.dev/runcloud9-505411/cloud9-images/runcloud9-ai`, applies `k8s/deployment.yaml`, and rolls out `runcloud9-ai` in GKE (`cloud9-system`). Requires the same GitHub secrets as the ganymede API deploy: `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT`.

## Offline eval

Labelled chaos fixtures are scored against committed golden post-mortem outputs (no cluster):

```powershell
python -m eval.run
```

Metrics: root-cause accuracy, citation validity, hallucinated-fact rate, negative-case abstention, cross-scope coverage. CI fails if any metric regresses below `eval/baseline.json`.

Mechanism and fact ablation (golden outputs, no LLM):

```powershell
python -m eval.ablation_run
```

Reports **mechanism recovery rate**, **fact ablation pass rate**, and **inferred claim precision** separately (`eval/ablation_baseline.json`).

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

## Kubernetes

`k8s/deployment.yaml` runs this service as `runcloud9-ai` in namespace `cloud9-system` (port 5000). CI publishes the image to Artifact Registry and updates this deployment on merge to `main`. Create the API key secret once in the cluster (see `k8s/secrets.example.yaml`). `CLOUD9_API_URL` must reach the control plane so the service can fetch `GET /meta/rules`.

The Go API sets `INFERENCE_URL=http://runcloud9-ai:5000` in its own manifests. Apply this file separately from the control-plane kustomize tree.

```powershell
kubectl apply -f k8s/secrets.example.yaml
kubectl apply -f k8s/deployment.yaml
```

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `BRAIN_MODEL` | `anthropic/claude-sonnet-4-20250514` | LiteLLM model id (not used in CI) |
| `ANTHROPIC_API_KEY` | — | Required for real LLM calls; CI omits it so `/postmortem` returns `skipped` |
| `CLOUD9_API_URL` | `http://localhost:8080` | Base URL for `GET /meta/rules` when generating claims |

Fixtures regenerate from the Go API repo: `go run scripts/gen_aicontext_fixtures.go` (run from `ganymede/`).
