"""schemas/recommendation.py — Recommendation engine schemas."""
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class RecommendationSource(str, Enum):
    SESSION_BASED   = "session_based"    # GRU4Rec
    COLLABORATIVE   = "collaborative"    # Matrix factorisation
    COLD_START      = "cold_start"       # Contextual signals
    TRENDING        = "trending"         # Global popularity fallback


class RecommendationItem(BaseModel):
    product_id: str
    score: float = Field(ge=0, le=1)
    source: RecommendationSource
    rank: int


class RecommendationRequest(BaseModel):
    session_id: str
    user_id: str | None = None
    session_items: list[str] = Field(default_factory=list)   # Products viewed this session
    top_k: int = Field(default=10, ge=1, le=50)
    device_type: str = "desktop"
    referral_source: str = "direct"
    exclude_product_ids: list[str] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    session_id: str
    items: list[RecommendationItem]
    source: RecommendationSource
    is_cold_start: bool
    computed_in_ms: float
