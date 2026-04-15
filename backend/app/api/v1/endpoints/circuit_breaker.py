"""api/v1/endpoints/circuit_breaker.py — Circuit breaker admin API."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from app.services.pricing.circuit_breaker import circuit_breaker, CircuitState

router = APIRouter(prefix="/circuit-breaker", tags=["Circuit Breaker"])


@router.get("/status", summary="Circuit breaker health + recent trip log")
async def get_status() -> dict:
    return await circuit_breaker.get_status()


@router.post("/reset", summary="Emergency reset (OPEN → CLOSED)")
async def manual_reset() -> dict:
    await circuit_breaker.manual_reset()
    return {"status": "CLOSED", "message": "Circuit breaker manually reset"}


@router.post("/trip", summary="Force-open (for testing)")
async def manual_trip() -> dict:
    await circuit_breaker.manual_trip()
    return {"status": "OPEN", "message": "Circuit breaker manually opened"}


@router.post("/test", summary="Test the circuit breaker with a bad price")
async def test_circuit_breaker(
    product_id: str = "TEST001",
    proposed_price: float = 0.01,   # Should trip the floor rule
    base_price: float = 100.0,
    cost_price: float = 40.0,
) -> dict:
    """Demonstrates the circuit breaker in action with a catastrophic price."""
    final, clamped, trip = await circuit_breaker.check_and_clamp(
        proposed_price=proposed_price,
        product_id=product_id,
        base_price=base_price,
        cost_price=cost_price,
        context="test",
    )
    return {
        "proposed_price":  proposed_price,
        "final_price":     final,
        "was_clamped":     clamped,
        "trip_details":    trip.to_dict() if trip else None,
        "verdict": "🔴 CLAMPED — circuit breaker fired" if clamped else "✅ SAFE — price passed",
    }
