"""
api/v1/endpoints/loyalty.py — User loyalty points and activity feed.

Endpoints:
  GET  /api/v1/loyalty/points          — Current points + tier (authenticated)
  GET  /api/v1/loyalty/activity        — Paginated activity history (authenticated)
  POST /api/v1/loyalty/award           — Internal: award points for an event
  GET  /api/v1/loyalty/leaderboard     — Top users by points (vendor only)
  GET  /api/v1/loyalty/tiers           — Static tier info (public)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_vendor
from app.db.session import get_db
from app.models.user import User
from app.schemas.loyalty import (
    ActivityFeed,
    PointsAwardRequest,
    PointsAwardResponse,
    PointsBalance,
    TIER_THRESHOLDS,
    TIER_BENEFITS,
    TIER_MULTIPLIERS,
)
from app.services.loyalty.loyalty_engine import loyalty_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/loyalty", tags=["Loyalty"])


# ── Public: tier reference ────────────────────────────────────────────────────

@router.get(
    "/tiers",
    summary="Get all tier definitions (public)",
)
async def get_tiers() -> dict:
    """Static tier info — shown on the storefront loyalty badge."""
    return {
        "tiers": [
            {
                "name": tier,
                "min_points": threshold,
                "benefit": TIER_BENEFITS[tier],
                "multiplier": TIER_MULTIPLIERS[tier],
            }
            for tier, threshold in TIER_THRESHOLDS.items()
        ]
    }


# ── Authenticated: user's own data ────────────────────────────────────────────

@router.get(
    "/points",
    response_model=PointsBalance,
    summary="Get current user's points balance and tier",
)
async def get_my_points(
    session_id: str | None = Query(
        default=None,
        description="Current browser session ID — adds real-time session points",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PointsBalance:
    return await loyalty_engine.get_balance(
        user_id=current_user.id,
        db=db,
        session_id=session_id,
    )


@router.get(
    "/activity",
    response_model=ActivityFeed,
    summary="Get current user's activity history (paginated)",
)
async def get_my_activity(
    page: int     = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActivityFeed:
    return await loyalty_engine.get_activity(
        user_id=current_user.id,
        db=db,
        page=page,
        per_page=per_page,
    )


# ── Internal: award points (called by feature_compute) ───────────────────────

@router.post(
    "/award",
    response_model=PointsAwardResponse,
    summary="Award points for an event (internal use)",
    description=(
        "Called internally by the event ingestion pipeline. "
        "Not intended for direct frontend use. "
        "No auth required — protected by internal network only in production."
    ),
)
async def award_points(
    req: PointsAwardRequest,
    db: AsyncSession = Depends(get_db),
) -> PointsAwardResponse:
    return await loyalty_engine.award_points(req=req, db=db)


# ── Vendor: leaderboard ───────────────────────────────────────────────────────

@router.get(
    "/leaderboard",
    summary="Top users by loyalty points (vendor only)",
)
async def get_leaderboard(
    top_k: int = Query(default=10, ge=1, le=50),
    _vendor: User = Depends(require_vendor),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns top-K users by total points.
    Reads from Redis sorted set if available, falls back to DB aggregate.
    """
    from sqlalchemy import func, select
    from app.models.activity_log import ActivityLog

    q = (
        select(
            ActivityLog.user_id,
            func.sum(ActivityLog.points_awarded).label("total_points"),
        )
        .group_by(ActivityLog.user_id)
        .order_by(func.sum(ActivityLog.points_awarded).desc())
        .limit(top_k)
    )
    rows = (await db.execute(q)).all()

    from app.schemas.loyalty import compute_tier
    return {
        "leaderboard": [
            {
                "rank": i + 1,
                "user_id": row.user_id,
                "total_points": int(row.total_points),
                "tier": compute_tier(int(row.total_points)),
            }
            for i, row in enumerate(rows)
        ],
        "total_users": len(rows),
    }