


"""
schemas/vendor.py — Request/Response models for the Vendor panel.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ── Discount ──────────────────────────────────────────────────────────────────

class DiscountRequest(BaseModel):
    product_id: str = Field(..., description="Target product ID")
    discount_pct: float = Field(..., ge=1.0, le=90.0, description="Discount % (1–90)")
    reason: str | None = Field(None, max_length=255)


class DiscountResponse(BaseModel):
    product_id: str
    original_price: float
    discounted_price: float
    discount_pct: float
    applied_at: datetime
    applied_by: str  # vendor user_id


# ── Coupon ────────────────────────────────────────────────────────────────────

class CouponRequest(BaseModel):
    code: str | None = Field(
        None,
        min_length=4,
        max_length=20,
        description="Custom code — auto-generated if omitted",
    )
    discount_pct: float = Field(..., ge=1.0, le=80.0)
    target: Literal["all", "user", "segment"] = "all"
    target_id: str | None = Field(
        None, description="user_id or segment name when target != 'all'"
    )
    max_uses: int = Field(default=1, ge=1, le=10_000)
    ttl_minutes: int = Field(
        default=1440, ge=5, le=43_200, description="Redis TTL in minutes"
    )

    @field_validator("target_id")
    @classmethod
    def target_id_required_for_non_all(cls, v: str | None, info) -> str | None:
        if info.data.get("target") != "all" and not v:
            raise ValueError(
                "target_id is required when target is 'user' or 'segment'"
            )
        return v


class CouponResponse(BaseModel):
    code: str
    discount_pct: float
    target: str
    target_id: str | None
    max_uses: int
    uses_remaining: int
    expires_at: datetime
    created_by: str


class CouponRedeemRequest(BaseModel):
    code: str
    user_id: str
    cart_total: float = Field(..., gt=0)


class CouponRedeemResponse(BaseModel):
    valid: bool
    discount_pct: float | None = None
    discounted_total: float | None = None
    message: str


# ── Sponsor ───────────────────────────────────────────────────────────────────

class SponsorRequest(BaseModel):
    product_id: str
    duration_hours: int = Field(default=24, ge=1, le=720)
    badge_label: str = Field(default="Sponsored", max_length=30)


class SponsorResponse(BaseModel):
    product_id: str
    is_sponsored: bool
    badge_label: str
    sponsored_until: datetime
    sponsored_by: str


# ── Notify ────────────────────────────────────────────────────────────────────

class NotifyRequest(BaseModel):
    user_email: str = Field(..., description="Recipient email address")
    coupon_code: str
    subject: str = Field(default="A special coupon just for you!")
    message: str | None = Field(None, max_length=1000)


class NotifyResponse(BaseModel):
    sent: bool
    recipient: str
    coupon_code: str
    message: str
