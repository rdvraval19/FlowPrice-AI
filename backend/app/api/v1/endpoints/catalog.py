"""
api/v1/endpoints/catalog.py — Dynamic product catalog served from Redis.

After running seed_from_organizer_data.py, this endpoint serves the
organizer's 5,000+ SKU catalog instead of the hardcoded 6 products.

Endpoints:
  GET /api/v1/catalog/              — Paginated catalog (for storefront)
  GET /api/v1/catalog/{sku_id}      — Single product
  GET /api/v1/catalog/categories    — Available categories
  GET /api/v1/catalog/competitor/{sku_id} — Competitor price for a SKU
"""
from __future__ import annotations
import logging
import time
from fastapi import APIRouter, Query
from app.core.redis_client import get_redis
from app.services.vendor.sponsor_service import sponsor_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/catalog", tags=["Catalog"])


@router.get("/", summary="Paginated product catalog from organizer dataset")
async def get_catalog(
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=24, ge=1, le=100),
) -> dict:
    """Returns products from Redis (seeded from product_catalog.parquet)."""
    r = get_redis()

    # Scan for all catalog keys
    keys = []
    async for key in r.scan_iter("catalog:SKU*", count=200):
        keys.append(key)

    if not keys:
        return {"products": [], "total": 0, "message": "Run seed_from_organizer_data.py first"}

    # Fetch all products
    products = []
    for key in keys:
        data = await r.hgetall(key)
        if data:
            prod = {k: _coerce(v) for k, v in data.items()}

            # 🟢 ADD THIS BLOCK (CRITICAL FIX)
            is_sponsored, badge = await sponsor_service.is_sponsored(prod["id"])
            prod["is_sponsored"] = is_sponsored
            prod["sponsor_badge"] = badge

            if category and prod.get("category") != category:
                continue

            products.append(prod)

    # Sort by trending first, then by rating
    products.sort(
    key=lambda p: (
        -(1 if p.get("is_sponsored") is True else 0),  # ← FIXED: already coerced by _coerce()
        -(1 if p.get("trending") is True else 0),
        -float(p.get("avg_rating", 0)),
    ))
    # Paginate
    total = len(products)
    start = (page - 1) * per_page
    page_products = products[start:start + per_page]

    return {
        "products": page_products,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.get("/categories", summary="All available product categories")
async def get_categories() -> dict:
    r = get_redis()
    categories: set[str] = set()
    async for key in r.scan_iter("catalog:SKU*", count=500):
        cat = await r.hget(key, "category")
        if cat:
            categories.add(cat)
    return {"categories": sorted(categories), "total": len(categories)}


@router.get("/competitor/{sku_id}", summary="Competitor price for a SKU")
async def get_competitor_price(sku_id: str) -> dict:
    r = get_redis()
    data = await r.hgetall(f"competitor:price:{sku_id}")
    if not data:
        return {"sku_id": sku_id, "competitor_price": None, "available": False}
    return {
        "sku_id":           sku_id,
        "competitor_price": float(data.get("price", 0)),
        "delta_pct":        float(data.get("delta_pct", 0)),
        "competitor":       data.get("competitor", ""),
        "updated_at":       int(data.get("updated_at", 0)),
        "available":        True,
    }


@router.get("/{sku_id}", summary="Single product by SKU")
async def get_product(sku_id: str) -> dict:
    r = get_redis()
    data = await r.hgetall(f"catalog:{sku_id}")
    if not data:
        return {"error": f"Product {sku_id} not found", "seeded": False}
    return {k: _coerce(v) for k, v in data.items()}


def _coerce(v: str):
    try: return int(v)
    except: pass
    try: return float(v)
    except: pass
    if v.lower() == "true":  return True
    if v.lower() == "false": return False
    return v
