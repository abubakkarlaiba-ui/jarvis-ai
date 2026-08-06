"""
API middleware for JARVIS.
=========================
Cross-cutting concerns applied to all API routes.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every incoming request and its response time."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        client = request.client.host if request.client else "unknown"
        logger.info("%s %s from %s", request.method, request.url.path, client)

        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed = time.perf_counter() - start
            logger.error("Request failed: %s %s (%.4fs) — %s", request.method, request.url.path, elapsed, exc)
            return JSONResponse(status_code=500, content={"error": "Internal server error"})

        elapsed = time.perf_counter() - start
        logger.info(
            "%s %s → %d (%.4fs)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validates API key from the X-API-Key header.

    Skips validation for health check and docs endpoints.
    """

    SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

    def __init__(self, api_key: str | None = None):
        super().__init__()
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        if self.api_key is None:
            return await call_next(request)

        provided_key = request.headers.get("X-API-Key")
        if provided_key != self.api_key:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid or missing API key"},
            )

        return await call_next(request)
