"""Inspector chat routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.catalog import get_rules_catalog_client
from app.chat.generator import generate_chat
from app.models import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def post_chat(body: ChatRequest) -> ChatResponse:
    """Answer one chat turn with fresh session context supplied by cloud9-api."""
    return generate_chat(body.context, body.messages, get_rules_catalog_client())
