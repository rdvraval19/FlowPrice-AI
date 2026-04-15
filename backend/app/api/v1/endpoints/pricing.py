"""
api/v1/endpoints/pricing.py — Dynamic Pricing API

Endpoints:
  GET  /api/v1/pricing/{product_id}         — Single product price for a session
  POST /api/v1/pricing/bulk                 — Catalog-page bulk pricing
  GET  /api/v1/pricing/stream/{session_id}  — SSE live price updates
  GET  /api/v1/pricing/audit/{product_id}   — Fairness audit log for a product
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.redis_client import feature_store, get_redis
from app.schemas.pricing import (
    BulkPricingRequest,
    BulkPricingResponse,
    PricingRequest,
    PricingResponse,
)
from app.services.pricing.engine import price_bulk, price_product

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pricing", tags=["Pricing"])


@router.get(
    "/{product_id}",
    response_model=PricingResponse,
    summary="Get dynamic price for a product",
    description=(
        "Returns the real-time dynamic price for a product within a session context. "
        "Includes a PriceExplanation payload for the transparency badge UI. "
        "Cache hit: < 1ms. Cache miss: < 10ms."
    ),
)
async def get_product_price(
    product_id: str,
    session_id: str = Query(..., min_length=8),
    user_segment: str = Query(default="unknown"),
    base_price: float = Query(..., gt=0),
    cost_price: float = Query(..., gt=0),
    inventory_level: int = Query(default=100, ge=0),
    competitor_price: float | None = Query(default=None),
    experiment_variant: str | None = Query(default=None),
) -> PricingResponse:
    """
    Single-product pricing endpoint.

    The frontend calls this on every Product Detail Page load.
    Session features are fetched from the Feature Store to personalize the price.
    """
    # Fetch live session features to get intent probability + engagement
    session_features = await feature_store.get_session_features(session_id)
    demand_velocity = await feature_store.get_demand_velocity(product_id)

    req = PricingRequest(
        product_id=product_id,
        session_id=session_id,
        user_segment=user_segment,
        base_price=base_price,
        cost_price=cost_price,
        inventory_level=inventory_level,
        competitor_price=competitor_price,
        engagement_score=float(session_features.get("engagement_score", 0.0)),
        intent_probability=float(session_features.get("intent_probability", 0.0)),
        demand_velocity=demand_velocity,
        experiment_variant=experiment_variant,
    )

    try:
        response = await price_product(req)
    except Exception as exc:
        logger.error("Pricing error product=%s: %s", product_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pricing service temporarily unavailable",
        ) from exc

    return response


@router.post(
    "/bulk",
    response_model=BulkPricingResponse,
    summary="Bulk price a product catalog (catalog page load)",
    description=(
        "Prices up to 50 products concurrently using asyncio.gather. "
        "Total latency ≈ slowest single product. "
        "Used for storefront catalog page rendering."
    ),
)
async def bulk_price_products(req: BulkPricingRequest) -> BulkPricingResponse:
    try:
        return await price_bulk(req)
    except Exception as exc:
        logger.error("Bulk pricing error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bulk pricing temporarily unavailable",
        ) from exc


@router.get(
    "/stream/{session_id}",
    summary="SSE: live price updates for a session",
    description=(
        "Server-Sent Events stream that pushes price updates when demand "
        "conditions change significantly. Frontend subscribes once per product "
        "page visit and receives push updates without polling."
    ),
)
async def stream_price_updates(
    session_id: str,
    product_id: str = Query(...),
    base_price: float = Query(..., gt=0),
    cost_price: float = Query(..., gt=0),
) -> StreamingResponse:
    return StreamingResponse(
        _price_sse_generator(session_id, product_id, base_price, cost_price),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _price_sse_generator(
    session_id: str,
    product_id: str,
    base_price: float,
    cost_price: float,
) -> AsyncGenerator[str, None]:
    """
    Polls for demand velocity changes every 10 seconds.
    Only pushes an update if the price changed by > 0.5%.
    Prevents UI flickering from micro-fluctuations.
    """
    last_price: float | None = None
    last_velocity = -1

    yield f"data: {json.dumps({'type': 'connected', 'product_id': product_id})}\n\n"

    while True:
        try:
            velocity = await feature_store.get_demand_velocity(product_id)

            # Only recompute if velocity changed meaningfully
            if abs(velocity - last_velocity) >= 2:
                req = PricingRequest(
                    product_id=product_id,
                    session_id=session_id,
                    base_price=base_price,
                    cost_price=cost_price,
                    demand_velocity=velocity,
                )
                result = await price_product(req)

                # Only push if price changed by > 0.5%
                if last_price is None or abs(result.final_price - last_price) / max(last_price, 0.01) > 0.005:
                    last_price = result.final_price
                    last_velocity = velocity

                    payload = {
                        "type": "price_update",
                        "product_id": product_id,
                        "final_price": result.final_price,
                        "base_price": result.base_price,
                        "discount_pct": result.discount_pct,
                        "reason": result.explanation.primary_reason.value,
                        "user_copy": result.explanation.user_copy,
                        "demand_velocity": velocity,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"

            await asyncio.sleep(10)   # Check every 10 seconds

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Price SSE error: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
            await asyncio.sleep(5)


@router.get(
    "/audit/{product_id}",
    summary="Fairness audit log for a product",
    description="Returns recent price history across segments for fairness review.",
)
async def get_pricing_audit(product_id: str) -> dict:
    """
    Returns recent pricing decisions for a product across all segments.
    Used by the admin dashboard fairness panel.
    """
    segments = ["new_visitor", "returning", "loyalty", "high_value", "price_sensitive"]
    audit = {}

    for segment in segments:
        cached = await feature_store.get_cached_price(product_id, segment)
        audit[segment] = {
            "cached_price": cached,
            "has_active_price": cached is not None,
        }

    # Compute price spread — a large spread may indicate fairness issues
    active_prices = [v["cached_price"] for v in audit.values() if v["cached_price"]]
    spread_pct = 0.0
    if len(active_prices) >= 2:
        spread_pct = round((max(active_prices) - min(active_prices)) / max(active_prices) * 100, 2)

    return {
        "product_id": product_id,
        "segment_prices": audit,
        "price_spread_pct": spread_pct,
        "fairness_flag": spread_pct > 30,   # Flag if > 30% spread across segments
        "audited_at_ms": int(time.time() * 1000),
    }
