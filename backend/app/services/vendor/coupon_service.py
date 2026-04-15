"""
services/vendor/coupon_service.py

Coupon lifecycle: generate → store (Redis + DB) → redeem → expire.

Redis key schema:
  coupon:{CODE}          → hash  (hot-path lookup, TTL = coupon TTL)
  coupon:uses:{CODE}     → int   (atomic counter, same TTL)

DB (Coupon model) is the audit trail and survives Redis flushes.
"""
from __future__ import annotations

import logging
import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.models.coupon import Coupon
from app.schemas.vendor import (
    CouponRequest,
    CouponRedeemRequest,
    CouponRedeemResponse,
    CouponResponse,
)

logger = logging.getLogger(__name__)

_COUPON_KEY = "coupon:{code}"
_USES_KEY = "coupon:uses:{code}"


def _generate_code(length: int = 8) -> str:
    """Random alphanumeric code — uppercased for readability."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choices(alphabet, k=length))


class CouponService:
    # ── Create ────────────────────────────────────────────────────────────────

    async def create(
        self,
        body: CouponRequest,
        vendor_id: str,
        db: AsyncSession,
    ) -> CouponResponse:
        code = (body.code or _generate_code()).upper()
        ttl_seconds = body.ttl_minutes * 60
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

        # ── Duplicate code check (prevents UNIQUE constraint crash) ───────────
        existing = await db.execute(select(Coupon).where(Coupon.code == code))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail=f"Coupon code '{code}' already exists. Use a different code.",
            )

        # ── Persist to DB first (source of truth) ────────────────────────────
        coupon = Coupon(
            code=code,
            discount_pct=body.discount_pct,
            target=body.target,
            target_id=body.target_id,
            max_uses=body.max_uses,
            expires_at=expires_at,
            created_by=vendor_id,
        )
        db.add(coupon)
        await db.flush()
        await db.refresh(coupon)

        # ── Mirror to Redis for fast hot-path lookups ─────────────────────────
        r = get_redis()
        key = _COUPON_KEY.format(code=code)
        uses_key = _USES_KEY.format(code=code)

        async with r.pipeline(transaction=False) as pipe:
            pipe.hset(
                key,
                mapping={
                    "discount_pct": str(body.discount_pct),
                    "target": body.target,
                    "target_id": body.target_id or "",
                    "max_uses": str(body.max_uses),
                    "expires_at": expires_at.isoformat(),
                    "created_by": vendor_id,
                },
            )
            pipe.expire(key, ttl_seconds)
            pipe.set(uses_key, 0)
            pipe.expire(uses_key, ttl_seconds)
            await pipe.execute()

        logger.info(
            "Coupon %s created by vendor %s | %.1f%% off | target=%s | ttl=%dm",
            code, vendor_id, body.discount_pct, body.target, body.ttl_minutes,
        )

        return CouponResponse(
            code=code,
            discount_pct=body.discount_pct,
            target=body.target,
            target_id=body.target_id,
            max_uses=body.max_uses,
            uses_remaining=body.max_uses,
            expires_at=expires_at,
            created_by=vendor_id,
        )

    # ── Redeem ────────────────────────────────────────────────────────────────

    async def redeem(
        self,
        body: CouponRedeemRequest,
        db: AsyncSession,
    ) -> CouponRedeemResponse:
        code = body.code.upper()
        r = get_redis()
        key = _COUPON_KEY.format(code=code)
        uses_key = _USES_KEY.format(code=code)

        # 1. Fast Redis check first
        data = await r.hgetall(key)
        if not data:
            return CouponRedeemResponse(
                valid=False, message="Coupon not found or expired"
            )

        max_uses = int(data["max_uses"])
        current_uses = int(await r.get(uses_key) or 0)

        if current_uses >= max_uses:
            return CouponRedeemResponse(
                valid=False, message="Coupon usage limit reached"
            )

        # 2. Target validation
        target = data["target"]
        target_id = data.get("target_id", "")
        if target == "user" and target_id and target_id != body.user_id:
            return CouponRedeemResponse(
                valid=False, message="Coupon is not valid for this user"
            )

        # 3. Atomic increment — prevents race conditions on concurrent redemptions
        new_count = await r.incr(uses_key)
        if new_count > max_uses:
            # Another request sneaked in — roll back and reject
            await r.decr(uses_key)
            return CouponRedeemResponse(
                valid=False, message="Coupon usage limit reached"
            )

        # 4. Update DB uses_count
        result = await db.execute(select(Coupon).where(Coupon.code == code))
        coupon = result.scalar_one_or_none()
        if coupon:
            coupon.uses_count += 1
            if coupon.uses_count >= coupon.max_uses:
                coupon.is_active = False

        discount_pct = float(data["discount_pct"])
        discounted_total = round(body.cart_total * (1 - discount_pct / 100), 2)

        logger.info(
            "Coupon %s redeemed by user %s | %.1f%% off | total %.2f → %.2f",
            code, body.user_id, discount_pct, body.cart_total, discounted_total,
        )

        return CouponRedeemResponse(
            valid=True,
            discount_pct=discount_pct,
            discounted_total=discounted_total,
            message="Coupon applied successfully",
        )

    # ── Info ──────────────────────────────────────────────────────────────────

    async def get_coupon_info(self, code: str, db: AsyncSession) -> Coupon | None:
        result = await db.execute(
            select(Coupon).where(Coupon.code == code.upper())
        )
        return result.scalar_one_or_none()


coupon_service = CouponService()