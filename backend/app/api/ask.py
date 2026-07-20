"""Ask API endpoint — Hybrid Graph + Vector RAG.

Implements thin routing layer calling AskService for hybrid RAG pipeline answers.
"""

from fastapi import APIRouter, Depends
from app.services.ask_service import AskService, AskRequest, AskResponse

router = APIRouter()


def get_ask_service() -> AskService:
    """Dependency provider for AskService."""
    return AskService()


@router.post("", response_model=AskResponse)
@router.post("/", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    ask_service: AskService = Depends(get_ask_service),
) -> AskResponse:
    """Answers a legal question using Hybrid Graph + Vector RAG pipeline."""
    return await ask_service.answer_question(request)

