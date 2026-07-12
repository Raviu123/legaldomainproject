"""Health check API endpoints.

Provides standard status checks to verify application readiness and LLM connectivity.
"""

import time
from typing import Dict, Optional

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from openai import OpenAI
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import logger

router = APIRouter()


class HealthResponse(BaseModel):
    """Pydantic schema for health response."""

    status: str
    version: str


class LlmHealthResponse(BaseModel):
    """Pydantic schema for LLM health check response."""

    status: str = Field(..., description="LLM health status")
    model: str = Field(..., description="LLM model used")
    response: Optional[str] = Field(None, description="LLM response")
    latency_ms: Optional[int] = Field(None, description="Response latency in milliseconds")
    error: Optional[str] = Field(None, description="Error message if unhealthy")

@router.get("", response_model=HealthResponse)
@router.get("/", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Returns the status of the API service."""
    return HealthResponse(status="healthy", version="1.0.0")


@router.get("/llm", response_model=LlmHealthResponse)
async def llm_health_check() -> LlmHealthResponse:
    """Check if the configured LLM is reachable and responding."""

    if not settings.OPENAI_API_KEY:
        return LlmHealthResponse(
            status="unhealthy",
            model="None",
            error="OPENAI_API_KEY is not configured.",
        )

    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )

    model = settings.OPENAI_MODEL or settings.LLM_MODEL or "gpt-4o-mini"

    start_time = time.perf_counter()

    try:
        response = await run_in_threadpool(
            lambda: client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": "say 'Hello, World!' in 5 words or less.",
                    }
                ],
                temperature=0,
                max_tokens=150,
            )
        )

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        message = response.choices[0].message

        # NVIDIA/OpenAI-compatible models may return content in different fields.
        llm_response = (
            message.content
            or getattr(message, "reasoning", None)
            or getattr(message, "reasoning_content", None)
            or ""
        ).strip()

        return LlmHealthResponse(
            status="healthy",
            model=model,
            response=llm_response,
            latency_ms=latency_ms,
        )

    except Exception as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        logger.exception("LLM health check failed")

        return LlmHealthResponse(
            status="unhealthy",
            model=model,
            latency_ms=latency_ms,
            error=str(e),
        )