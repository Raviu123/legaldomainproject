import time
from typing import Any, Dict, Optional
from openai import OpenAI
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import logger


class LlmHealthResponse(BaseModel):
    """Pydantic schema for LLM health check response."""

    status: str = Field(..., description="LLM health status")
    model: str = Field(..., description="LLM model used")
    response: Optional[str] = Field(None, description="LLM response")
    latency_ms: Optional[int] = Field(None, description="Response latency in milliseconds")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class HealthService:
    """Service to handle health checks for the API and external integrations like LLMs."""

    def __init__(self) -> None:
        pass

    def get_api_health(self) -> Dict[str, str]:
        """Checks the API service status."""
        return {"status": "healthy", "version": "1.0.0"}

    async def check_llm_health(self) -> Dict[str, Any]:
        """Checks if the configured LLM is reachable and responding."""
        if not settings.OPENAI_API_KEY:
            return {
                "status": "unhealthy",
                "model": "None",
                "error": "OPENAI_API_KEY is not configured.",
            }

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

            return {
                "status": "healthy",
                "model": model,
                "response": llm_response,
                "latency_ms": latency_ms,
            }

        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.exception("LLM health check failed")
            return {
                "status": "unhealthy",
                "model": model,
                "latency_ms": latency_ms,
                "error": str(e),
            }
