"""
main.py — FastAPI application factory.

Startup sequence:
  1. Lifespan: init Redis pool → create consumer groups → warm caches
  2. Middleware stack: CORS → Latency → (Auth in production)
  3. Routers: /api/v1/* + /health
  4. Background workers: stream consumer task

Design:
  • No global state except the Redis pool (managed by lifespan).
  • All config via Settings (pydantic-settings, env-file driven).
  • OpenAPI docs available at /docs (disabled in production).
"""
from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.redis_client import close_redis, init_redis
from app.middleware.latency import LatencyMiddleware

# ── Logging Setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ── Lifespan (Startup / Shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.
    Code before `yield` runs at startup; code after runs at shutdown.
    """
    logger.info("🚀  Starting %s v%s [%s]", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)

    # ── Startup ───────────────────────────────────────────────────────────────
    # ── Startup ───────────────────────────────────────────────────────────────
    await init_redis()

    # Create DB tables (safe to call repeatedly)
    from app.db.init_db import init_db
    import app.models  # noqa — registers all models with Base.metadata
    await init_db()

    from app.services.recommendations.session_model import session_model
    session_model.load()
    logger.info("✅  Recommendation model ready (loaded=%s)", session_model.is_loaded)

    # Start background stream consumer (processes events from Redis Streams)
    consumer_task = asyncio.create_task(
        _run_stream_consumer(), name="stream-consumer"
    )
    logger.info("✅  Background stream consumer started")

    yield  # ← Application is live and serving requests here

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("⏳  Shutting down gracefully...")
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass

    await close_redis()
    logger.info("✅  Shutdown complete")


# ── Application Factory ───────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="FlowPriceAI",
        version=settings.APP_VERSION,
        description=(
            "Real-time FlowPriceAI — Real-Time Dynamic Pricing Engine. "
            "Processes behavioral signals in sub-second latency. "
            "p99 target: < 200ms end-to-end."
        ),
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Middleware (outermost first) ──────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Response-Time", "X-Request-ID"],
    )

    app.add_middleware(
        LatencyMiddleware,
        record_to_redis=True,
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # ── Health Check (no auth required) ──────────────────────────────────────
    @app.get(
        "/health",
        tags=["System"],
        summary="System health probe",
        status_code=status.HTTP_200_OK,
    )
    async def health_check() -> dict:
        from app.core.redis_client import get_redis
        try:
            r = get_redis()
            await r.ping()
            redis_ok = True
        except Exception:
            redis_ok = False

        return {
            "status": "healthy" if redis_ok else "degraded",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "redis": "connected" if redis_ok else "disconnected",
        }

    # ── Global Exception Handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "path": str(request.url.path),
            },
        )

    return app


# ── Background Stream Consumer ────────────────────────────────────────────────

async def _run_stream_consumer() -> None:
    """
    Background task: continuously polls Redis Streams for new events.

    Consumer group ensures each event is processed exactly once across
    multiple worker instances. On failure, stale message reclamation
    (XAUTOCLAIM) prevents data loss.

    In production: run multiple workers as separate processes/pods.
    """
    from app.core.redis_client import stream_consumer

    logger.info("Stream consumer started — group=%s consumer=%s",
                settings.EVENTS_CONSUMER_GROUP, settings.EVENTS_CONSUMER_NAME)

    consecutive_errors = 0

    while True:
        try:
            # Read new messages (blocking with timeout)
            messages = await stream_consumer.read()

            if messages:
                # Process each message
                entry_ids = []
                for entry_id, fields in messages:
                    await _process_stream_message(entry_id, fields)
                    entry_ids.append(entry_id)

                # ACK all processed messages
                if entry_ids:
                    await stream_consumer.ack(*entry_ids)
                    logger.debug("ACKed %d stream messages", len(entry_ids))

                consecutive_errors = 0

            # Periodically reclaim stale messages from dead workers
            # Run every ~100 iterations (roughly every 10s with 100ms blocking)
            if asyncio.get_event_loop().time() % 10 < 0.2:
                stale = await stream_consumer.claim_stale(min_idle_ms=30_000)
                if stale:
                    logger.info("Reclaimed %d stale messages", len(stale))
                    for entry_id, fields in stale:
                        await _process_stream_message(entry_id, fields)
                    if stale:
                        await stream_consumer.ack(*[e[0] for e in stale])

        except asyncio.CancelledError:
            logger.info("Stream consumer cancelled — exiting cleanly")
            break
        except Exception as exc:
            consecutive_errors += 1
            backoff = min(2 ** consecutive_errors, 30)
            logger.error(
                "Stream consumer error #%d: %s — retrying in %ds",
                consecutive_errors, exc, backoff
            )
            await asyncio.sleep(backoff)


async def _process_stream_message(entry_id: str, fields: dict) -> None:
    """
    Secondary processing of events after ingestion.
    This is where you'd trigger:
      - Demand velocity alerts (→ pricing engine re-evaluation)
      - Purchase event → collaborative filtering model update
      - High-intent session → real-time recommendation refresh
    """
    event_type = fields.get("event_type", "unknown")
    session_id = fields.get("session_id", "")

    # Example: trigger pricing re-evaluation on high-intent events
    if event_type in ("cart_add", "checkout_start", "product_view"):
        logger.debug(
            "High-signal event %s for session %s — queuing pricing update",
            event_type, session_id[:12],
        )
        # In production: publish to a dedicated pricing-trigger channel
        # await pricing_engine.maybe_reprice(fields.get("product_id"))

    # Example: persist to analytics DB (async, non-critical path)
    # await analytics_db.insert_event(fields)


# ── Entrypoint ────────────────────────────────────────────────────────────────

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else 4,
        log_level="debug" if settings.DEBUG else "info",
        access_log=False,   # Handled by LatencyMiddleware
    )
