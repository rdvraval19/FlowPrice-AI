"""
tests/integration/test_event_ingestion.py

Integration tests for the clickstream event ingestion pipeline.
Uses fakeredis so no live Redis instance is required.

Run: pytest tests/integration/test_event_ingestion.py -v
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ── Test Fixtures ─────────────────────────────────────────────────────────────

VALID_SESSION_ID = "sess_test_abcdef1234567890"


def _make_product_view_payload(session_id: str = VALID_SESSION_ID) -> dict:
    return {
        "session_id": session_id,
        "event_type": "product_view",
        "timestamp_ms": int(time.time() * 1000),
        "device_type": "desktop",
        "user_segment": "returning",
        "referral_source": "organic",
        "product": {
            "product_id": "prod_nike_air_001",
            "category": "sneakers",
            "price_shown": 129.99,
            "base_price": 149.99,
            "inventory_level": 42,
        },
    }


def _make_cart_add_payload(session_id: str = VALID_SESSION_ID) -> dict:
    return {
        "session_id": session_id,
        "event_type": "cart_add",
        "timestamp_ms": int(time.time() * 1000),
        "device_type": "mobile",
        "user_segment": "loyalty",
        "product": {
            "product_id": "prod_nike_air_001",
            "category": "sneakers",
            "price_shown": 129.99,
            "base_price": 149.99,
        },
    }


def _make_purchase_payload(session_id: str = VALID_SESSION_ID) -> dict:
    return {
        "session_id": session_id,
        "event_type": "purchase",
        "timestamp_ms": int(time.time() * 1000),
        "device_type": "desktop",
        "user_segment": "high_value",
        "product": None,
        "purchase": {
            "order_id": "ord_20240101_abc",
            "items": [{"product_id": "prod_001", "qty": 1, "unit_price": 129.99}],
            "order_total": 129.99,
            "payment_method": "card",
            "coupon_used": False,
        },
    }


# ── Mock Redis for Unit/Integration Tests ─────────────────────────────────────

@pytest.fixture
def mock_redis_client():
    """Replace Redis with an in-memory fake."""
    import fakeredis.aioredis as fakeredis

    fake = fakeredis.FakeRedis(decode_responses=True)

    with patch("app.core.redis_client._redis", fake), \
         patch("app.core.redis_client.get_redis", return_value=fake), \
         patch("app.core.redis_client.stream_writer.write", new_callable=AsyncMock) as mock_write, \
         patch("app.core.redis_client.feature_store.update_session_features", new_callable=AsyncMock), \
         patch("app.core.redis_client.feature_store.get_session_features", return_value={}), \
         patch("app.core.redis_client.feature_store.get_top_categories", return_value=[]), \
         patch("app.core.redis_client.feature_store.record_product_view", new_callable=AsyncMock), \
         patch("app.core.redis_client.feature_store.get_demand_velocity", return_value=15), \
         patch("app.core.redis_client.feature_store.record_latency", new_callable=AsyncMock):

        mock_write.return_value = "1700000000000-0"
        yield fake


@pytest_asyncio.fixture
async def client(mock_redis_client):
    """AsyncClient with mocked Redis injected."""
    from app.main import create_app

    with patch("app.main.init_redis", new_callable=AsyncMock), \
         patch("app.main.close_redis", new_callable=AsyncMock), \
         patch("app.main._run_stream_consumer", new_callable=AsyncMock):

        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestSingleEventIngestion:
    @pytest.mark.asyncio
    async def test_product_view_returns_202(self, client, mock_redis_client):
        """Happy path: product_view event is accepted."""
        resp = await client.post(
            "/api/v1/events/ingest",
            json=_make_product_view_payload(),
        )
        assert resp.status_code == 202

    @pytest.mark.asyncio
    async def test_response_contains_event_id(self, client, mock_redis_client):
        resp = await client.post(
            "/api/v1/events/ingest",
            json=_make_product_view_payload(),
        )
        body = resp.json()
        assert "event_id" in body
        assert body["success"] is True

    @pytest.mark.asyncio
    async def test_response_contains_latency_ms(self, client, mock_redis_client):
        resp = await client.post(
            "/api/v1/events/ingest",
            json=_make_product_view_payload(),
        )
        body = resp.json()
        assert "latency_ms" in body
        assert isinstance(body["latency_ms"], float)
        # Validate sub-200ms (with mocked Redis this should be < 50ms)
        assert body["latency_ms"] < 200.0

    @pytest.mark.asyncio
    async def test_x_response_time_header_present(self, client, mock_redis_client):
        resp = await client.post(
            "/api/v1/events/ingest",
            json=_make_product_view_payload(),
        )
        assert "x-response-time" in resp.headers

    @pytest.mark.asyncio
    async def test_cart_add_requires_product_context(self, client, mock_redis_client):
        payload = {
            "session_id": VALID_SESSION_ID,
            "event_type": "cart_add",
            "timestamp_ms": int(time.time() * 1000),
            # Missing product context — should fail validation
        }
        resp = await client.post("/api/v1/events/ingest", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_purchase_requires_purchase_context(self, client, mock_redis_client):
        payload = {
            "session_id": VALID_SESSION_ID,
            "event_type": "purchase",
            "timestamp_ms": int(time.time() * 1000),
            # Missing purchase context — should fail validation
        }
        resp = await client.post("/api/v1/events/ingest", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_event_type_rejected(self, client, mock_redis_client):
        payload = _make_product_view_payload()
        payload["event_type"] = "invalid_event_type_xyz"
        resp = await client.post("/api/v1/events/ingest", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_short_session_id_rejected(self, client, mock_redis_client):
        payload = _make_product_view_payload()
        payload["session_id"] = "short"   # < 16 chars
        resp = await client.post("/api/v1/events/ingest", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_cart_add_accepted(self, client, mock_redis_client):
        resp = await client.post(
            "/api/v1/events/ingest",
            json=_make_cart_add_payload(),
        )
        assert resp.status_code == 202
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_purchase_event_accepted(self, client, mock_redis_client):
        resp = await client.post(
            "/api/v1/events/ingest",
            json=_make_purchase_payload(),
        )
        assert resp.status_code == 202


class TestBatchIngestion:
    @pytest.mark.asyncio
    async def test_batch_ingest_accepted(self, client, mock_redis_client):
        with patch(
            "app.core.redis_client.stream_writer.write_batch",
            new_callable=AsyncMock,
            return_value=["1700000000000-0", "1700000000001-0"],
        ):
            resp = await client.post(
                "/api/v1/events/ingest/batch",
                json={"events": [
                    _make_product_view_payload(),
                    _make_cart_add_payload(),
                ]},
            )
        assert resp.status_code == 202
        body = resp.json()
        assert body["accepted"] == 2
        assert body["rejected"] == 0

    @pytest.mark.asyncio
    async def test_empty_batch_rejected(self, client, mock_redis_client):
        resp = await client.post(
            "/api/v1/events/ingest/batch",
            json={"events": []},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_batch_deduplication(self, client, mock_redis_client):
        """Duplicate events in a batch should be deduplicated."""
        event = _make_product_view_payload()
        with patch(
            "app.core.redis_client.stream_writer.write_batch",
            new_callable=AsyncMock,
            return_value=["1700000000000-0"],   # Only 1 written
        ):
            resp = await client.post(
                "/api/v1/events/ingest/batch",
                json={"events": [event, event]},  # Same event twice
            )
        assert resp.status_code == 202
        # Deduplication happens in the schema validator
        assert resp.json()["accepted"] <= 1


class TestSessionFeatures:
    @pytest.mark.asyncio
    async def test_session_features_endpoint(self, client, mock_redis_client):
        resp = await client.get(
            f"/api/v1/events/session/{VALID_SESSION_ID}/features"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == VALID_SESSION_ID
        assert "features" in body
        assert "top_categories" in body


class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_health_check(self, client, mock_redis_client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] in ("healthy", "degraded")
