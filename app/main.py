"""runcloud9-ai FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI

from app.routes.postmortem import router as postmortem_router
from app.routes.reel import router as reel_router

app = FastAPI(title="runcloud9-ai", version="0.1.0")
app.include_router(postmortem_router)
app.include_router(reel_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
