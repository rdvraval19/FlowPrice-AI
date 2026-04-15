"""
services/recommendations/engine.py — Hybrid Recommendation Orchestrator.

FIXES (Phase 0):
  • Cold-start trending data now uses ACTUAL product categories from the catalog
    (Electronics, Gaming, Cameras, Cookware, Clothing, Beauty & Health, Sports)
    instead of sneaker-only keys that never matched — this was the primary bug.
  • Session model failure now properly falls through to cold-start instead of
    returning an empty list.
  • Added get_recommendations_for_product() for "similar items" on product pages.
  • Trending index is seeded from FALLBACK_PRODUCTS so recs work even with no
    Redis data (backend just started / no traffic yet).
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.redis_client import feature_store
from app.schemas.recommendation import (
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationSource,
)
from app.services.recommendations.session_model import session_model

logger = logging.getLogger(__name__)

# Blending weights — must sum to 1.0
SESSION_WEIGHT  = 0.55
CF_WEIGHT       = 0.30
CONTEXT_WEIGHT  = 0.15


@dataclass
class ScoredCandidate:
    product_id: str
    score: float
    source: RecommendationSource
    category: str = "unknown"


# ── Main entry point ──────────────────────────────────────────────────────────

async def get_recommendations(req: RecommendationRequest) -> RecommendationResponse:
    """
    Main recommendation entry point.
    Runs all sources concurrently then blends + re-ranks.
    """
    t0 = time.perf_counter()

    session_features  = await feature_store.get_session_features(req.session_id)
    top_categories    = await feature_store.get_top_categories(req.session_id, top_k=3)

    session_event_count = int(session_features.get("session_event_count", 0))
    is_cold_start = session_event_count < 3 or not req.user_id

    # Run sources concurrently
    session_task = asyncio.create_task(
        _get_session_candidates(req.session_items, req.top_k * 2)
    )
    context_task = asyncio.create_task(
        _get_contextual_candidates(
            top_categories, req.device_type, req.referral_source, req.top_k * 2
        )
    )

    session_candidates, context_candidates = await asyncio.gather(
        session_task, context_task, return_exceptions=True
    )

    if isinstance(session_candidates, Exception):
        logger.warning("Session model error (using cold-start): %s", session_candidates)
        session_candidates = []
    if isinstance(context_candidates, Exception):
        logger.warning("Context model error: %s", context_candidates)
        context_candidates = []

    # FIX: if session gave nothing AND we're not in cold_start mode, force cold_start
    if not session_candidates:
        is_cold_start = True

    blended = _blend_candidates(
        session_candidates=session_candidates,
        context_candidates=context_candidates,
        is_cold_start=is_cold_start,
    )

    diverse = _diversify(blended, top_k=req.top_k)

    # FIX: if still empty after all that, return global trending as last resort
    if not diverse:
        diverse = [
            ScoredCandidate(
                product_id=pid,
                score=score,
                source=RecommendationSource.TRENDING,
                category="various",
            )
            for pid, score in _get_trending_global(req.top_k)
        ]

    items = [
        RecommendationItem(
            product_id=c.product_id,
            score=round(c.score, 4),
            source=c.source,
            rank=i + 1,
        )
        for i, c in enumerate(diverse)
    ]

    elapsed     = round((time.perf_counter() - t0) * 1000, 2)
    source_used = _determine_primary_source(diverse)

    logger.info(
        "Recommendations: session=%s items=%d source=%s cold_start=%s [%.2f ms]",
        req.session_id, len(items), source_used.value, is_cold_start, elapsed,
    )

    return RecommendationResponse(
        session_id=req.session_id,
        items=items,
        source=source_used,
        is_cold_start=is_cold_start,
        computed_in_ms=elapsed,
    )


async def get_recommendations_for_product(
    product_id: str,
    category: str,
    top_k: int = 6,
) -> list[RecommendationItem]:
    """
    'Similar items' recommendations for a product detail page.
    Returns products from the same category + global trending as padding.
    """
    same_cat = _get_trending_for_category(category, n=top_k)
    # Exclude the product itself
    filtered = [(pid, s) for pid, s in same_cat if pid != product_id]

    # Pad with global trending if not enough
    if len(filtered) < top_k:
        seen = {p for p, _ in filtered} | {product_id}
        for pid, score in _get_trending_global(top_k):
            if pid not in seen:
                filtered.append((pid, score * 0.85))
            if len(filtered) >= top_k:
                break

    return [
        RecommendationItem(
            product_id=pid,
            score=round(score, 4),
            source=RecommendationSource.TRENDING,
            rank=i + 1,
        )
        for i, (pid, score) in enumerate(filtered[:top_k])
    ]


# ── Source: Session-Based (GRU4Rec) ──────────────────────────────────────────

async def _get_session_candidates(
    session_items: list[str], top_k: int
) -> list[ScoredCandidate]:
    """Run GRU4Rec inference. Returns empty list on any failure."""
    if len(session_items) < 2:
        return []

    try:
        loop = asyncio.get_event_loop()
        predictions = await loop.run_in_executor(
            None, session_model.predict, session_items, top_k
        )
        if not predictions:
            return []
        return [
            ScoredCandidate(
                product_id=pid,
                score=score,
                source=RecommendationSource.SESSION_BASED,
            )
            for pid, score in predictions
        ]
    except Exception as exc:
        logger.warning("GRU4Rec inference failed: %s", exc)
        return []


# ── Source: Contextual / Cold-Start ──────────────────────────────────────────

async def _get_contextual_candidates(
    top_categories: list[tuple[str, float]],
    device_type: str,
    referral_source: str,
    top_k: int,
) -> list[ScoredCandidate]:
    candidates: list[ScoredCandidate] = []

    # Trending in user's top affinity categories
    for category, affinity_score in top_categories[:3]:
        trending = _get_trending_for_category(category, n=max(top_k // 3, 2))
        for pid, base_score in trending:
            score = base_score * (0.5 + 0.5 * min(affinity_score / 10.0, 1.0))
            candidates.append(ScoredCandidate(
                product_id=pid,
                score=score,
                source=RecommendationSource.COLD_START,
                category=category,
            ))

    # Pad with global trending
    if len(candidates) < top_k:
        seen_ids = {c.product_id for c in candidates}
        for pid, score in _get_trending_global(top_k):
            if pid not in seen_ids:
                candidates.append(ScoredCandidate(
                    product_id=pid,
                    score=score * 0.7,
                    source=RecommendationSource.TRENDING,
                ))
            if len(candidates) >= top_k:
                break

    return candidates[:top_k]


# ── Blending ──────────────────────────────────────────────────────────────────

def _blend_candidates(
    session_candidates: list[ScoredCandidate],
    context_candidates: list[ScoredCandidate],
    is_cold_start: bool,
) -> list[ScoredCandidate]:
    k_rrf = 60

    if is_cold_start:
        w_session, w_context = 0.0, 1.0
    else:
        w_session = SESSION_WEIGHT / (SESSION_WEIGHT + CONTEXT_WEIGHT)
        w_context = CONTEXT_WEIGHT / (SESSION_WEIGHT + CONTEXT_WEIGHT)

    rrf_scores: dict[str, float] = {}
    source_map: dict[str, RecommendationSource] = {}
    category_map: dict[str, str] = {}

    def add_rrf(candidates: list[ScoredCandidate], weight: float) -> None:
        for rank, c in enumerate(
            sorted(candidates, key=lambda x: x.score, reverse=True)
        ):
            rrf_scores[c.product_id] = (
                rrf_scores.get(c.product_id, 0.0) + weight / (k_rrf + rank + 1)
            )
            if c.product_id not in source_map:
                source_map[c.product_id]   = c.source
                category_map[c.product_id] = c.category

    add_rrf(session_candidates, w_session)
    add_rrf(context_candidates, w_context)

    return [
        ScoredCandidate(
            product_id=pid,
            score=score,
            source=source_map.get(pid, RecommendationSource.TRENDING),
            category=category_map.get(pid, "unknown"),
        )
        for pid, score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    ]


def _diversify(candidates: list[ScoredCandidate], top_k: int) -> list[ScoredCandidate]:
    selected: list[ScoredCandidate] = []
    category_counts: dict[str, int] = {}
    MAX_PER_CATEGORY = 2

    for candidate in candidates:
        cat = candidate.category
        if category_counts.get(cat, 0) >= MAX_PER_CATEGORY:
            continue
        selected.append(candidate)
        category_counts[cat] = category_counts.get(cat, 0) + 1
        if len(selected) >= top_k:
            break

    if len(selected) < top_k:
        seen = {c.product_id for c in selected}
        for c in candidates:
            if c.product_id not in seen:
                selected.append(c)
            if len(selected) >= top_k:
                break

    return selected[:top_k]


def _determine_primary_source(
    candidates: list[ScoredCandidate],
) -> RecommendationSource:
    if not candidates:
        return RecommendationSource.TRENDING
    source_counts: dict[str, int] = {}
    for c in candidates:
        source_counts[c.source] = source_counts.get(c.source, 0) + 1
    return max(source_counts, key=source_counts.get)


# ── FIX: Trending data using ACTUAL product catalog categories ────────────────
#
# Previously this used sneaker-only keys ("sneakers", "running", "boots")
# which NEVER matched the real categories ("Electronics", "Gaming", etc.)
# causing the recommendation engine to always return empty or wrong results.
#
# Now keyed by the actual catalog categories used in catalog.ts / organizer data.

_CATEGORY_TRENDING: dict[str, list[tuple[str, float]]] = {
    "Electronics": [
        ("SKU001000", 0.95),   # ProSound Wireless Headphones
        ("SKU006000", 0.88),
        ("SKU006001", 0.82),
    ],
    "Gaming": [
        ("SKU003200", 0.95),   # Pro Gaming Headset RGB
        ("SKU007000", 0.87),
        ("SKU007001", 0.80),
    ],
    "Cameras": [
        ("SKU004100", 0.93),   # Mirrorless Camera Kit 24MP
        ("SKU008000", 0.85),
        ("SKU008001", 0.78),
    ],
    "Cookware": [
        ("SKU002100", 0.91),   # Smart Chef Cookware Set
        ("SKU009000", 0.83),
    ],
    "Clothing": [
        ("SKU001500", 0.89),   # Urban Fit Running Jacket
        ("SKU010000", 0.82),
        ("SKU010001", 0.75),
    ],
    "Beauty & Health": [
        ("SKU005500", 0.87),   # Vitamin C Serum
        ("SKU011000", 0.80),
        ("SKU011001", 0.73),
    ],
    "Sports": [
        ("SKU012000", 0.86),
        ("SKU012001", 0.79),
        ("SKU012002", 0.72),
    ],
    "Home & Kitchen": [
        ("SKU013000", 0.84),
        ("SKU013001", 0.77),
    ],
    "Books & Media": [
        ("SKU014000", 0.80),
        ("SKU014001", 0.73),
    ],
    "Accessories": [
        ("SKU015000", 0.82),
        ("SKU015001", 0.75),
    ],
    "Footwear": [
        ("SKU016000", 0.88),
        ("SKU016001", 0.81),
        ("SKU016002", 0.74),
    ],
}

# Global trending — mix of all categories, ordered by demand
_GLOBAL_TRENDING: list[tuple[str, float]] = [
    ("SKU001000", 0.95),  # Electronics
    ("SKU003200", 0.93),  # Gaming
    ("SKU004100", 0.91),  # Cameras
    ("SKU002100", 0.89),  # Cookware
    ("SKU001500", 0.87),  # Clothing
    ("SKU005500", 0.85),  # Beauty & Health
    ("SKU006000", 0.83),
    ("SKU007000", 0.81),
    ("SKU008000", 0.79),
    ("SKU009000", 0.77),
]


def _get_trending_for_category(category: str, n: int) -> list[tuple[str, float]]:
    """FIX: Now matches actual catalog categories."""
    items = _CATEGORY_TRENDING.get(category)
    if not items:
        # Fuzzy fallback: try case-insensitive match
        lower = category.lower()
        for key, val in _CATEGORY_TRENDING.items():
            if key.lower() == lower or lower in key.lower():
                items = val
                break
    return (items or _GLOBAL_TRENDING[:3])[:n]


def _get_trending_global(n: int) -> list[tuple[str, float]]:
    return _GLOBAL_TRENDING[:n]