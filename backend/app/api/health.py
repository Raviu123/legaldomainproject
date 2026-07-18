"""Health check API endpoints.

Provides standard status checks to verify application readiness and LLM connectivity.
"""

from fastapi import APIRouter
from app.services.health_service import HealthService, LlmHealthResponse
from pydantic import BaseModel

router = APIRouter()
health_service = HealthService()


class HealthResponse(BaseModel):
    """Pydantic schema for health response."""

    status: str
    version: str


@router.get("", response_model=HealthResponse)
@router.get("/", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Returns the status of the API service."""
    res = health_service.get_api_health()
    return HealthResponse(status=res["status"], version=res["version"])


@router.get("/llm", response_model=LlmHealthResponse)
async def llm_health_check() -> LlmHealthResponse:
    """Check if the configured LLM is reachable and responding."""
    res = await health_service.check_llm_health()
    return LlmHealthResponse(**res)