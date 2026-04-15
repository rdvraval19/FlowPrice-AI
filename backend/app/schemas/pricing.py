"""
schemas/pricing.py — Pydantic schemas for the dynamic pricing pipeline.

PricingRequest → PricingEngine → PricingResponse (with PriceExplanation)
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


class PriceAdjustmentReason(str, Enum):
    """
    Human-readable reason codes mapped to UI badge copy.
    These are shown directly to users — must be fair, honest, and non-discriminatory.
    """
    HIGH_DEMAND         = "high_demand"
    LOW_DEMAND          = "low_demand"
    LIMITED_STOCK       = "limited_stock"
    FLASH_SALE          = "flash_sale"
    LOYALTY_DISCOUNT    = "loyalty_discount"
    NEW_VISITOR_OFFER   = "new_visitor_offer"
    COMPETITOR_MATCH    = "competitor_match"
    BASE_PRICE          = "base_price"           # No adjustment — showing base
    MARGIN_FLOOR_HIT    = "margin_floor_hit"     # Business rule prevented discount
    CAP_HIT             = "cap_hit"              # Business rule prevented surge


# UI copy for each reason — rendered in the tooltip transparency badge
REASON_COPY: dict[PriceAdjustmentReason, str] = {
    PriceAdjustmentReason.HIGH_DEMAND:
        "Price adjusted for high real-time demand in your area.",
    PriceAdjustmentReason.LOW_DEMAND:
        "Limited-time savings — lower demand right now.",
    PriceAdjustmentReason.LIMITED_STOCK:
        "Only a few left — price reflects limited availability.",
    PriceAdjustmentReason.FLASH_SALE:
        "Flash sale active — this price won't last long.",
    PriceAdjustmentReason.LOYALTY_DISCOUNT:
        "Your loyalty member discount is applied.",
    PriceAdjustmentReason.NEW_VISITOR_OFFER:
        "Welcome offer — exclusive savings for new visitors.",
    PriceAdjustmentReason.COMPETITOR_MATCH:
        "We matched a lower price found nearby.",
    PriceAdjustmentReason.BASE_PRICE:
        "Standard pricing — no adjustments active.",
    PriceAdjustmentReason.MARGIN_FLOOR_HIT:
        "Best available price — at our lowest margin.",
    PriceAdjustmentReason.CAP_HIT:
        "Price adjusted for demand — within our fairness cap.",
}


class PriceExplanation(BaseModel):
    """
    Transparency payload — attached to every pricing response.
    The frontend renders this as the pulsing 'i' badge tooltip.
    """
    primary_reason: PriceAdjustmentReason
    secondary_reasons: list[PriceAdjustmentReason] = []
    user_copy: str                              # Human-readable tooltip text
    discount_pct: float = Field(ge=-100, le=100)  # + = discount, - = surge
    demand_velocity: int                         # Views/5min at time of pricing
    inventory_level: int | None = None
    confidence: float = Field(ge=0, le=1)        # Model confidence in this price
    is_personalized: bool = False               # True if segment-adjusted
    fairness_checked: bool = True               # Always True — audit trail


class PricingRequest(BaseModel):
    """Input to the pricing engine for a single product + session context."""
    product_id: str
    session_id: str
    user_id: str | None = None
    user_segment: str = "unknown"
    base_price: float = Field(gt=0)
    cost_price: float = Field(gt=0)             # COGS — used for margin floor
    competitor_price: float | None = None
    inventory_level: int = Field(ge=0, default=100)
    # Injected from Feature Store — not sent by client
    engagement_score: float = 0.0
    intent_probability: float = 0.0
    demand_velocity: int = 0                    # Pre-fetched from feature store
    experiment_variant: str | None = None


class PricingResponse(BaseModel):
    """Full pricing output including the transparency explanation."""
    product_id: str
    session_id: str
    final_price: float
    base_price: float
    discount_pct: float                          # Signed: negative = surged
    explanation: PriceExplanation
    variant_id: str | None = None               # A/B variant that produced this price
    computed_in_ms: float
    cached: bool = False


class ProductPricingContext(BaseModel):
    """Lightweight context used when bulk-pricing a catalog page."""
    product_id: str
    base_price: float
    cost_price: float
    inventory_level: int = 100
    competitor_price: float | None = None


class BulkPricingRequest(BaseModel):
    """Price multiple products in one call (catalog page load)."""
    session_id: str
    user_segment: str = "unknown"
    products: list[ProductPricingContext] = Field(min_length=1, max_length=50)


class BulkPricingResponse(BaseModel):
    prices: dict[str, PricingResponse]          # product_id → PricingResponse
    session_id: str
    total_computed_ms: float
