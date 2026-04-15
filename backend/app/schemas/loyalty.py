"""app/schemas/loyalty.py — Request/response schemas for loyalty + activity endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Tier definitions ──────────────────────────────────────────────────────────
# Thresholds are cumulative lifetime points — never expire.

TIER_THRESHOLDS = {
    "bronze":   0,
    "silver":   100,
    "gold":     500,
    "platinum": 2000,
}

TIER_BENEFITS = {
    "bronze":   "Standard pricing. Earn 1× points on all actions.",
    "silver":   "5% loyalty discount on cart. Earn 1.25× points.",
    "gold":     "10% loyalty discount. Priority support. Earn 1.5× points.",
    "platinum": "15% loyalty discount. Free shipping. Earn 2× points.",
}

TIER_MULTIPLIERS = {
    "bronze":   1.0,
    "silver":   1.25,
    "gold":     1.5,
    "platinum": 2.0,
}


def compute_tier(total_points: int) -> str:
    tier = "bronze"
    for t, threshold in TIER_THRESHOLDS.items():
        if total_points >= threshold:
            tier = t
    return tier


def points_to_next_tier(total_points: int, current_tier: str) -> int | None:
    tiers = list(TIER_THRESHOLDS.keys())
    idx = tiers.index(current_tier)
    if idx + 1 >= len(tiers):
        return None  # already at max tier
    next_threshold = TIER_THRESHOLDS[tiers[idx + 1]]
    return max(0, next_threshold - total_points)


# ── Response schemas ──────────────────────────────────────────────────────────

class ActivityItem(BaseModel):
    """Single activity log entry for the frontend feed."""
    id: str
    event_type: str
    product_id: str | None
    category: str | None
    price_shown: float | None
    points_awarded: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PointsBalance(BaseModel):
    """Points summary returned by GET /api/v1/loyalty/points."""
    user_id: str
    total_points: int
    tier: str
    tier_benefit: str
    tier_multiplier: float
    points_to_next_tier: int | None = Field(
        description="Points needed to reach next tier. None if already Platinum."
    )
    # Real-time session points (from Redis — not yet persisted)
    session_points: int = 0
    last_updated_at: datetime


class ActivityFeed(BaseModel):
    """Paginated activity history returned by GET /api/v1/loyalty/activity."""
    user_id: str
    total_points: int
    tier: str
    activities: list[ActivityItem]
    page: int
    per_page: int
    total_count: int
    has_more: bool


class PointsAwardRequest(BaseModel):
    """Internal — used by LoyaltyEngine to award points for an event."""
    user_id: str
    session_id: str
    event_type: str
    product_id: str | None = None
    category: str | None = None
    price_shown: float | None = None
    metadata_json: str | None = None


class PointsAwardResponse(BaseModel):
    points_awarded: int
    new_total: int
    tier: str
    tier_changed: bool
    previous_tier: str | None = None
