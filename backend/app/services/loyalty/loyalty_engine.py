"""
services/loyalty/loyalty_engine.py — Points award, balance, and tier system.

Architecture:
  • Redis (hot path):  session-scoped points counter, per-user total cache
  • SQLite (cold path): ActivityLog rows — immutable ledger, survives Redis flushes

Point award flow (called from feature_compute.py on every ingestion):
  1. Determine base points for event_type
  2. Apply tier multiplier (silver→1.25×, gold→1.5×, platinum→2×)
  3. Atomically increment Redis counter (user:points:{user_id})
  4. Insert ActivityLog row asynchronously (non-blocking to ingestion path)
  5. Return PointsAwardResponse to caller
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.models.activity_log import ActivityLog
from app.schemas.loyalty import (
    ActivityFeed,
    ActivityItem,
    PointsAwardRequest,
    PointsAwardResponse,
    PointsBalance,
    TIER_BENEFITS,
    TIER_MULTIPLIERS,
    compute_tier,
    points_to_next_tier,
)

logger = logging.getLogger(__name__)

# ── Point values per event type ───────────────────────────────────────────────
# Tunable without schema changes — only this dict needs updating.
BASE_POINTS: dict[str, int] = {
    "session_start":    1,
    "page_view":        0,   # too noisy to award
    "category_browse":  0,
    "search":           1,
    "product_view":     1,
    "image_zoom":       1,
    "review_read":      2,
    "wishlist_add":     3,
    "cart_add":         5,
    "cart_remove":      0,   # no penalty, but no reward
    "cart_view":        0,
    "checkout_start":   3,
    "purchase":        20,
    "return_initiate":  0,
}

# Redis key schema
_POINTS_KEY    = "loyalty:points:{user_id}"    # int — total cumulative points
_TIER_KEY      = "loyalty:tier:{user_id}"      # string — cached tier
_SESSION_PTS   = "loyalty:session:{session_id}" # int — points this session
_POINTS_TTL    = 86400 * 30                    # 30 days — soft cache


class LoyaltyEngine:

    # ── Award points ──────────────────────────────────────────────────────────

    async def award_points(
        self,
        req: PointsAwardRequest,
        db: AsyncSession,
    ) -> PointsAwardResponse:
        """
        Award points for a single event.
        Called from feature_compute after every ingestion event.

        Hot path: only Redis writes here.
        DB write happens fire-and-forget via asyncio.ensure_future.
        """
        import asyncio

        base = BASE_POINTS.get(req.event_type, 0)
        if base == 0:
            return PointsAwardResponse(
                points_awarded=0,
                new_total=await self._get_cached_total(req.user_id),
                tier=await self._get_cached_tier(req.user_id),
                tier_changed=False,
            )

        # Get current tier for multiplier
        current_tier = await self._get_cached_tier(req.user_id)
        multiplier = TIER_MULTIPLIERS.get(current_tier, 1.0)
        points = max(1, round(base * multiplier))

        # Atomically update Redis
        r = get_redis()
        points_key   = _POINTS_KEY.format(user_id=req.user_id)
        session_key  = _SESSION_PTS.format(session_id=req.session_id)

        async with r.pipeline(transaction=False) as pipe:
            pipe.incrby(points_key, points)
            pipe.expire(points_key, _POINTS_TTL)
            pipe.incrby(session_key, points)
            pipe.expire(session_key, 1800)   # session TTL = 30 min
            results = await pipe.execute()

        new_total = int(results[0])
        new_tier  = compute_tier(new_total)

        # Update cached tier if changed
        tier_changed = new_tier != current_tier
        if tier_changed:
            tier_key = _TIER_KEY.format(user_id=req.user_id)
            await r.set(tier_key, new_tier, ex=_POINTS_TTL)
            logger.info(
                "User %s tier upgrade: %s → %s (total=%d pts)",
                req.user_id, current_tier, new_tier, new_total,
            )

        # DB write — fire and forget so ingestion path isn't blocked
        asyncio.ensure_future(
            self._persist_activity(req, points, db)
        )

        return PointsAwardResponse(
            points_awarded=points,
            new_total=new_total,
            tier=new_tier,
            tier_changed=tier_changed,
            previous_tier=current_tier if tier_changed else None,
        )

    # ── Query points balance ──────────────────────────────────────────────────

    async def get_balance(
        self,
        user_id: str,
        db: AsyncSession,
        session_id: str | None = None,
    ) -> PointsBalance:
        """
        Returns the full points summary for a user.
        Reads from Redis cache; falls back to DB aggregate on cache miss.
        """
        total = await self._get_cached_total(user_id)

        # Cache miss — recompute from DB
        if total == 0:
            total = await self._sum_from_db(user_id, db)
            if total > 0:
                r = get_redis()
                await r.set(
                    _POINTS_KEY.format(user_id=user_id),
                    total, ex=_POINTS_TTL,
                )

        tier = compute_tier(total)
        session_pts = 0
        if session_id:
            r = get_redis()
            raw = await r.get(_SESSION_PTS.format(session_id=session_id))
            session_pts = int(raw) if raw else 0

        return PointsBalance(
            user_id=user_id,
            total_points=total,
            tier=tier,
            tier_benefit=TIER_BENEFITS.get(tier, ""),
            tier_multiplier=TIER_MULTIPLIERS.get(tier, 1.0),
            points_to_next_tier=points_to_next_tier(total, tier),
            session_points=session_pts,
            last_updated_at=datetime.now(timezone.utc),
        )

    # ── Activity feed ─────────────────────────────────────────────────────────

    async def get_activity(
        self,
        user_id: str,
        db: AsyncSession,
        page: int = 1,
        per_page: int = 20,
    ) -> ActivityFeed:
        """Paginated activity history from the DB ledger."""
        offset = (page - 1) * per_page

        # Total count
        count_q  = select(func.count()).where(ActivityLog.user_id == user_id)
        total    = (await db.execute(count_q)).scalar_one()

        # Page of activities
        rows_q = (
            select(ActivityLog)
            .where(ActivityLog.user_id == user_id)
            .order_by(ActivityLog.created_at.desc())
            .offset(offset)
            .limit(per_page)
        )
        rows = (await db.execute(rows_q)).scalars().all()

        total_pts = await self._get_cached_total(user_id)
        tier      = compute_tier(total_pts)

        return ActivityFeed(
            user_id=user_id,
            total_points=total_pts,
            tier=tier,
            activities=[ActivityItem.model_validate(r) for r in rows],
            page=page,
            per_page=per_page,
            total_count=total,
            has_more=(offset + per_page) < total,
        )

    # ── Sync total from DB (cache rebuild) ────────────────────────────────────

    async def _sum_from_db(self, user_id: str, db: AsyncSession) -> int:
        q = select(func.sum(ActivityLog.points_awarded)).where(
            ActivityLog.user_id == user_id
        )
        result = await db.execute(q)
        return int(result.scalar_one() or 0)

    # ── Redis helpers ─────────────────────────────────────────────────────────

    async def _get_cached_total(self, user_id: str) -> int:
        try:
            r = get_redis()
            raw = await r.get(_POINTS_KEY.format(user_id=user_id))
            return int(raw) if raw else 0
        except Exception:
            return 0

    async def _get_cached_tier(self, user_id: str) -> str:
        try:
            r = get_redis()
            raw = await r.get(_TIER_KEY.format(user_id=user_id))
            if raw:
                return raw
            # Compute from total and cache it
            total = await self._get_cached_total(user_id)
            tier  = compute_tier(total)
            await r.set(_TIER_KEY.format(user_id=user_id), tier, ex=_POINTS_TTL)
            return tier
        except Exception:
            return "bronze"

    # ── DB persistence (called fire-and-forget) ───────────────────────────────

    async def _persist_activity(
        self,
        req: PointsAwardRequest,
        points: int,
        db: AsyncSession,
    ) -> None:
        """Write ActivityLog row. Non-fatal — never raises to caller."""
        try:
            row = ActivityLog(
                user_id=req.user_id,
                session_id=req.session_id,
                event_type=req.event_type,
                product_id=req.product_id,
                category=req.category,
                price_shown=req.price_shown,
                points_awarded=points,
                metadata_json=req.metadata_json,
            )
            db.add(row)
            await db.commit()
        except Exception as exc:
            logger.warning("ActivityLog persist failed (non-fatal): %s", exc)
            await db.rollback()


# Module-level singleton
loyalty_engine = LoyaltyEngine()