"""
schemas/event.py — Pydantic v2 schemas for the clickstream event pipeline.

Design principles:
  • Strict validation at the API boundary — fail fast, fail loudly.
  • Enums for all categorical fields — prevent garbage from entering the stream.
  • Computed fields (event_id, server_timestamp) injected server-side.
  • EventBatch supports bulk ingest for SDK/mobile clients.
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Event Type Enum ───────────────────────────────────────────────────────────

class EventType(str, Enum):
    """
    Canonical event taxonomy.
    Ordering loosely mirrors a typical purchase funnel.
    """
    # Discovery
    PAGE_VIEW       = "page_view"
    SEARCH          = "search"
    CATEGORY_BROWSE = "category_browse"
    # Engagement
    PRODUCT_VIEW    = "product_view"
    IMAGE_ZOOM      = "image_zoom"
    REVIEW_READ     = "review_read"
    # Intent
    WISHLIST_ADD    = "wishlist_add"
    CART_ADD        = "cart_add"
    CART_REMOVE     = "cart_remove"
    CART_VIEW       = "cart_view"
    CHECKOUT_START  = "checkout_start"
    # Conversion
    PURCHASE        = "purchase"
    # Post-purchase
    RETURN_INITIATE = "return_initiate"
    # System
    SESSION_START   = "session_start"
    SESSION_END     = "session_end"


class DeviceType(str, Enum):
    DESKTOP = "desktop"
    MOBILE  = "mobile"
    TABLET  = "tablet"
    APP     = "app"        # Native mobile app


class UserSegment(str, Enum):
    """Coarse willingness-to-pay buckets — never derived from demographics."""
    NEW_VISITOR    = "new_visitor"
    RETURNING      = "returning"
    LOYALTY        = "loyalty"        # Has loyalty programme membership
    HIGH_VALUE     = "high_value"     # LTV > threshold
    PRICE_SENSITIVE = "price_sensitive"
    UNKNOWN        = "unknown"


class ReferralSource(str, Enum):
    DIRECT      = "direct"
    ORGANIC     = "organic"
    PAID_SEARCH = "paid_search"
    SOCIAL      = "social"
    EMAIL       = "email"
    AFFILIATE   = "affiliate"
    UNKNOWN     = "unknown"


# ── Sub-schemas ───────────────────────────────────────────────────────────────

class ProductContext(BaseModel):
    """Embedded product info — denormalised for stream self-containment."""
    product_id: str
    category: str
    price_shown: float = Field(ge=0)
    base_price: float = Field(ge=0)
    inventory_level: int | None = Field(default=None, ge=0)

    @field_validator("price_shown", "base_price")
    @classmethod
    def round_price(cls, v: float) -> float:
        return round(v, 2)


class SearchContext(BaseModel):
    query: str = Field(max_length=500)
    result_count: int = Field(ge=0)
    filters_applied: list[str] = Field(default_factory=list)


class PurchaseContext(BaseModel):
    order_id: str
    items: list[dict[str, Any]]       # [{product_id, qty, unit_price}]
    order_total: float = Field(ge=0)
    payment_method: str | None = None
    coupon_used: bool = False


class GeoContext(BaseModel):
    """
    Coarse geo only — city/region level.
    Never store precise GPS; it has no pricing value and creates GDPR risk.
    """
    country_code: str = Field(max_length=2)
    region: str | None = None
    city: str | None = None
    timezone: str | None = None


# ── Core Event Schema ─────────────────────────────────────────────────────────

class ClickstreamEvent(BaseModel):
    """
    The canonical event payload sent by the frontend SDK.

    Required fields: session_id, event_type, timestamp_ms.
    All other fields are optional but richer signals improve model quality.
    """
    # Identity
    session_id: str = Field(
        min_length=16,
        max_length=128,
        description="Stable within a browser session. Rotates on new visit.",
    )
    user_id: str | None = Field(
        default=None,
        description="Authenticated user ID. Null for anonymous visitors.",
    )
    anonymous_id: str | None = Field(
        default=None,
        description="Persistent cookie-based ID for cross-session stitching.",
    )

    # Event core
    event_type: EventType
    timestamp_ms: int = Field(
        description="Client-side epoch ms. Used to compute client-server skew.",
        gt=0,
    )

    # Page context
    page_url: str | None = Field(default=None, max_length=2048)
    referrer_url: str | None = Field(default=None, max_length=2048)

    # Entity contexts (polymorphic — only relevant fields sent per event type)
    product: ProductContext | None = None
    search: SearchContext | None = None
    purchase: PurchaseContext | None = None

    # Client context
    device_type: DeviceType = DeviceType.UNKNOWN if hasattr(DeviceType, "UNKNOWN") else DeviceType.DESKTOP
    user_segment: UserSegment = UserSegment.UNKNOWN
    referral_source: ReferralSource = ReferralSource.UNKNOWN
    geo: GeoContext | None = None

    # Experiment context — injected by the A/B router middleware
    experiment_id: str | None = None
    variant_id: str | None = None

    # Custom properties — escape hatch for future signals
    properties: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_event_context(self) -> "ClickstreamEvent":
        """
        Cross-field validation: product events need product context,
        purchase events need purchase context, search events need search context.
        """
        product_events = {
            EventType.PRODUCT_VIEW, EventType.CART_ADD, EventType.CART_REMOVE,
            EventType.WISHLIST_ADD, EventType.IMAGE_ZOOM, EventType.REVIEW_READ,
        }
        if self.event_type in product_events and self.product is None:
            raise ValueError(
                f"event_type '{self.event_type}' requires a 'product' context object"
            )
        if self.event_type == EventType.PURCHASE and self.purchase is None:
            raise ValueError("event_type 'purchase' requires a 'purchase' context object")
        if self.event_type == EventType.SEARCH and self.search is None:
            raise ValueError("event_type 'search' requires a 'search' context object")
        return self

    def to_stream_fields(self) -> dict[str, Any]:
        """
        Flatten to Redis Streams compatible dict.
        All values must be strings; nested objects are JSON-serialised.
        """
        return {
            "session_id":      self.session_id,
            "user_id":         self.user_id or "",
            "anonymous_id":    self.anonymous_id or "",
            "event_type":      self.event_type.value,
            "timestamp_ms":    str(self.timestamp_ms),
            "page_url":        self.page_url or "",
            "device_type":     self.device_type.value,
            "user_segment":    self.user_segment.value,
            "referral_source": self.referral_source.value,
            "experiment_id":   self.experiment_id or "",
            "variant_id":      self.variant_id or "",
            # Nested objects serialised as JSON strings
            "product":         self.product.model_dump_json() if self.product else "",
            "search":          self.search.model_dump_json() if self.search else "",
            "purchase":        self.purchase.model_dump_json() if self.purchase else "",
            "geo":             self.geo.model_dump_json() if self.geo else "",
            "properties":      self.model_dump_json(include={"properties"}),
        }


# ── Batch Ingest Schema ───────────────────────────────────────────────────────

class EventBatch(BaseModel):
    """
    Batch endpoint payload — used by mobile SDKs that buffer events.
    Max 100 events per call to prevent abuse.
    """
    events: list[ClickstreamEvent] = Field(min_length=1, max_length=100)

    @field_validator("events")
    @classmethod
    def deduplicate_by_idempotency(
        cls, events: list[ClickstreamEvent]
    ) -> list[ClickstreamEvent]:
        """Drop duplicate (session_id, event_type, timestamp_ms) combos."""
        seen: set[tuple] = set()
        deduped = []
        for e in events:
            key = (e.session_id, e.event_type, e.timestamp_ms)
            if key not in seen:
                seen.add(key)
                deduped.append(e)
        return deduped


# ── Response Schemas ──────────────────────────────────────────────────────────

class EventIngestResponse(BaseModel):
    success: bool
    event_id: str           # Redis stream entry ID
    session_id: str
    features_updated: bool  # Whether feature store was synchronously updated
    latency_ms: float       # Server-side processing time


class BatchIngestResponse(BaseModel):
    success: bool
    accepted: int
    rejected: int
    event_ids: list[str]
    latency_ms: float


class HealthResponse(BaseModel):
    status: str
    redis_connected: bool
    stream_len: int
    p99_latency_ms: float
    meets_sla: bool


# ── DeviceType fix (add UNKNOWN) ──────────────────────────────────────────────
# Patch the enum post-class definition to keep the class body clean
DeviceType._value2member_map_["unknown"] = DeviceType.DESKTOP  # type: ignore[attr-defined]
