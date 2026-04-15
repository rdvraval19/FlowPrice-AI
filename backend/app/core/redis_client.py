"""
core/redis_client.py — Production-grade async Redis client.

Provides:
  • Connection pool singleton with health checks
  • Redis Streams: write, consumer group management, ACK
  • Feature store: typed get/set with TTL and atomic increments
  • Latency-aware wrapper that records operation timings
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import redis.asyncio as aioredis
from redis.asyncio.client import Pipeline
from redis.exceptions import ConnectionError, RedisError, ResponseError

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Module-level pool singleton ───────────────────────────────────────────────
_pool: aioredis.ConnectionPool | None = None
_redis: aioredis.Redis | None = None


async def init_redis() -> None:
    """Called once at application startup (lifespan hook)."""
    global _pool, _redis
    _pool = aioredis.ConnectionPool.from_url(
        settings.REDIS_URL,
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
        socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
        decode_responses=True,
        health_check_interval=30,
    )
    _redis = aioredis.Redis(connection_pool=_pool)

    # Verify connectivity
    try:
        await _redis.ping()
        logger.info("✅  Redis connected: %s", settings.REDIS_URL)
    except ConnectionError as exc:
        logger.error("❌  Redis connection failed: %s", exc)
        raise

    # Bootstrap consumer groups (idempotent)
    await _ensure_consumer_groups()


async def close_redis() -> None:
    """Called at application shutdown."""
    global _redis, _pool
    if _redis:
        await _redis.aclose()
    if _pool:
        await _pool.aclose()
    logger.info("Redis connections closed.")


def get_redis() -> aioredis.Redis:
    """Dependency injection helper — use in FastAPI Depends()."""
    if _redis is None:
        raise RuntimeError("Redis not initialised. Call init_redis() first.")
    return _redis


@asynccontextmanager
async def redis_pipeline() -> AsyncGenerator[Pipeline, None]:
    """Context manager for pipelined (batched) Redis commands."""
    r = get_redis()
    async with r.pipeline(transaction=False) as pipe:
        yield pipe


# ── Consumer Group Bootstrap ──────────────────────────────────────────────────

async def _ensure_consumer_groups() -> None:
    """
    Idempotently create the clickstream consumer group.
    MKSTREAM ensures the stream key is created if it doesn't exist yet.
    """
    r = get_redis()
    cfg = settings.redis_stream_config
    try:
        await r.xgroup_create(
            cfg["stream_key"],
            cfg["group"],
            id="0",           # Start from the very beginning
            mkstream=True,    # Auto-create stream if absent
        )
        logger.info(
            "Consumer group '%s' created on stream '%s'",
            cfg["group"],
            cfg["stream_key"],
        )
    except ResponseError as exc:
        if "BUSYGROUP" in str(exc):
            logger.debug("Consumer group already exists — skipping creation.")
        else:
            raise


# ── Redis Streams API ─────────────────────────────────────────────────────────

class StreamWriter:
    """
    High-throughput stream writer with automatic MAXLEN trimming.
    Uses XADD with MAXLEN ~ (approximate, ~10% faster than exact).
    """

    def __init__(self, stream_key: str | None = None):
        self.stream_key = stream_key or settings.EVENTS_STREAM_KEY
        self.max_len = settings.STREAM_MAX_LEN

    async def write(self, fields: dict[str, Any]) -> str:
        """
        Write one event to the stream.
        Returns the auto-generated stream entry ID (e.g. '1700000000000-0').
        """
        r = get_redis()
        # Serialize nested structures to JSON strings for Redis compatibility
        serialised = {
            k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
            for k, v in fields.items()
        }
        start = time.perf_counter()
        entry_id = await r.xadd(
            self.stream_key,
            serialised,
            maxlen=self.max_len,
            approximate=True,   # ~MAXLEN — much faster than exact trim
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.debug("XADD %s [%.2f ms] → %s", self.stream_key, elapsed_ms, entry_id)
        return entry_id

    async def write_batch(self, events: list[dict[str, Any]]) -> list[str]:
        """
        Pipeline multiple events in a single round-trip.
        Critical for burst traffic — reduces per-event network overhead.
        """
        r = get_redis()
        async with r.pipeline(transaction=False) as pipe:
            for event in events:
                serialised = {
                    k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                    for k, v in event.items()
                }
                pipe.xadd(
                    self.stream_key,
                    serialised,
                    maxlen=self.max_len,
                    approximate=True,
                )
            ids = await pipe.execute()
        return ids


class StreamConsumer:
    """
    Consumer group reader for background processing workers.
    Supports both blocking reads and non-blocking polling modes.
    """

    def __init__(
        self,
        stream_key: str | None = None,
        group: str | None = None,
        consumer: str | None = None,
    ):
        cfg = settings.redis_stream_config
        self.stream_key = stream_key or cfg["stream_key"]
        self.group = group or cfg["group"]
        self.consumer = consumer or cfg["consumer"]
        self.batch_size = cfg["batch_size"]
        self.block_ms = cfg["block_ms"]

    async def read(self) -> list[tuple[str, dict]]:
        """
        Blocking read from consumer group.
        Returns list of (entry_id, fields) tuples.
        Uses '>' to read only NEW (undelivered) messages.
        """
        r = get_redis()
        try:
            results = await r.xreadgroup(
                groupname=self.group,
                consumername=self.consumer,
                streams={self.stream_key: ">"},
                count=self.batch_size,
                block=self.block_ms,
            )
        except RedisError as exc:
            logger.error("Stream read error: %s", exc)
            return []

        if not results:
            return []

        # results format: [(stream_key, [(id, {fields}), ...])]
        _, messages = results[0]
        return [
            (msg_id, {k: _maybe_json(v) for k, v in fields.items()})
            for msg_id, fields in messages
        ]

    async def ack(self, *entry_ids: str) -> int:
        """Acknowledge processed entries — removes from PEL (pending list)."""
        r = get_redis()
        return await r.xack(self.stream_key, self.group, *entry_ids)

    async def claim_stale(self, min_idle_ms: int = 30_000) -> list[tuple[str, dict]]:
        """
        Re-claim messages idle for > min_idle_ms from crashed consumers.
        Prevents message loss on worker failure.
        """
        r = get_redis()
        result = await r.xautoclaim(
            self.stream_key,
            self.group,
            self.consumer,
            min_idle_time=min_idle_ms,
            start_id="0-0",
            count=self.batch_size,
        )
        _, claimed, _ = result
        return [
            (msg_id, {k: _maybe_json(v) for k, v in fields.items()})
            for msg_id, fields in claimed
        ]


def _maybe_json(value: str) -> Any:
    """Attempt JSON parse; return raw string on failure."""
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


# ── Feature Store API ─────────────────────────────────────────────────────────

class FeatureStore:
    """
    Redis-backed real-time feature store with typed accessors.

    Key schema:
      features:session:{session_id}   → hash (TTL: 30 min)
      features:user:{user_id}         → hash (TTL: 24 hr)
      features:product:{product_id}   → hash (TTL: 60 s)
      demand:velocity:{product_id}    → sorted set (event timestamps)
    """

    # ── Session Features ──────────────────────────────────────────────────────

    async def get_session_features(self, session_id: str) -> dict[str, Any]:
        r = get_redis()
        key = f"features:session:{session_id}"
        data = await r.hgetall(key)
        return {k: _coerce(v) for k, v in data.items()}

    async def update_session_features(
        self,
        session_id: str,
        updates: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        r = get_redis()
        key = f"features:session:{session_id}"
        ttl = ttl or settings.SESSION_FEATURE_TTL
        async with r.pipeline(transaction=False) as pipe:
            pipe.hset(key, mapping={k: str(v) for k, v in updates.items()})
            pipe.expire(key, ttl)
            await pipe.execute()

    # ── Demand Velocity ───────────────────────────────────────────────────────

    async def record_product_view(self, product_id: str) -> None:
        """
        Adds current timestamp to a sorted set.
        Sorted sets give us O(log N) range queries for velocity calculation.
        """
        r = get_redis()
        key = f"demand:velocity:{product_id}"
        now = time.time()
        window_start = now - settings.DEMAND_VELOCITY_WINDOW_SECONDS

        async with r.pipeline(transaction=False) as pipe:
            # Add new event
            pipe.zadd(key, {str(now): now})
            # Prune events outside the rolling window
            pipe.zremrangebyscore(key, "-inf", window_start)
            # Set TTL to auto-clean inactive products
            pipe.expire(key, settings.DEMAND_VELOCITY_WINDOW_SECONDS * 2)
            await pipe.execute()

    async def get_demand_velocity(self, product_id: str) -> int:
        """Returns count of views in the configured velocity window."""
        r = get_redis()
        key = f"demand:velocity:{product_id}"
        window_start = time.time() - settings.DEMAND_VELOCITY_WINDOW_SECONDS
        count = await r.zcount(key, window_start, "+inf")
        return int(count)

    # ── Price Cache ───────────────────────────────────────────────────────────

    async def get_cached_price(self, product_id: str, segment: str) -> float | None:
        r = get_redis()
        key = f"pricing:cache:{product_id}:{segment}"
        value = await r.get(key)
        return float(value) if value else None

    async def cache_price(
        self, product_id: str, segment: str, price: float
    ) -> None:
        r = get_redis()
        key = f"pricing:cache:{product_id}:{segment}"
        await r.setex(key, settings.PRICING_CACHE_TTL, str(price))

    # ── Category Affinity ─────────────────────────────────────────────────────

    async def increment_category_affinity(
        self, session_id: str, category: str, weight: float = 1.0
    ) -> None:
        r = get_redis()
        key = f"affinity:session:{session_id}"
        async with r.pipeline(transaction=False) as pipe:
            pipe.zincrby(key, weight, category)
            pipe.expire(key, settings.SESSION_FEATURE_TTL)
            await pipe.execute()

    async def get_top_categories(
        self, session_id: str, top_k: int = 5
    ) -> list[tuple[str, float]]:
        r = get_redis()
        key = f"affinity:session:{session_id}"
        results = await r.zrevrange(key, 0, top_k - 1, withscores=True)
        return [(cat, score) for cat, score in results]

    # ── Latency Metrics ───────────────────────────────────────────────────────

    async def record_latency(self, endpoint: str, latency_ms: float) -> None:
        """Push latency sample into a capped list for p99 computation."""
        r = get_redis()
        key = f"metrics:latency:{endpoint}"
        async with r.pipeline(transaction=False) as pipe:
            pipe.lpush(key, str(latency_ms))
            pipe.ltrim(key, 0, 999)   # Keep last 1000 samples
            pipe.expire(key, 3600)
            await pipe.execute()

    async def get_latency_percentiles(
        self, endpoint: str
    ) -> dict[str, float]:
        r = get_redis()
        key = f"metrics:latency:{endpoint}"
        raw = await r.lrange(key, 0, -1)
        if not raw:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "count": 0}

        samples = sorted(float(x) for x in raw)
        n = len(samples)

        def percentile(p: float) -> float:
            idx = int(n * p / 100)
            return samples[min(idx, n - 1)]

        return {
            "p50": round(percentile(50), 2),
            "p95": round(percentile(95), 2),
            "p99": round(percentile(99), 2),
            "count": n,
        }


def _coerce(value: str) -> Any:
    """Try int → float → json → raw string."""
    try:
        return int(value)
    except (ValueError, TypeError):
        pass
    try:
        return float(value)
    except (ValueError, TypeError):
        pass
    return _maybe_json(value)


# ── Module-level singletons ───────────────────────────────────────────────────
stream_writer = StreamWriter()
stream_consumer = StreamConsumer()
feature_store = FeatureStore()
