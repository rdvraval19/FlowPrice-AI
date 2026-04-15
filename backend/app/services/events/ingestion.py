"""
services/events/ingestion.py — Event ingestion orchestrator.

Responsibilities:
  1. Validate and enrich the event (server_timestamp, geo inference)
  2. Write to Redis Streams (primary, non-blocking)
  3. Synchronously compute real-time features (< 5ms budget)
  4. Fire-and-forget async tasks for downstream consumers
  5. Instrument latency at every stage

The ingestion path is the hottest code in the system.
Every allocation and await is deliberate.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.core.redis_client import feature_store, stream_writer
from app.schemas.event import (
    BatchIngestResponse,
    ClickstreamEvent,
    EventBatch,
    EventIngestResponse,
    EventType,
)
from app.services.events.feature_compute import compute_and_store_features

logger = logging.getLogger(__name__)


async def ingest_event(
    event: ClickstreamEvent,
    *,
    compute_features: bool = True,
) -> EventIngestResponse:
    """
    Ingest a single clickstream event.

    Pipeline:
      enrich → write stream → compute features → record latency → return

    Total target: < 15ms server-side (network dominates the 200ms p99 SLA).
    """
    t0 = time.perf_counter()

    # ── Enrich with server-side fields ───────────────────────────────────────
    enriched_fields = event.to_stream_fields()
    enriched_fields["server_timestamp_ms"] = str(int(time.time() * 1000))
    enriched_fields["client_skew_ms"] = str(
        int(time.time() * 1000) - event.timestamp_ms
    )

    # ── Write to Redis Streams ────────────────────────────────────────────────
    # This is the critical path — must succeed before we return 200.
    try:
        entry_id = await stream_writer.write(enriched_fields)
    except Exception as exc:
        logger.error("Stream write failed for session=%s: %s", event.session_id, exc)
        raise

    stream_ms = (time.perf_counter() - t0) * 1000

    # ── Real-Time Feature Computation ─────────────────────────────────────────
    # Run synchronously so the API response can include fresh feature values.
    # Feature compute is O(1) Redis ops — budget is 5ms.
    features_updated = False
    if compute_features:
        try:
            computed = await compute_and_store_features(event)
            features_updated = True
            logger.debug(
                "Features: engagement=%.2f intent=%.3f velocity=%d [%.1f ms]",
                computed.new_engagement_score,
                computed.intent_probability,
                computed.demand_velocity,
                computed.compute_ms,
            )
        except Exception as exc:
            # Feature compute failure must NEVER fail ingestion
            logger.warning("Feature compute error (non-fatal): %s", exc)

    # ── Record Latency Sample ─────────────────────────────────────────────────
    total_ms = (time.perf_counter() - t0) * 1000
    asyncio.ensure_future(
        feature_store.record_latency("events.ingest", total_ms)
    )

    logger.info(
        "Ingested event session=%s type=%s stream_id=%s [%.2f ms]",
        event.session_id,
        event.event_type.value,
        entry_id,
        total_ms,
    )

    return EventIngestResponse(
        success=True,
        event_id=entry_id,
        session_id=event.session_id,
        features_updated=features_updated,
        latency_ms=round(total_ms, 2),
    )


async def ingest_batch(batch: EventBatch) -> BatchIngestResponse:
    """
    Batch ingestion — pipeline all stream writes in one round-trip,
    then compute features concurrently.

    Used by mobile SDKs that buffer events during offline periods.
    """
    t0 = time.perf_counter()

    # ── Pipeline Stream Writes ────────────────────────────────────────────────
    field_list = []
    for event in batch.events:
        fields = event.to_stream_fields()
        fields["server_timestamp_ms"] = str(int(time.time() * 1000))
        field_list.append(fields)

    accepted_ids: list[str] = []
    rejected = 0

    try:
        accepted_ids = await stream_writer.write_batch(field_list)
    except Exception as exc:
        logger.error("Batch stream write failed: %s", exc)
        rejected = len(batch.events)

    # ── Concurrent Feature Computation ───────────────────────────────────────
    # Use gather with return_exceptions so one failure doesn't kill the batch
    if accepted_ids:
        feature_tasks = [
            compute_and_store_features(event) for event in batch.events
        ]
        results = await asyncio.gather(*feature_tasks, return_exceptions=True)
        failures = sum(1 for r in results if isinstance(r, Exception))
        if failures:
            logger.warning("%d feature computations failed in batch", failures)

    total_ms = (time.perf_counter() - t0) * 1000
    asyncio.ensure_future(
        feature_store.record_latency("events.batch_ingest", total_ms)
    )

    return BatchIngestResponse(
        success=rejected == 0,
        accepted=len(accepted_ids),
        rejected=rejected,
        event_ids=accepted_ids,
        latency_ms=round(total_ms, 2),
    )
