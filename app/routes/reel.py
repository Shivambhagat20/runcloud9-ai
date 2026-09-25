"""Highlight reel caption routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.models import AIContext
from app.reel import generate_reel_captions

router = APIRouter()


class ReelCaptionsRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    context: AIContext
    highlights: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/reel/captions")
def post_reel_captions(body: ReelCaptionsRequest) -> JSONResponse:
    """Caption highlights Go already selected. Empty captions when no API key is set."""
    payload = generate_reel_captions(body.context, body.highlights)
    return JSONResponse(payload)
