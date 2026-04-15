"""
services/events/feature_compute.py — Real-time feature engineering.

PHASE 4 ADDITION:
  After computing session features, award loyalty points if the event
  belongs to an authenticated user (user_id is present on the event).
  Points are awarded fire-and-forget — never block the ingestion path.

Point hook is at the very end of compute_and_store_features so that
even if loyalty_engine raises, the core feature computation still succeeds.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.redis_client import feature_store
from app.schemas.event import ClickstreamEvent, EventType, UserSegment

logger = logging.getLogger(__name__)

# ── Engagement Signal Weights ─────────────────────────────────────────────────
ENGAGEMENT_WEIGHTS: dict[EventType, float] = {
    EventType.PAGE_VIEW:        0.5,
    EventType.CATEGORY_BROWSE:  0.8,
    EventType.SEARCH:           1.0,
    EventType.PRODUCT_VIEW:     2.0,
    EventType.IMAGE_ZOOM:       2.5,
    EventType.REVIEW_READ:      3.0,
    EventType.WISHLIST_ADD:     4.0,
    EventType.CART_ADD:         6.0,
    EventType.CART_REMOVE:     -2.0,
    EventType.CART_VIEW:        3.5,
    EventType.CHECKOUT_START:   8.0,
    EventType.PURCHASE:        10.0,
    EventType.SESSION_START:    0.1,
    EventType.SESSION_END:      0.0,
}

HIGH_INTENT_SCORE_THRESHOLD   = 7.0
MEDIUM_INTENT_SCORE_THRESHOLD = 3.0
AFFINITY_HALF_LIFE_SECONDS    = 600.0


@dataclass
class ComputedFeatures:
    session_id: str
    event_type: str
    engagement_delta: float
    new_engagement_score: float
    intent_probability: float
    top_categories: list[tuple[str, float]]
    demand_velocity: int
    # Phase 4 additions
    points_awarded: int = 0
    user_tier: str = "bronze"
    features_written: bool = True
    compute_ms: float = 0.0


async def compute_and_store_features(event: ClickstreamEvent) -> ComputedFeatures:
    """
    Main entry point — called synchronously during event ingestion.
    Phase 4: also awards loyalty points for authenticated users.
    """
    t0 = time.perf_counter()

    # ── Step 1: Engagement Score ──────────────────────────────────────────────
    engagement_delta  = ENGAGEMENT_WEIGHTS.get(event.event_type, 0.5)
    current_features  = await feature_store.get_session_features(event.session_id)
    current_score     = float(current_features.get("engagement_score", 0.0))
    new_score         = max(0.0, current_score + engagement_delta)

    # ── Step 2: Category Affinity ─────────────────────────────────────────────
    category_weight = _category_weight_for_event(event)
    if event.product and category_weight > 0:
        await feature_store.increment_category_affinity(
            event.session_id, event.product.category, weight=category_weight,
        )

    # ── Step 3: Demand Velocity ───────────────────────────────────────────────
    demand_velocity = 0
    if event.event_type == EventType.PRODUCT_VIEW and event.product:
        await feature_store.record_product_view(event.product.product_id)
        demand_velocity = await feature_store.get_demand_velocity(event.product.product_id)

    # ── Step 4: Intent Probability ────────────────────────────────────────────
    intent_prob = _compute_intent_probability(
        engagement_score=new_score,
        event_type=event.event_type,
        user_segment=event.user_segment,
        has_cart=current_features.get("has_cart_items", False),
    )

    # ── Step 5: Persist Session Features ─────────────────────────────────────
    updates: dict[str, Any] = {
        "engagement_score":    round(new_score, 3),
        "intent_probability":  round(intent_prob, 4),
        "last_event_type":     event.event_type.value,
        "last_seen_ms":        int(time.time() * 1000),
        "session_event_count": int(current_features.get("session_event_count", 0)) + 1,
        "user_segment":        event.user_segment.value,
        "device_type":         event.device_type.value,
    }
    if event.user_id:
        updates["user_id"] = event.user_id   # persist for downstream consumers

    if event.event_type == EventType.CART_ADD:
        updates["has_cart_items"] = True
    elif event.event_type == EventType.PURCHASE:
        updates["has_cart_items"] = False
        updates["purchase_count"] = int(current_features.get("purchase_count", 0)) + 1

    if event.product:
        updates["last_product_id"] = event.product.product_id
        updates["last_category"]   = event.product.category
        updates["last_price_shown"] = event.product.price_shown

    await feature_store.update_session_features(event.session_id, updates)

    # ── Step 6: Top Categories ────────────────────────────────────────────────
    top_categories = await feature_store.get_top_categories(event.session_id, top_k=5)

    # ── Step 7 (Phase 4): Award Loyalty Points ────────────────────────────────
    # Only for authenticated users — anonymous sessions accumulate no points.
    points_awarded = 0
    user_tier      = "bronze"

    if event.user_id:
        points_awarded, user_tier = await _award_loyalty_points_safe(event)

    elapsed = (time.perf_counter() - t0) * 1000
    logger.debug(
        "Features computed for session=%s event=%s pts=%d [%.2f ms]",
        event.session_id, event.event_type.value, points_awarded, elapsed,
    )

    return ComputedFeatures(
        session_id=event.session_id,
        event_type=event.event_type.value,
        engagement_delta=engagement_delta,
        new_engagement_score=round(new_score, 3),
        intent_probability=round(intent_prob, 4),
        top_categories=top_categories,
        demand_velocity=demand_velocity,
        points_awarded=points_awarded,
        user_tier=user_tier,
        compute_ms=round(elapsed, 2),
    )


async def _award_loyalty_points_safe(event: ClickstreamEvent) -> tuple[int, str]:
    """
    Award loyalty points without blocking or crashing ingestion.
    Uses Redis-only path (no DB) to stay within the 5ms feature compute budget.
    DB persistence happens fire-and-forget inside loyalty_engine.
    """
    try:
        from app.services.loyalty.loyalty_engine import loyalty_engine, BASE_POINTS
        from app.schemas.loyalty import TIER_MULTIPLIERS, compute_tier
        from app.core.redis_client import get_redis

        base = BASE_POINTS.get(event.event_type.value, 0)
        if base == 0:
            return 0, "bronze"

        # Quick Redis-only tier lookup (no DB)
        r = get_redis()
        tier_key   = f"loyalty:tier:{event.user_id}"
        points_key = f"loyalty:points:{event.user_id}"

        tier_raw = await r.get(tier_key)
        tier     = tier_raw if tier_raw else "bronze"
        mult     = TIER_MULTIPLIERS.get(tier, 1.0)
        points   = max(1, round(base * mult))

        # Atomic Redis increment
        new_total = await r.incrby(points_key, points)
        await r.expire(points_key, 86400 * 30)

        # Session points
        session_key = f"loyalty:session:{event.session_id}"
        await r.incrby(session_key, points)
        await r.expire(session_key, 1800)

        # Update tier cache if needed
        new_tier = compute_tier(int(new_total))
        if new_tier != tier:
            await r.set(tier_key, new_tier, ex=86400 * 30)
            logger.info(
                "Tier upgrade: user=%s %s→%s (%d pts)",
                event.user_id, tier, new_tier, new_total,
            )

        # Fire-and-forget DB persistence (non-blocking)
        asyncio.ensure_future(
            _persist_activity_log(event, points)
        )

        return points, new_tier

    except Exception as exc:
        logger.debug("Loyalty points award skipped (non-fatal): %s", exc)
        return 0, "bronze"


async def _persist_activity_log(event: ClickstreamEvent, points: int) -> None:
    """Write ActivityLog to DB. Runs outside the request context — creates its own session."""
    try:
        from app.db.session import AsyncSessionLocal
        from app.models.activity_log import ActivityLog

        async with AsyncSessionLocal() as db:
            row = ActivityLog(
                user_id=event.user_id,
                session_id=event.session_id,
                event_type=event.event_type.value,
                product_id=event.product.product_id if event.product else None,
                category=event.product.category if event.product else None,
                price_shown=event.product.price_shown if event.product else None,
                points_awarded=points,
            )
            db.add(row)
            await db.commit()
    except Exception as exc:
        logger.warning("ActivityLog DB persist failed (non-fatal): %s", exc)


# ── Helpers (unchanged from original) ────────────────────────────────────────

def _category_weight_for_event(event: ClickstreamEvent) -> float:
    weights = {
        EventType.PRODUCT_VIEW:  1.0,
        EventType.IMAGE_ZOOM:    1.5,
        EventType.REVIEW_READ:   1.2,
        EventType.WISHLIST_ADD:  2.0,
        EventType.CART_ADD:      3.0,
        EventType.PURCHASE:      5.0,
    }
    return weights.get(event.event_type, 0.0)


def _compute_intent_probability(
    engagement_score: float,
    event_type: EventType,
    user_segment: UserSegment,
    has_cart: bool,
) -> float:
    normalised = min(engagement_score / 50.0, 1.0)
    base_prob  = _sigmoid(normalised * 6 - 3)
    adjustments = 0.0

    if has_cart:
        adjustments += 0.20
    if event_type == EventType.CHECKOUT_START:
        adjustments += 0.35
    elif event_type == EventType.CART_ADD:
        adjustments += 0.15
    elif event_type == EventType.WISHLIST_ADD:
        adjustments += 0.08
    elif event_type == EventType.CART_REMOVE:
        adjustments -= 0.12

    segment_boost = {
        UserSegment.LOYALTY:         0.10,
        UserSegment.HIGH_VALUE:      0.08,
        UserSegment.RETURNING:       0.05,
        UserSegment.PRICE_SENSITIVE: -0.05,
        UserSegment.NEW_VISITOR:     0.0,
        UserSegment.UNKNOWN:         0.0,
    }
    adjustments += segment_boost.get(user_segment, 0.0)
    return max(0.0, min(1.0, base_prob + adjustments))


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)