"""
services/pricing/demand_model.py — Real-time demand scoring.

Computes a continuous demand_score ∈ [0, 1] that feeds the pricing engine.

Pipeline:
  1. demand_velocity   → normalise against category baseline
  2. inventory_level   → scarcity multiplier
  3. competitor_price  → price gap signal
  4. time_of_day       → demand seasonality pattern
  5. Weighted combination → demand_score

In production the weights are learned via gradient boosting on historical
(demand_velocity, price, conversion) tuples. Here we use calibrated
heuristics that replicate the expected model behaviour.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
from sklearn.preprocessing import MinMaxScaler

from app.core.config import settings


# ── Calibration Constants ────────────────────────────────────────────────────
# Category-level baseline velocities (views per 5-min window).
# Used to normalise raw velocity into a meaningful signal.
CATEGORY_VELOCITY_BASELINES: dict[str, float] = {
    "sneakers":     35.0,
    "running":      28.0,
    "basketball":   20.0,
    "casual":       22.0,
    "boots":        18.0,
    "sandals":      15.0,
    "default":      25.0,
}

# Elasticity multipliers by category.
# Higher = price is more sensitive to demand changes in this category.
CATEGORY_ELASTICITY: dict[str, float] = {
    "sneakers":     1.2,
    "running":      1.0,
    "basketball":   0.9,
    "casual":       0.8,
    "boots":        0.7,
    "sandals":      0.6,
    "default":      1.0,
}

# Inventory scarcity breakpoints → multiplier on demand signal
SCARCITY_BANDS: list[tuple[int, float]] = [
    (0,    0.0),   # OOS — no pricing needed
    (5,    1.4),   # Critical: < 5 units
    (15,   1.25),  # Low: < 15 units
    (30,   1.10),  # Moderate: < 30 units
    (100,  1.0),   # Normal
    (999,  0.95),  # Overstock — slight discount nudge
]

# Hour-of-day demand multipliers (UTC).
# Peak = 18:00-22:00 (evening shopping), trough = 02:00-06:00.
HOURLY_DEMAND_PATTERN: list[float] = [
    0.60, 0.50, 0.45, 0.42, 0.45, 0.55,  # 00-05
    0.70, 0.80, 0.85, 0.88, 0.90, 0.92,  # 06-11
    0.95, 0.92, 0.90, 0.93, 0.96, 1.00,  # 12-17
    1.05, 1.08, 1.10, 1.05, 0.95, 0.75,  # 18-23
]


@dataclass
class DemandSignals:
    """Intermediate scoring breakdown — returned for explainability."""
    raw_velocity: int
    normalised_velocity: float      # [0, 1]
    scarcity_multiplier: float
    competitor_gap_signal: float    # [0, 1] — 0=cheaper, 1=we're much cheaper
    time_multiplier: float
    demand_score: float             # Final composite [0, 1]
    elasticity: float
    category: str


def compute_demand_score(
    velocity: int,
    inventory: int,
    base_price: float,
    competitor_price: float | None,
    category: str = "default",
    hour_utc: int | None = None,
) -> DemandSignals:
    """
    Compute a composite demand score from real-time signals.

    All inputs are normalised to [0, 1] before combining so that
    no single signal can dominate due to scale differences.
    """
    if hour_utc is None:
        hour_utc = datetime.now(timezone.utc).hour

    baseline = CATEGORY_VELOCITY_BASELINES.get(category, CATEGORY_VELOCITY_BASELINES["default"])
    elasticity = CATEGORY_ELASTICITY.get(category, CATEGORY_ELASTICITY["default"])

    # ── Signal 1: Demand Velocity ─────────────────────────────────────────────
    # Sigmoid normalisation — smooth handling of extreme velocity spikes
    velocity_ratio = velocity / max(baseline, 1.0)
    normalised_velocity = _sigmoid_norm(velocity_ratio, centre=1.0, steepness=2.0)

    # ── Signal 2: Inventory Scarcity ──────────────────────────────────────────
    scarcity_mult = _get_scarcity_multiplier(inventory)

    # ── Signal 3: Competitor Price Gap ────────────────────────────────────────
    if competitor_price and competitor_price > 0:
        # Positive gap = we are cheaper (discount opportunity)
        # Negative gap = competitor is cheaper (pressure to reduce)
        gap_pct = (competitor_price - base_price) / max(competitor_price, 0.01)
        competitor_signal = max(0.0, min(1.0, 0.5 + gap_pct))
    else:
        competitor_signal = 0.5   # Neutral when no competitor data

    # ── Signal 4: Time-of-Day Multiplier ─────────────────────────────────────
    time_mult = HOURLY_DEMAND_PATTERN[hour_utc % 24]

    # ── Weighted Composite Score ──────────────────────────────────────────────
    demand_score = (
        settings.DEMAND_WEIGHT    * normalised_velocity +
        settings.INVENTORY_WEIGHT * (scarcity_mult - 1.0) / 0.4 +   # Normalise [1,1.4] → [0,1]
        settings.COMPETITOR_WEIGHT * competitor_signal +
        (1 - settings.DEMAND_WEIGHT - settings.INVENTORY_WEIGHT - settings.COMPETITOR_WEIGHT)
        * time_mult
    )

    # Apply category elasticity stretch
    demand_score = min(1.0, max(0.0, demand_score * elasticity))

    return DemandSignals(
        raw_velocity=velocity,
        normalised_velocity=round(normalised_velocity, 4),
        scarcity_multiplier=scarcity_mult,
        competitor_gap_signal=round(competitor_signal, 4),
        time_multiplier=time_mult,
        demand_score=round(demand_score, 4),
        elasticity=elasticity,
        category=category,
    )


def velocity_to_adjustment_pct(demand_score: float, max_surge: float, max_discount: float) -> float:
    """
    Map demand_score [0, 1] to a price adjustment percentage.

    Score mapping (symmetric around 0.5 neutral point):
      0.0  → -max_discount  (floor: maximum discount)
      0.5  →  0.0           (neutral: base price)
      1.0  → +max_surge     (ceiling: maximum surge)

    Uses a cubic curve for smooth, human-friendly price transitions
    rather than a harsh linear mapping.
    """
    # Centre around 0: [-0.5, 0.5]
    centred = demand_score - 0.5

    # Cubic easing: small changes near centre, sharper at extremes
    # f(x) = 4x³ maps [-0.5,0.5] → [-0.5,0.5] with cubic easing
    eased = 4 * (centred ** 3)

    # Scale to adjustment range
    if eased >= 0:
        adjustment_pct = eased * 2 * max_surge      # [0, max_surge]
    else:
        adjustment_pct = eased * 2 * max_discount   # [-max_discount, 0]

    return round(adjustment_pct, 4)


def _sigmoid_norm(x: float, centre: float = 1.0, steepness: float = 2.0) -> float:
    """Smooth sigmoid normalisation for velocity ratios."""
    return 1.0 / (1.0 + math.exp(-steepness * (x - centre)))


def _get_scarcity_multiplier(inventory: int) -> float:
    """Step-function scarcity multiplier from inventory bands."""
    for threshold, multiplier in SCARCITY_BANDS:
        if inventory <= threshold:
            return multiplier
    return SCARCITY_BANDS[-1][1]
