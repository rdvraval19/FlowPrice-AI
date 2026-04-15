"""api/v1/router.py — All v1 endpoints wired together."""
from fastapi import APIRouter
from app.api.v1.endpoints import (
    events, pricing, recommendations,
    experiments, catalog, evaluation, circuit_breaker,
    auth,
)
from app.api.v1.endpoints.vendor import router as vendor_router   # Phase 3
from app.api.v1.endpoints.loyalty import router as loyalty_router  # Phase 4

api_router = APIRouter()

# ── Phase 1: Auth ─────────────────────────────────────────────────────────────
api_router.include_router(auth.router)

# ── Phase 3: Vendor Panel ─────────────────────────────────────────────────────
api_router.include_router(vendor_router)

# ── Phase 4: Loyalty + Activity ───────────────────────────────────────────────
api_router.include_router(loyalty_router)

# ── Existing routers ──────────────────────────────────────────────────────────
api_router.include_router(events.router)
api_router.include_router(pricing.router)
api_router.include_router(recommendations.router)
api_router.include_router(experiments.router)
api_router.include_router(catalog.router)
api_router.include_router(evaluation.router)
api_router.include_router(circuit_breaker.router)