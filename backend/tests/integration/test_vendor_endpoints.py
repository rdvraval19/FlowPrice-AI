"""
tests/integration/test_vendor_endpoints.py

Integration tests for all vendor panel endpoints.
Uses FastAPI TestClient with overridden dependencies.
Requires a vendor-role JWT to pass require_vendor.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient

from app.main import app
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_vendor() -> User:
    u = User()
    u.id = "vendor-uuid-001"
    u.email = "vendor@test.com"
    u.role = "vendor"
    u.is_active = True
    return u


def _make_user() -> User:
    u = User()
    u.id = "user-uuid-002"
    u.email = "user@test.com"
    u.role = "user"
    u.is_active = True
    return u


@pytest.fixture
def vendor_client():
    """AsyncClient authenticated as vendor."""
    vendor = _make_vendor()
    app.dependency_overrides[get_current_user] = lambda: vendor
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def user_client():
    """AsyncClient authenticated as regular user — should get 403 on vendor routes."""
    user = _make_user()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    yield
    app.dependency_overrides.clear()


# ── Discount endpoint ─────────────────────────────────────────────────────────

class TestDiscountEndpoint:
    @pytest.mark.asyncio
    async def test_apply_discount_vendor(self, vendor_client):
        mock_redis = AsyncMock()
        mock_redis.hset = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch("app.services.vendor.discount_service.get_redis", return_value=mock_redis):
            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/vendor/discount",
                    json={"product_id": "prod-1", "discount_pct": 15.0},
                    params={"original_price": 200.0},
                )
        assert response.status_code == 200
        data = response.json()
        assert data["discounted_price"] == 170.0
        assert data["discount_pct"] == 15.0

    @pytest.mark.asyncio
    async def test_apply_discount_forbidden_for_user(self, user_client):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/vendor/discount",
                json={"product_id": "prod-1", "discount_pct": 10.0},
                params={"original_price": 100.0},
            )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_apply_discount_exceeds_cap(self, vendor_client):
        mock_redis = AsyncMock()
        with patch("app.services.vendor.discount_service.get_redis", return_value=mock_redis):
            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/vendor/discount",
                    json={"product_id": "prod-1", "discount_pct": 99.0},
                    params={"original_price": 100.0},
                )
        assert response.status_code == 422


# ── Coupon endpoint ───────────────────────────────────────────────────────────

class TestCouponEndpoint:
    @pytest.mark.asyncio
    async def test_create_coupon(self, vendor_client):
        mock_redis = AsyncMock()
        pipe = AsyncMock()
        pipe.__aenter__ = AsyncMock(return_value=pipe)
        pipe.__aexit__ = AsyncMock(return_value=False)
        pipe.hset = AsyncMock()
        pipe.expire = AsyncMock()
        pipe.set = AsyncMock()
        pipe.execute = AsyncMock(return_value=[True, True, True, True])
        mock_redis.pipeline = MagicMock(return_value=pipe)

        with patch("app.services.vendor.coupon_service.get_redis", return_value=mock_redis):
            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/vendor/coupon",
                    json={"discount_pct": 10.0, "max_uses": 100, "ttl_minutes": 60},
                )
        assert response.status_code == 201
        data = response.json()
        assert "code" in data
        assert data["discount_pct"] == 10.0

    @pytest.mark.asyncio
    async def test_redeem_coupon_open_endpoint(self):
        """Redeem endpoint is open — no auth required."""
        mock_redis = AsyncMock()
        mock_redis.hgetall = AsyncMock(return_value={
            "discount_pct": "25.0",
            "target": "all",
            "target_id": "",
            "max_uses": "10",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "created_by": "v-1",
        })
        mock_redis.get = AsyncMock(return_value="0")
        mock_redis.incr = AsyncMock(return_value=1)

        coupon_obj = MagicMock()
        coupon_obj.uses_count = 0
        coupon_obj.max_uses = 10

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=coupon_obj)
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = lambda: db

        with patch("app.services.vendor.coupon_service.get_redis", return_value=mock_redis):
            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/vendor/coupon/redeem",
                    json={"code": "SAVE25", "user_id": "user-1", "cart_total": 100.0},
                )
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["discounted_total"] == 75.0


# ── Sponsor endpoint ──────────────────────────────────────────────────────────

class TestSponsorEndpoint:
    @pytest.mark.asyncio
    async def test_sponsor_product(self, vendor_client):
        mock_redis = AsyncMock()
        pipe = AsyncMock()
        pipe.__aenter__ = AsyncMock(return_value=pipe)
        pipe.__aexit__ = AsyncMock(return_value=False)
        pipe.hset = AsyncMock()
        pipe.expire = AsyncMock()
        pipe.execute = AsyncMock(return_value=[True, True])
        mock_redis.pipeline = MagicMock(return_value=pipe)

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[]))
        )
        db.execute = AsyncMock(return_value=mock_result)
        db.add = MagicMock()
        db.flush = AsyncMock()
        app.dependency_overrides[get_db] = lambda: db

        with patch("app.services.vendor.sponsor_service.get_redis", return_value=mock_redis):
            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/vendor/sponsor",
                    json={"product_id": "prod-99", "duration_hours": 24},
                )
        assert response.status_code == 201
        data = response.json()
        assert data["is_sponsored"] is True
        assert data["product_id"] == "prod-99"


# ── Notify endpoint ───────────────────────────────────────────────────────────

class TestNotifyEndpoint:
    @pytest.mark.asyncio
    async def test_notify_without_smtp_config(self, vendor_client):
        """Should return 200 with sent=False when SMTP not configured."""
        with patch(
            "app.services.vendor.notification_service._get_smtp_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(
                SMTP_HOST=None,
                SMTP_USERNAME=None,
                SMTP_PASSWORD=None,
                APP_NAME="TestApp",
            )
            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/vendor/notify",
                    json={
                        "user_email": "buyer@test.com",
                        "coupon_code": "HELLO10",
                        "subject": "Your coupon",
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["sent"] is False
        assert data["recipient"] == "buyer@test.com"
