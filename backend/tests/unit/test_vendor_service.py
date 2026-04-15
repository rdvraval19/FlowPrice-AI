"""
tests/unit/test_vendor_service.py

Unit tests for discount, coupon, and sponsor services.
Redis and DB are mocked — no infrastructure required.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.vendor import (
    CouponRedeemRequest,
    CouponRequest,
    DiscountRequest,
    SponsorRequest,
)


# ── Discount Service ──────────────────────────────────────────────────────────

class TestDiscountService:
    @pytest.mark.asyncio
    async def test_apply_discount_success(self):
        from app.services.vendor.discount_service import DiscountService

        mock_redis = AsyncMock()
        mock_redis.hset = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch("app.services.vendor.discount_service.get_redis", return_value=mock_redis):
            svc = DiscountService()
            body = DiscountRequest(product_id="prod-1", discount_pct=20.0)
            result = await svc.apply(body, original_price=100.0, vendor_id="vendor-123")

        assert result.product_id == "prod-1"
        assert result.discounted_price == 80.0
        assert result.discount_pct == 20.0
        assert result.applied_by == "vendor-123"

    @pytest.mark.asyncio
    async def test_apply_discount_exceeds_cap(self):
        from app.services.vendor.discount_service import DiscountService

        mock_redis = AsyncMock()
        with patch("app.services.vendor.discount_service.get_redis", return_value=mock_redis):
            svc = DiscountService()
            body = DiscountRequest(product_id="prod-1", discount_pct=99.0)

            with pytest.raises(ValueError, match="exceeds system cap"):
                await svc.apply(body, original_price=100.0, vendor_id="vendor-123")

    @pytest.mark.asyncio
    async def test_remove_discount(self):
        from app.services.vendor.discount_service import DiscountService

        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=1)

        with patch("app.services.vendor.discount_service.get_redis", return_value=mock_redis):
            svc = DiscountService()
            result = await svc.remove_discount("prod-1")

        assert result is True

    @pytest.mark.asyncio
    async def test_discount_price_rounds_to_2dp(self):
        from app.services.vendor.discount_service import DiscountService

        mock_redis = AsyncMock()
        mock_redis.hset = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch("app.services.vendor.discount_service.get_redis", return_value=mock_redis):
            svc = DiscountService()
            body = DiscountRequest(product_id="prod-2", discount_pct=33.0)
            result = await svc.apply(body, original_price=99.99, vendor_id="v-1")

        # 99.99 * (1 - 0.33) = 66.9933 → rounds to 66.99
        assert result.discounted_price == 66.99


# ── Coupon Service ────────────────────────────────────────────────────────────

class TestCouponService:
    def _mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        return db

    def _mock_pipeline(self, mock_redis):
        pipe = AsyncMock()
        pipe.__aenter__ = AsyncMock(return_value=pipe)
        pipe.__aexit__ = AsyncMock(return_value=False)
        pipe.hset = AsyncMock()
        pipe.expire = AsyncMock()
        pipe.set = AsyncMock()
        pipe.execute = AsyncMock(return_value=[True, True, True, True])
        mock_redis.pipeline = MagicMock(return_value=pipe)

    @pytest.mark.asyncio
    async def test_create_coupon_auto_code(self):
        from app.services.vendor.coupon_service import CouponService

        mock_redis = AsyncMock()
        self._mock_pipeline(mock_redis)
        db = self._mock_db()

        with patch("app.services.vendor.coupon_service.get_redis", return_value=mock_redis):
            svc = CouponService()
            body = CouponRequest(discount_pct=15.0, max_uses=5)
            result = await svc.create(body, vendor_id="v-1", db=db)

        assert len(result.code) == 8
        assert result.code.isupper()
        assert result.discount_pct == 15.0
        assert result.uses_remaining == 5

    @pytest.mark.asyncio
    async def test_create_coupon_custom_code(self):
        from app.services.vendor.coupon_service import CouponService

        mock_redis = AsyncMock()
        self._mock_pipeline(mock_redis)
        db = self._mock_db()

        with patch("app.services.vendor.coupon_service.get_redis", return_value=mock_redis):
            svc = CouponService()
            body = CouponRequest(code="SAVE20", discount_pct=20.0)
            result = await svc.create(body, vendor_id="v-1", db=db)

        assert result.code == "SAVE20"

    @pytest.mark.asyncio
    async def test_redeem_coupon_success(self):
        from app.services.vendor.coupon_service import CouponService

        mock_redis = AsyncMock()
        mock_redis.hgetall = AsyncMock(return_value={
            "discount_pct": "20.0",
            "target": "all",
            "target_id": "",
            "max_uses": "5",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "created_by": "v-1",
        })
        mock_redis.get = AsyncMock(return_value="2")
        mock_redis.incr = AsyncMock(return_value=3)

        coupon_obj = MagicMock()
        coupon_obj.uses_count = 2
        coupon_obj.max_uses = 5

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=coupon_obj)
        db.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.vendor.coupon_service.get_redis", return_value=mock_redis):
            svc = CouponService()
            body = CouponRedeemRequest(code="SAVE20", user_id="user-1", cart_total=100.0)
            result = await svc.redeem(body, db)

        assert result.valid is True
        assert result.discount_pct == 20.0
        assert result.discounted_total == 80.0

    @pytest.mark.asyncio
    async def test_redeem_expired_coupon(self):
        from app.services.vendor.coupon_service import CouponService

        mock_redis = AsyncMock()
        mock_redis.hgetall = AsyncMock(return_value={})

        db = AsyncMock()
        with patch("app.services.vendor.coupon_service.get_redis", return_value=mock_redis):
            svc = CouponService()
            body = CouponRedeemRequest(code="OLD999", user_id="user-1", cart_total=50.0)
            result = await svc.redeem(body, db)

        assert result.valid is False

    @pytest.mark.asyncio
    async def test_redeem_max_uses_reached(self):
        from app.services.vendor.coupon_service import CouponService

        mock_redis = AsyncMock()
        mock_redis.hgetall = AsyncMock(return_value={
            "discount_pct": "10.0",
            "target": "all",
            "target_id": "",
            "max_uses": "2",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "created_by": "v-1",
        })
        mock_redis.get = AsyncMock(return_value="2")

        db = AsyncMock()
        with patch("app.services.vendor.coupon_service.get_redis", return_value=mock_redis):
            svc = CouponService()
            body = CouponRedeemRequest(code="LIMIT2", user_id="user-1", cart_total=50.0)
            result = await svc.redeem(body, db)

        assert result.valid is False
        assert "limit" in result.message.lower()


# ── Sponsor Service ───────────────────────────────────────────────────────────

class TestSponsorService:
    def _mock_pipeline(self, mock_redis):
        pipe = AsyncMock()
        pipe.__aenter__ = AsyncMock(return_value=pipe)
        pipe.__aexit__ = AsyncMock(return_value=False)
        pipe.hset = AsyncMock()
        pipe.expire = AsyncMock()
        pipe.execute = AsyncMock(return_value=[True, True])
        mock_redis.pipeline = MagicMock(return_value=pipe)

    @pytest.mark.asyncio
    async def test_sponsor_product(self):
        from app.services.vendor.sponsor_service import SponsorService

        mock_redis = AsyncMock()
        self._mock_pipeline(mock_redis)

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[]))
        )
        db.execute = AsyncMock(return_value=mock_result)
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.services.vendor.sponsor_service.get_redis", return_value=mock_redis):
            svc = SponsorService()
            body = SponsorRequest(product_id="prod-99", duration_hours=48)
            result = await svc.sponsor(body, vendor_id="v-1", db=db)

        assert result.product_id == "prod-99"
        assert result.is_sponsored is True
        assert result.badge_label == "Sponsored"

    @pytest.mark.asyncio
    async def test_is_sponsored_true(self):
        from app.services.vendor.sponsor_service import SponsorService

        mock_redis = AsyncMock()
        mock_redis.hgetall = AsyncMock(return_value={
            "badge_label": "Hot Deal",
            "sponsored_until": "2099-01-01T00:00:00+00:00",
            "sponsored_by": "v-1",
        })

        with patch("app.services.vendor.sponsor_service.get_redis", return_value=mock_redis):
            svc = SponsorService()
            is_sponsored, label = await svc.is_sponsored("prod-99")

        assert is_sponsored is True
        assert label == "Hot Deal"

    @pytest.mark.asyncio
    async def test_is_sponsored_false(self):
        from app.services.vendor.sponsor_service import SponsorService

        mock_redis = AsyncMock()
        mock_redis.hgetall = AsyncMock(return_value={})

        with patch("app.services.vendor.sponsor_service.get_redis", return_value=mock_redis):
            svc = SponsorService()
            is_sponsored, label = await svc.is_sponsored("prod-99")

        assert is_sponsored is False
