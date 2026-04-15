"""
services/vendor/sponsor_service.py

Marks a product as Sponsored for a fixed duration.

Redis key schema:
  sponsor:{product_id} → hash  { badge_label, sponsored_until, sponsored_by }
  TTL = duration_hours * 3600

DB (SponsoredProduct) is the persistent audit trail.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.models.sponsor import SponsoredProduct
from app.schemas.vendor import SponsorRequest, SponsorResponse

logger = logging.getLogger(__name__)

_SPONSOR_KEY = "sponsor:{product_id}"


class SponsorService:
    async def sponsor(
        self,
        body: SponsorRequest,
        vendor_id: str,
        db: AsyncSession,
    ) -> SponsorResponse:
        sponsored_until = datetime.now(timezone.utc) + timedelta(hours=body.duration_hours)
        ttl_seconds = body.duration_hours * 3600

        # ── Deactivate any previous active sponsorship for this product ───────
        result = await db.execute(
            select(SponsoredProduct).where(
                SponsoredProduct.product_id == body.product_id,
                SponsoredProduct.is_active == True,  # noqa: E712
            )
        )
        existing = result.scalars().all()
        for s in existing:
            s.is_active = False

        # ── Persist new sponsorship ───────────────────────────────────────────
        record = SponsoredProduct(
            product_id=body.product_id,
            badge_label=body.badge_label,
            sponsored_until=sponsored_until,
            sponsored_by=vendor_id,
        )
        db.add(record)
        await db.flush()

        # ── Mirror to Redis for low-latency badge checks ──────────────────────
        r = get_redis()
        key = _SPONSOR_KEY.format(product_id=body.product_id)
        async with r.pipeline(transaction=False) as pipe:
            pipe.hset(
                key,
                mapping={
                    "badge_label": body.badge_label,
                    "sponsored_until": sponsored_until.isoformat(),
                    "sponsored_by": vendor_id,
                },
            )
            pipe.expire(key, ttl_seconds)
            await pipe.execute()

        logger.info(
            "Product %s sponsored by vendor %s for %dh (until %s)",
            body.product_id, vendor_id, body.duration_hours, sponsored_until.isoformat(),
        )

        return SponsorResponse(
            product_id=body.product_id,
            is_sponsored=True,
            badge_label=body.badge_label,
            sponsored_until=sponsored_until,
            sponsored_by=vendor_id,
        )

    async def is_sponsored(self, product_id: str) -> tuple[bool, str]:
        """
        Fast Redis check for sponsored badge rendering.
        Returns (is_sponsored, badge_label).
        """
        r = get_redis()
        key = _SPONSOR_KEY.format(product_id=product_id)
        data = await r.hgetall(key)
        if not data:
            return False, ""
        return True, data.get("badge_label", "Sponsored")

    async def remove_sponsor(self, product_id: str, db: AsyncSession) -> bool:
        """Manually revoke sponsorship before TTL expires."""
        r = get_redis()
        key = _SPONSOR_KEY.format(product_id=product_id)
        await r.delete(key)

        result = await db.execute(
            select(SponsoredProduct).where(
                SponsoredProduct.product_id == product_id,
                SponsoredProduct.is_active == True,  # noqa: E712
            )
        )
        for s in result.scalars().all():
            s.is_active = False

        return True


sponsor_service = SponsorService()
