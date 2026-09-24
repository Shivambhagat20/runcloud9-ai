"""Post-mortem generation routes (stub until PR-21)."""

from __future__ import annotations

from fastapi import APIRouter

from app.models import AIContext, PostmortemResponse

router = APIRouter()


@router.post("/postmortem", response_model=PostmortemResponse)
def post_postmortem(context: AIContext) -> PostmortemResponse:
    """Accept AIContext and return a stub response. Real LLM wiring lands in PR-21."""
    return PostmortemResponse(
        status="stub",
        claims=[],
        summary="Post-mortem generation not implemented yet.",
        schema_version=context.schema_version,
        catalog_version=context.catalog_version,
        prompt_version="stub-v0",
        model="none",
    )
