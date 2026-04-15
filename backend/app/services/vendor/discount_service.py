"""
services/vendor/discount_service.py

Applies a vendor discount to a product price.

Flow:
  1. Fetch current product price from the catalog (injected as dependency).
  2. Validate discount % against MAX_DISCOUNT_PCT from settings.
  3. Compute discounted price and write it to Redis pricing cache.
  4. Return a DiscountResponse for the endpoint to return.

Note: We do NOT own the catalog — we receive `original_price` from the
caller so this service stays decoupled from catalog internals.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.core.redis_client import get_redis
from app.schemas.vendor import DiscountRequest, DiscountResponse

logger = logging.getLogger(__name__)

# Redis key pattern: vendor:discount:{product_id}
_DISCOUNT_KEY = "vendor:discount:{product_id}"
_DISCOUNT_TTL = 86_400  # 24 hours — vendor discount valid for 1 day by default


class DiscountService:
    async def apply(
        self,
        body: DiscountRequest,
        original_price: float,
        vendor_id: str,
    ) -> DiscountResponse:
        """
        Persist discount to Redis and return computed response.

        Args:
            body:           Validated DiscountRequest from endpoint.
            original_price: Current product price from catalog.
            vendor_id:      Authenticated vendor's user_id.

        Raises:
            ValueError: If discount_pct exceeds the global MAX_DISCOUNT_PCT cap.
        """
        max_allowed_pct = settings.MAX_DISCOUNT_PCT * 100  # e.g. 0.40 → 40.0
        if body.discount_pct > max_allowed_pct:
            raise ValueError(
                f"Discount {body.discount_pct}% exceeds system cap of {max_allowed_pct}%"
            )

        discounted_price = round(original_price * (1 - body.discount_pct / 100), 2)
        now = datetime.now(timezone.utc)

        # Persist to Redis so the pricing engine and catalog reads can pick it up
        r = get_redis()
        key = _DISCOUNT_KEY.format(product_id=body.product_id)
        await r.hset(
            key,
            mapping={
                "discount_pct": str(body.discount_pct),
                "discounted_price": str(discounted_price),
                "original_price": str(original_price),
                "vendor_id": vendor_id,
                "reason": body.reason or "",
                "applied_at": now.isoformat(),
            },
        )
        await r.expire(key, _DISCOUNT_TTL)

        logger.info(
            "Discount %.1f%% applied to product %s by vendor %s → ₹%.2f",
            body.discount_pct,
            body.product_id,
            vendor_id,
            discounted_price,
        )

        return DiscountResponse(
            product_id=body.product_id,
            original_price=original_price,
            discounted_price=discounted_price,
            discount_pct=body.discount_pct,
            applied_at=now,
            applied_by=vendor_id,
        )

    async def get_active_discount(self, product_id: str) -> dict | None:
        """Return current discount metadata for a product, or None if none exists."""
        r = get_redis()
        key = _DISCOUNT_KEY.format(product_id=product_id)
        data = await r.hgetall(key)
        return data if data else None

    async def remove_discount(self, product_id: str) -> bool:
        """Manually clear a discount before TTL expiry."""
        r = get_redis()
        key = _DISCOUNT_KEY.format(product_id=product_id)
        deleted = await r.delete(key)
        return bool(deleted)


discount_service = DiscountService()
