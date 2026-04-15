"""
services/experiments/framework.py — A/B Testing Framework.

Design:
  • Deterministic assignment — same session always gets the same variant
  • Namespace isolation — experiments don't interfere with each other
  • Mutual exclusivity — a session is in at most one pricing experiment
  • Metric tracking — conversion, AOV, RPS recorded per variant in Redis

Assignment algorithm:
  hash(salt + experiment_id + session_id) % 100 → bucket [0-99]
  Traffic allocation maps buckets to variants:
    control:   [0, 49]
    treatment: [50, 99]  (for 50/50 split)

This is deterministic without any database lookup — critical for < 1ms
assignment within the p99 SLA.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.config import settings
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)


class ExperimentStatus(str, Enum):
    DRAFT    = "draft"
    RUNNING  = "running"
    PAUSED   = "paused"
    COMPLETE = "complete"


@dataclass
class Variant:
    id: str
    name: str
    traffic_pct: float          # [0, 1] fraction of traffic
    config: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass
class Experiment:
    id: str
    name: str
    description: str
    variants: list[Variant]
    status: ExperimentStatus = ExperimentStatus.DRAFT
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    ended_at: float | None = None

    def __post_init__(self):
        total = sum(v.traffic_pct for v in self.variants)
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Variant traffic_pct must sum to 1.0, got {total:.3f}")

    @property
    def is_active(self) -> bool:
        return self.status == ExperimentStatus.RUNNING


# ── Predefined Experiments ────────────────────────────────────────────────────
# In production these come from a database. Hardcoded here for hackathon demo.

EXPERIMENT_REGISTRY: dict[str, Experiment] = {
    "pricing_strategy_v1": Experiment(
        id="pricing_strategy_v1",
        name="Demand-Responsive vs Flat Pricing",
        description=(
            "Tests whether dynamic demand-responsive pricing "
            "increases revenue vs a flat base-price strategy."
        ),
        variants=[
            Variant(
                id="control",
                name="Flat Pricing",
                traffic_pct=0.50,
                config={"pricing_mode": "flat"},
                description="No dynamic adjustment — show base price only",
            ),
            Variant(
                id="treatment",
                name="Dynamic Pricing",
                traffic_pct=0.50,
                config={"pricing_mode": "dynamic"},
                description="Full demand-responsive pricing engine",
            ),
        ],
        status=ExperimentStatus.RUNNING,
        started_at=time.time() - 86400,   # Started 1 day ago
    ),

    "rec_model_v1": Experiment(
        id="rec_model_v1",
        name="GRU4Rec vs Trending Baseline",
        description=(
            "Tests whether session-based GRU4Rec recommendations "
            "improve CTR and conversion vs global trending fallback."
        ),
        variants=[
            Variant(
                id="control",
                name="Trending Baseline",
                traffic_pct=0.50,
                config={"rec_model": "trending"},
                description="Global popularity-based recommendations",
            ),
            Variant(
                id="treatment",
                name="GRU4Rec Session Model",
                traffic_pct=0.50,
                config={"rec_model": "gru4rec"},
                description="Session-aware GRU4Rec recommendations",
            ),
        ],
        status=ExperimentStatus.RUNNING,
        started_at=time.time() - 43200,   # Started 12 hours ago
    ),
}


# ── Assignment Engine ─────────────────────────────────────────────────────────

def assign_variant(experiment_id: str, session_id: str) -> Variant | None:
    """
    Deterministically assign a session to an experiment variant.

    Algorithm:
      1. Compute SHA-256(salt + experiment_id + session_id)
      2. Take the last 4 bytes as a uint32
      3. bucket = uint32 % 100  → [0, 99]
      4. Walk variants in order, assign when cumulative_pct > bucket/100

    This is O(1), stateless, and consistent across restarts.
    """
    experiment = EXPERIMENT_REGISTRY.get(experiment_id)
    if not experiment or not experiment.is_active:
        return None

    # Deterministic hash
    hash_input = f"{settings.AB_SALT}:{experiment_id}:{session_id}"
    digest = hashlib.sha256(hash_input.encode()).digest()
    bucket = int.from_bytes(digest[-4:], "big") % 100

    # Assign to variant by cumulative traffic allocation
    cumulative = 0.0
    for variant in experiment.variants:
        cumulative += variant.traffic_pct * 100
        if bucket < cumulative:
            return variant

    # Fallback to last variant (rounding safety)
    return experiment.variants[-1]


def get_session_experiments(session_id: str) -> dict[str, str]:
    """
    Return all active experiment assignments for a session.
    Called by the AB router middleware to inject variant context into requests.
    Returns {experiment_id: variant_id}
    """
    assignments = {}
    for exp_id, experiment in EXPERIMENT_REGISTRY.items():
        if experiment.is_active:
            variant = assign_variant(exp_id, session_id)
            if variant:
                assignments[exp_id] = variant.id
    return assignments


# ── Metric Recording ──────────────────────────────────────────────────────────

class ExperimentMetrics:
    """
    Redis-backed metric collection for A/B experiments.

    Keys:
      exp:metrics:{experiment_id}:{variant_id}:impressions  → integer
      exp:metrics:{experiment_id}:{variant_id}:conversions  → integer
      exp:metrics:{experiment_id}:{variant_id}:revenue      → float (stored as string)
      exp:metrics:{experiment_id}:{variant_id}:aov_samples  → list of order totals
    """

    async def record_impression(self, experiment_id: str, variant_id: str) -> None:
        r = get_redis()
        key = f"exp:metrics:{experiment_id}:{variant_id}:impressions"
        await r.incr(key)
        await r.expire(key, 86400 * 30)   # 30 days

    async def record_conversion(
        self,
        experiment_id: str,
        variant_id: str,
        order_total: float,
    ) -> None:
        r = get_redis()
        prefix = f"exp:metrics:{experiment_id}:{variant_id}"
        async with (await r.pipeline(transaction=False)) as pipe:
            pipe.incr(f"{prefix}:conversions")
            pipe.incrbyfloat(f"{prefix}:revenue", order_total)
            pipe.lpush(f"{prefix}:aov_samples", str(order_total))
            pipe.ltrim(f"{prefix}:aov_samples", 0, 999)
            pipe.expire(f"{prefix}:conversions", 86400 * 30)
            pipe.expire(f"{prefix}:revenue", 86400 * 30)
            pipe.expire(f"{prefix}:aov_samples", 86400 * 30)
            await pipe.execute()

    async def get_variant_metrics(
        self, experiment_id: str, variant_id: str
    ) -> dict[str, Any]:
        r = get_redis()
        prefix = f"exp:metrics:{experiment_id}:{variant_id}"

        impressions = int(await r.get(f"{prefix}:impressions") or 0)
        conversions = int(await r.get(f"{prefix}:conversions") or 0)
        revenue = float(await r.get(f"{prefix}:revenue") or 0.0)
        aov_samples = await r.lrange(f"{prefix}:aov_samples", 0, -1)

        conversion_rate = conversions / max(impressions, 1)
        aov = (
            sum(float(x) for x in aov_samples) / len(aov_samples)
            if aov_samples else 0.0
        )
        rps = revenue / max(impressions, 1)   # Revenue per session

        return {
            "variant_id": variant_id,
            "impressions": impressions,
            "conversions": conversions,
            "conversion_rate": round(conversion_rate, 4),
            "revenue": round(revenue, 2),
            "aov": round(aov, 2),
            "rps": round(rps, 4),
        }

    async def get_experiment_results(self, experiment_id: str) -> dict[str, Any]:
        experiment = EXPERIMENT_REGISTRY.get(experiment_id)
        if not experiment:
            return {}

        variant_metrics = {}
        for variant in experiment.variants:
            metrics = await self.get_variant_metrics(experiment_id, variant.id)
            variant_metrics[variant.id] = metrics

        # Compute statistical significance (chi-squared for conversion rate)
        significance = _compute_significance(variant_metrics, experiment.variants)

        return {
            "experiment_id": experiment_id,
            "name": experiment.name,
            "status": experiment.status.value,
            "started_at": experiment.started_at,
            "variants": variant_metrics,
            "statistical_significance": significance,
            "winner": _determine_winner(variant_metrics, significance),
        }


def _compute_significance(
    metrics: dict[str, dict],
    variants: list[Variant],
) -> dict[str, Any]:
    """
    Chi-squared test for conversion rate significance.
    Returns p-value and whether result is significant at 95% confidence.
    """
    if len(variants) != 2:
        return {"p_value": None, "is_significant": False, "confidence": 0.0}

    v_ids = [v.id for v in variants]
    m0, m1 = metrics.get(v_ids[0], {}), metrics.get(v_ids[1], {})

    n0, c0 = m0.get("impressions", 0), m0.get("conversions", 0)
    n1, c1 = m1.get("impressions", 0), m1.get("conversions", 0)

    if n0 < 100 or n1 < 100:
        return {"p_value": None, "is_significant": False, "confidence": 0.0,
                "note": "Insufficient sample size (< 100 impressions per variant)"}

    # Two-proportion z-test
    import math
    p0, p1 = c0 / n0, c1 / n1
    p_pool = (c0 + c1) / (n0 + n1)

    if p_pool in (0.0, 1.0):
        return {"p_value": 1.0, "is_significant": False, "confidence": 0.0}

    se = math.sqrt(p_pool * (1 - p_pool) * (1/n0 + 1/n1))
    if se == 0:
        return {"p_value": 1.0, "is_significant": False, "confidence": 0.0}

    z = abs(p1 - p0) / se
    # Approximate p-value from z-score
    p_value = 2 * (1 - _norm_cdf(z))
    confidence = round((1 - p_value) * 100, 1)

    return {
        "p_value": round(p_value, 4),
        "is_significant": p_value < 0.05,
        "confidence": confidence,
        "z_score": round(z, 3),
    }


def _determine_winner(
    metrics: dict[str, dict], significance: dict
) -> str | None:
    if not significance.get("is_significant"):
        return None
    best = max(metrics.items(), key=lambda x: x[1].get("rps", 0))
    return best[0]


def _norm_cdf(x: float) -> float:
    """Approximation of the normal CDF using the error function."""
    import math
    return (1.0 + math.erf(x / math.sqrt(2))) / 2.0


# Module-level singletons
experiment_metrics = ExperimentMetrics()
