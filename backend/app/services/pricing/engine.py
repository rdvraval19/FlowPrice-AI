"""
services/pricing/engine.py — Dynamic Pricing Engine Orchestrator.

Execution pipeline per request:
  1. Check Redis cache (< 1ms if hit)
  2. Fetch demand velocity from Feature Store
  3. Run demand model → demand_score + adjustment_pct
  4. Apply segment willingness-to-pay modifier
  5. Apply business rules (margin floor, caps, fairness)
  6. Generate price explanation
  7. Cache result with TTL
  8. Return PricingResponse

Total target: < 10ms on cache miss, < 1ms on cache hit.
"""
from __future__ import annotations

import logging
import time

from app.core.config import settings
from app.core.redis_client import feature_store
from app.schemas.pricing import (
    BulkPricingRequest,
    BulkPricingResponse,
    PricingRequest,
    PricingResponse,
)
from app.services.pricing.business_rules import business_rules
from app.services.pricing.demand_model import compute_demand_score, velocity_to_adjustment_pct
from app.services.pricing.explainer import generate_explanation
from app.services.pricing.circuit_breaker import circuit_breaker

import asyncio

logger = logging.getLogger(__name__)

# Willingness-to-pay multipliers by segment.
# Applied AFTER demand model, BEFORE business rules.
# Based on behavioural signals only — never demographic attributes.
SEGMENT_WTP_MULTIPLIERS: dict[str, float] = {
    "loyalty":        0.92,   # Reward loyalty with a 8% discount
    "high_value":     1.00,   # Full price — already proven buyers
    "returning":      0.97,   # Small retention discount
    "new_visitor":    0.95,   # Acquisition discount to convert
    "price_sensitive": 0.90,  # Larger discount to overcome barrier
    "unknown":        1.00,   # No adjustment on unknown segment
}


async def price_product(req: PricingRequest) -> PricingResponse:
    """
    Main entry point for single-product dynamic pricing.
    Fetches live signals, runs models, enforces rules, returns explanation.
    """
    t0 = time.perf_counter()

    # ── 1. Cache Check ────────────────────────────────────────────────────────
    # Cache key includes segment so different segments get their own entries
    cached_price = await feature_store.get_cached_price(req.product_id, req.user_segment)
    if cached_price is not None:
        elapsed = (time.perf_counter() - t0) * 1000
        logger.debug("Price cache HIT product=%s [%.2f ms]", req.product_id, elapsed)
        # Reconstruct a lightweight response from cached value
        return _build_cached_response(req, cached_price, elapsed)

    # ── 2. Fetch Live Demand Velocity ─────────────────────────────────────────
    # Use pre-computed value if provided (e.g. from batch context), else fetch
    velocity = req.demand_velocity
    if velocity == 0:
        velocity = await feature_store.get_demand_velocity(req.product_id)

    # ── 3. Demand Model ───────────────────────────────────────────────────────
    demand = compute_demand_score(
        velocity=velocity,
        inventory=req.inventory_level,
        base_price=req.base_price,
        competitor_price=req.competitor_price,
    )

    raw_adjustment_pct = velocity_to_adjustment_pct(
        demand.demand_score,
        max_surge=settings.MAX_SURGE_PCT,
        max_discount=settings.MAX_DISCOUNT_PCT,
    )

    # ── 4. Segment WTP Adjustment ─────────────────────────────────────────────
    # Modifies the adjustment independently of demand
    # e.g. loyalty member on a high-demand product still gets their discount
    wtp_mult = SEGMENT_WTP_MULTIPLIERS.get(req.user_segment, 1.0)
    proposed_price = req.base_price * (1.0 + raw_adjustment_pct) * wtp_mult

    # ── 5. Intent Boost (high-intent users see slightly better prices) ─────────
    # Small nudge to convert high-intent sessions — rewards engagement
    if req.intent_probability > 0.7 and req.user_segment not in ("high_value",):
        intent_discount = 0.02 * (req.intent_probability - 0.7) / 0.3  # Max 2%
        proposed_price *= (1.0 - intent_discount)

    # ── 6. Business Rules (always last, always enforced) ─────────────────────
    rules = business_rules.apply(
        proposed_price=proposed_price,
        base_price=req.base_price,
        cost_price=req.cost_price,
        user_segment=req.user_segment,
    )
    final_price = rules.final_price

    # ── 6b. Circuit Breaker — absolute safety valve ─────────────────────────
    # Runs AFTER business rules as a final hard-stop.
    # Catches catastrophic model failures (e.g., TV priced at ₹100).
    cb_price, was_clamped, cb_trip = await circuit_breaker.check_and_clamp(
        proposed_price=final_price,
        product_id=req.product_id,
        base_price=req.base_price,
        cost_price=req.cost_price,
        context=f"segment={req.user_segment}",
    )
    if was_clamped:
        # Override the business-rules price with the circuit-breaker safe price
        final_price = cb_price
        if cb_trip:
            logger.warning(
                "⚡ Circuit breaker clamped %s: %.2f → %.2f (%s)",
                req.product_id, rules.final_price, final_price, cb_trip.rule_violated
            )

    # ── 7. Generate Explanation ───────────────────────────────────────────────
    explanation = generate_explanation(
        demand=demand,
        rules=rules,
        final_price=final_price,
        base_price=req.base_price,
        user_segment=req.user_segment,
        inventory=req.inventory_level,
    )

    # ── 8. Cache Result ───────────────────────────────────────────────────────
    await feature_store.cache_price(req.product_id, req.user_segment, final_price)

    elapsed = (time.perf_counter() - t0) * 1000
    discount_pct = round((req.base_price - final_price) / req.base_price * 100, 1)

    logger.info(
        "Priced product=%s segment=%s base=%.2f final=%.2f "
        "demand=%.3f adjustment=%.1f%% [%.2f ms]",
        req.product_id, req.user_segment,
        req.base_price, final_price,
        demand.demand_score, raw_adjustment_pct * 100, elapsed,
    )

    return PricingResponse(
        product_id=req.product_id,
        session_id=req.session_id,
        final_price=final_price,
        base_price=req.base_price,
        discount_pct=discount_pct,
        explanation=explanation,
        variant_id=req.experiment_variant,
        computed_in_ms=round(elapsed, 2),
        cached=False,
    )


async def price_bulk(req: BulkPricingRequest) -> BulkPricingResponse:
    """
    Price multiple products concurrently — used for catalog page loads.
    All pricing calls run in parallel; total time ≈ slowest single call.
    """
    t0 = time.perf_counter()

    tasks = [
        price_product(PricingRequest(
            product_id=p.product_id,
            session_id=req.session_id,
            user_segment=req.user_segment,
            base_price=p.base_price,
            cost_price=p.cost_price,
            inventory_level=p.inventory_level,
            competitor_price=p.competitor_price,
        ))
        for p in req.products
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    prices: dict[str, PricingResponse] = {}
    for product, result in zip(req.products, results):
        if isinstance(result, Exception):
            logger.error("Pricing failed for product=%s: %s", product.product_id, result)
            # Fallback: return base price with neutral explanation
            prices[product.product_id] = _fallback_response(
                product.product_id, req.session_id, product.base_price
            )
        else:
            prices[product.product_id] = result

    total_ms = round((time.perf_counter() - t0) * 1000, 2)
    return BulkPricingResponse(
        prices=prices,
        session_id=req.session_id,
        total_computed_ms=total_ms,
    )


def _build_cached_response(
    req: PricingRequest, cached_price: float, elapsed_ms: float
) -> PricingResponse:
    """Lightweight response from cached price — avoids full model re-run."""
    from app.schemas.pricing import PriceAdjustmentReason, PriceExplanation, REASON_COPY
    discount_pct = round((req.base_price - cached_price) / req.base_price * 100, 1)

    # Determine primary reason from discount direction
    if discount_pct > 1:
        reason = PriceAdjustmentReason.LOW_DEMAND
    elif discount_pct < -1:
        reason = PriceAdjustmentReason.HIGH_DEMAND
    else:
        reason = PriceAdjustmentReason.BASE_PRICE

    return PricingResponse(
        product_id=req.product_id,
        session_id=req.session_id,
        final_price=cached_price,
        base_price=req.base_price,
        discount_pct=discount_pct,
        explanation=PriceExplanation(
            primary_reason=reason,
            user_copy=REASON_COPY[reason],
            discount_pct=discount_pct,
            demand_velocity=req.demand_velocity,
            inventory_level=req.inventory_level,
            confidence=0.85,
            fairness_checked=True,
        ),
        computed_in_ms=elapsed_ms,
        cached=True,
    )


def _fallback_response(
    product_id: str, session_id: str, base_price: float
) -> PricingResponse:
    """Safe fallback when pricing fails — never show a broken UI."""
    from app.schemas.pricing import PriceAdjustmentReason, PriceExplanation, REASON_COPY
    return PricingResponse(
        product_id=product_id,
        session_id=session_id,
        final_price=round(base_price, 2),
        base_price=base_price,
        discount_pct=0.0,
        explanation=PriceExplanation(
            primary_reason=PriceAdjustmentReason.BASE_PRICE,
            user_copy=REASON_COPY[PriceAdjustmentReason.BASE_PRICE],
            discount_pct=0.0,
            demand_velocity=0,
            confidence=1.0,
            fairness_checked=True,
        ),
        computed_in_ms=0.0,
        cached=False,
    )
