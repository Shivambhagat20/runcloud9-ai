"""Post-mortem generation routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.catalog import get_rules_catalog_client
from app.models import AIContext, PostmortemResponse
from app.postmortem import generate_postmortem

router = APIRouter()


@router.post("/postmortem", response_model=PostmortemResponse)
def post_postmortem(context: AIContext) -> PostmortemResponse:
    """Accept AIContext and return structured claims (LLM when API key is set)."""
    return generate_postmortem(context, get_rules_catalog_client())
