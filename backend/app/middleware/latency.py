"""
middleware/latency.py — Request latency instrumentation middleware.

Adds:
  • X-Response-Time header to every response (ms, 2 decimal places)
  • Background recording of latency into the Feature Store for p99 calculation
  • Request ID header (X-Request-ID) for distributed tracing
  • Structured access log with latency + status code
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.redis_client import feature_store

logger = logging.getLogger(__name__)

# Endpoints excluded from latency recording (too noisy / not business-critical)
EXCLUDED_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}


class LatencyMiddleware(BaseHTTPMiddleware):
    """
    Measures wall-clock request latency and injects it into:
      1. Response headers (for client-side monitoring)
      2. Redis feature store (for server-side p99 calculation)
    """

    def __init__(self, app: ASGIApp, *, record_to_redis: bool = True):
        super().__init__(app)
        self.record_to_redis = record_to_redis

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Assign a unique request ID for tracing
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]

        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Inject headers
        response.headers["X-Response-Time"] = f"{elapsed_ms:.2f}ms"
        response.headers["X-Request-ID"] = request_id

        # Structured log
        path = request.url.path
        logger.info(
            "%s %s %d %.2fms req=%s",
            request.method,
            path,
            response.status_code,
            elapsed_ms,
            request_id,
        )

        # Async Redis write — fire and forget, never block the response
        if self.record_to_redis and path not in EXCLUDED_PATHS:
            endpoint_key = _path_to_key(path)
            asyncio.ensure_future(
                feature_store.record_latency(endpoint_key, elapsed_ms)
            )

        return response


def _path_to_key(path: str) -> str:
    """
    Normalise URL paths to metric keys.
    e.g. /api/v1/events/ingest → api.v1.events.ingest
    """
    return path.strip("/").replace("/", ".").replace("-", "_")
