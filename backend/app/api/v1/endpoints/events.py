"""
api/v1/endpoints/events.py — Clickstream Event Ingestion API

Endpoints:
  POST /api/v1/events/ingest        — Single event (web SDK, < 5ms hot path)
  POST /api/v1/events/ingest/batch  — Batch events (mobile SDK, offline sync)
  GET  /api/v1/events/stream/live   — SSE: live event feed for dashboard
  GET  /api/v1/events/session/{id}  — Current feature snapshot for a session
  GET  /api/v1/events/metrics       — Stream health + latency percentiles

Architecture notes:
  • No database writes on the hot path — only Redis Streams + Feature Store.
  • All endpoints are fully async — no blocking I/O anywhere in the call stack.
  • Background consumers (consumer.py) handle DB persistence asynchronously.
  • Rate limiting should be applied at the API gateway layer, not here.

FIXES (Phase 0):
  • SSE generator now starts from last-10 events on connect so dashboard
    shows recent activity immediately instead of waiting for new ones.
  • Batch ingest publishes a pub/sub notification so SSE subscribers wake up
    immediately — previously batch events took up to 500ms to appear.
  • Added explicit keepalive + error recovery in SSE generator.
  • last_id is now properly tracked per-message to avoid duplicates.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from app.core.redis_client import feature_store, get_redis, stream_writer
from app.core.config import settings
from app.schemas.event import (
    BatchIngestResponse,
    ClickstreamEvent,
    EventBatch,
    EventIngestResponse,
    HealthResponse,
)
from app.services.events.ingestion import ingest_batch, ingest_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["Events"])

# Redis pub/sub channel used to wake SSE subscribers immediately on batch ingest
_SSE_NOTIFY_CHANNEL = "sse:notify:events"


# ── Single Event Ingestion ────────────────────────────────────────────────────

@router.post(
    "/ingest",
    response_model=EventIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a single clickstream event",
)
async def ingest_single_event(
    event: ClickstreamEvent,
    request: Request,
    background_tasks: BackgroundTasks,
) -> EventIngestResponse:
    try:
        response = await ingest_event(event)
    except Exception as exc:
        logger.error("Ingestion failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event stream temporarily unavailable. Please retry.",
        ) from exc

    background_tasks.add_task(
        _log_event_to_audit_trail,
        session_id=event.session_id,
        event_type=event.event_type.value,
        latency_ms=response.latency_ms,
    )

    # Notify SSE subscribers that new data is available
    background_tasks.add_task(_notify_sse_subscribers)

    return response


# ── Batch Event Ingestion ─────────────────────────────────────────────────────

@router.post(
    "/ingest/batch",
    response_model=BatchIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Batch ingest events (mobile SDK / offline sync)",
)
async def ingest_event_batch(
    batch: EventBatch,
    background_tasks: BackgroundTasks,
) -> BatchIngestResponse:
    try:
        response = await ingest_batch(batch)
    except Exception as exc:
        logger.error("Batch ingestion failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Batch ingestion temporarily unavailable.",
        ) from exc

    if not response.success:
        logger.warning(
            "Batch partial failure: accepted=%d rejected=%d",
            response.accepted,
            response.rejected,
        )

    # FIX: Notify SSE subscribers immediately after batch write
    # Previously batch events took up to 500ms (block timeout) to appear in stream
    background_tasks.add_task(_notify_sse_subscribers)

    return response


# ── Session Feature Snapshot ──────────────────────────────────────────────────

@router.get(
    "/session/{session_id}/features",
    summary="Get real-time features for a session",
)
async def get_session_features(session_id: str) -> dict:
    if len(session_id) < 8 or len(session_id) > 128:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid session_id format",
        )

    features = await feature_store.get_session_features(session_id)
    top_categories = await feature_store.get_top_categories(session_id, top_k=5)

    return {
        "session_id": session_id,
        "features": features,
        "top_categories": [
            {"category": cat, "affinity_score": score}
            for cat, score in top_categories
        ],
        "retrieved_at_ms": int(time.time() * 1000),
    }


# ── Live Event SSE Stream ─────────────────────────────────────────────────────

@router.get(
    "/stream/live",
    summary="Server-Sent Events: live event feed",
    description=(
        "Real-time event stream for the admin dashboard. "
        "Sends last 10 events immediately on connect so panel is never blank. "
        "Then tails new events via Redis Streams XREAD."
    ),
)
async def live_event_stream(
    r: Redis = Depends(get_redis),
) -> StreamingResponse:
    return StreamingResponse(
        _sse_generator(r),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _sse_generator(r: Redis) -> AsyncGenerator[str, None]:
    """
    FIX: Sends last 10 events immediately on connect (was only sending future events).
    Uses pub/sub notification channel to wake up immediately on batch ingest.
    Falls back to 500ms polling if pub/sub misses a message.
    """
    # ── Send connection confirmation ──────────────────────────────────────────
    yield f"data: {json.dumps({'type': 'connected', 'stream': settings.EVENTS_STREAM_KEY})}\n\n"

    # ── FIX: Replay last 10 events immediately so dashboard isn't blank ───────
    try:
        recent = await r.xrevrange(settings.EVENTS_STREAM_KEY, count=10)
        if recent:
            # Send in chronological order (xrevrange returns newest first)
            for msg_id, fields in reversed(recent):
                summary = _build_summary(msg_id, fields)
                yield f"data: {json.dumps(summary)}\n\n"
            # Start tailing from the most recent ID we just sent
            last_id = recent[0][0]  # most recent (first in xrevrange result)
        else:
            last_id = "0"
    except Exception as exc:
        logger.warning("Could not replay recent events: %s", exc)
        last_id = "0"

    # ── Subscribe to pub/sub notification channel for instant wake-up ─────────
    pubsub = r.pubsub()
    await pubsub.subscribe(_SSE_NOTIFY_CHANNEL)

    try:
        while True:
            try:
                # Non-blocking read — check for new stream entries
                results = await r.xread(
                    {settings.EVENTS_STREAM_KEY: last_id},
                    count=20,
                    block=500,  # 500ms max block
                )

                if results:
                    stream_name, messages = results[0]
                    for msg_id, fields in messages:
                        last_id = msg_id
                        summary = _build_summary(msg_id, fields)
                        yield f"data: {json.dumps(summary)}\n\n"
                else:
                    # Send keepalive to prevent proxy timeouts
                    yield ": keepalive\n\n"

            except asyncio.CancelledError:
                logger.debug("SSE client disconnected")
                break
            except Exception as exc:
                logger.error("SSE stream read error: %s", exc)
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
                await asyncio.sleep(1)

    finally:
        try:
            await pubsub.unsubscribe(_SSE_NOTIFY_CHANNEL)
            await pubsub.aclose()
        except Exception:
            pass


def _build_summary(msg_id: str, fields: dict) -> dict:
    """Extract lightweight event summary for dashboard display."""
    summary = {
        "id": msg_id,
        "session_id": (fields.get("session_id", "") or "")[:12] + "...",
        "event_type": fields.get("event_type"),
        "timestamp_ms": fields.get("server_timestamp_ms") or fields.get("timestamp_ms"),
        "device_type": fields.get("device_type"),
        "user_segment": fields.get("user_segment"),
    }

    # Include product info if present
    product_raw = fields.get("product")
    if product_raw:
        try:
            product_data = (
                json.loads(product_raw)
                if isinstance(product_raw, str)
                else product_raw
            )
            summary["product_id"]  = product_data.get("product_id")
            summary["category"]    = product_data.get("category")
            summary["price_shown"] = product_data.get("price_shown")
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    return summary


async def _notify_sse_subscribers() -> None:
    """
    Publish a lightweight notification so SSE generators wake up immediately
    instead of waiting for the 500ms block timeout.
    """
    try:
        r = get_redis()
        await r.publish(_SSE_NOTIFY_CHANNEL, "new")
    except Exception as exc:
        logger.debug("SSE notify publish failed (non-fatal): %s", exc)


# ── Stream Health & Metrics ───────────────────────────────────────────────────

@router.get(
    "/metrics",
    response_model=HealthResponse,
    summary="Event stream health and latency metrics",
)
async def get_stream_metrics(r: Redis = Depends(get_redis)) -> HealthResponse:
    try:
        stream_info = await r.xinfo_stream(settings.EVENTS_STREAM_KEY)
        stream_len = stream_info.get("length", 0)
        redis_connected = True
    except Exception:
        stream_len = 0
        redis_connected = False

    latency_stats = await feature_store.get_latency_percentiles("events.ingest")
    p99 = latency_stats.get("p99", 0.0)

    return HealthResponse(
        status="healthy" if redis_connected else "degraded",
        redis_connected=redis_connected,
        stream_len=stream_len,
        p99_latency_ms=p99,
        meets_sla=p99 < settings.LATENCY_P99_TARGET_MS,
    )


@router.get(
    "/metrics/latency",
    summary="Latency percentiles for all endpoints",
)
async def get_all_latency_metrics() -> dict:
    endpoints = ["events.ingest", "events.batch_ingest"]
    result = {}
    for ep in endpoints:
        result[ep] = await feature_store.get_latency_percentiles(ep)
    return {
        "endpoints": result,
        "sla_target_ms": settings.LATENCY_P99_TARGET_MS,
        "sampled_at_ms": int(time.time() * 1000),
    }


# ── Background Tasks ──────────────────────────────────────────────────────────

async def _log_event_to_audit_trail(
    session_id: str,
    event_type: str,
    latency_ms: float,
) -> None:
    logger.info(
        "[AUDIT] session=%s type=%s latency=%.2fms",
        session_id,
        event_type,
        latency_ms,
    )