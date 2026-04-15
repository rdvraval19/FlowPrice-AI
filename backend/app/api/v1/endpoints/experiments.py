"""api/v1/endpoints/experiments.py — A/B Experiments API"""
from __future__ import annotations
import time
from fastapi import APIRouter, HTTPException, status
from app.services.experiments.framework import (
    EXPERIMENT_REGISTRY, experiment_metrics, get_session_experiments, assign_variant
)

router = APIRouter(prefix="/experiments", tags=["Experiments"])


@router.get("/", summary="List all experiments")
async def list_experiments() -> dict:
    return {
        "experiments": [
            {
                "id": exp.id,
                "name": exp.name,
                "status": exp.status.value,
                "variants": [{"id": v.id, "name": v.name, "traffic_pct": v.traffic_pct}
                             for v in exp.variants],
                "started_at": exp.started_at,
            }
            for exp in EXPERIMENT_REGISTRY.values()
        ],
        "total": len(EXPERIMENT_REGISTRY),
    }


@router.get("/{experiment_id}/results", summary="Get live experiment results")
async def get_experiment_results(experiment_id: str) -> dict:
    if experiment_id not in EXPERIMENT_REGISTRY:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return await experiment_metrics.get_experiment_results(experiment_id)


@router.get("/session/{session_id}/assignments", summary="Get variant assignments for a session")
async def get_session_assignments(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "assignments": get_session_experiments(session_id),
        "resolved_at_ms": int(time.time() * 1000),
    }


@router.post("/{experiment_id}/record/impression", summary="Record an impression")
async def record_impression(experiment_id: str, variant_id: str) -> dict:
    await experiment_metrics.record_impression(experiment_id, variant_id)
    return {"recorded": True}


@router.post("/{experiment_id}/record/conversion", summary="Record a conversion")
async def record_conversion(experiment_id: str, variant_id: str, order_total: float) -> dict:
    await experiment_metrics.record_conversion(experiment_id, variant_id, order_total)
    return {"recorded": True}


@router.get("/dashboard/summary", summary="All experiments summary for dashboard")
async def get_dashboard_summary() -> dict:
    """Aggregated view for the Judge's Dashboard."""
    summaries = []
    for exp_id in EXPERIMENT_REGISTRY:
        result = await experiment_metrics.get_experiment_results(exp_id)
        summaries.append(result)
    return {"experiments": summaries, "fetched_at_ms": int(time.time() * 1000)}
