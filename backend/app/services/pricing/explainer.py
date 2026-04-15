"""
services/pricing/explainer.py — Price change explainability.

Generates the PriceExplanation payload that powers the UI transparency badge.
Every price served to a user is accompanied by an explanation — no black boxes.

Design goals:
  • Primary reason captures the DOMINANT signal (not every signal)
  • User copy is honest, simple, and non-discriminatory
  • Secondary reasons give auditors the full picture
  • Confidence score reflects how many signals agreed
"""
from __future__ import annotations

from app.schemas.pricing import PriceAdjustmentReason, PriceExplanation, REASON_COPY
from app.services.pricing.business_rules import RuleCheckResult
from app.services.pricing.demand_model import DemandSignals
from app.core.config import settings


def generate_explanation(
    demand: DemandSignals,
    rules: RuleCheckResult,
    final_price: float,
    base_price: float,
    user_segment: str,
    inventory: int,
) -> PriceExplanation:
    """
    Derive the primary reason and user-facing copy from the pricing signals.

    Priority order for primary reason (first match wins):
      1. Business rule override (margin floor, discount/surge cap)
      2. Flash sale (synthetic — injected by campaign system)
      3. Loyalty/new-visitor personalisation
      4. High demand surge
      5. Low demand discount
      6. Limited stock
      7. Competitor match
      8. Base price (no adjustment)
    """
    discount_pct = round((base_price - final_price) / base_price * 100, 1)
    secondary: list[PriceAdjustmentReason] = []
    is_personalized = False

    # ── Rule Override (highest priority — user deserves to know) ──────────────
    if rules.surge_cap_applied:
        primary = PriceAdjustmentReason.CAP_HIT
        secondary.append(PriceAdjustmentReason.HIGH_DEMAND)
    elif rules.discount_cap_applied:
        primary = PriceAdjustmentReason.CAP_HIT
        secondary.append(PriceAdjustmentReason.LOW_DEMAND)
    elif rules.margin_floor_applied:
        primary = PriceAdjustmentReason.MARGIN_FLOOR_HIT

    # ── Segment Personalisation ───────────────────────────────────────────────
    elif user_segment == "loyalty":
        primary = PriceAdjustmentReason.LOYALTY_DISCOUNT
        is_personalized = True
        if demand.demand_score > 0.65:
            secondary.append(PriceAdjustmentReason.HIGH_DEMAND)

    elif user_segment == "new_visitor":
        primary = PriceAdjustmentReason.NEW_VISITOR_OFFER
        is_personalized = True

    # ── Demand Signals ────────────────────────────────────────────────────────
    elif demand.demand_score >= 0.7:
        primary = PriceAdjustmentReason.HIGH_DEMAND
        if inventory <= 15:
            secondary.append(PriceAdjustmentReason.LIMITED_STOCK)
        if demand.competitor_gap_signal < 0.4:
            secondary.append(PriceAdjustmentReason.COMPETITOR_MATCH)

    elif demand.demand_score <= 0.35:
        primary = PriceAdjustmentReason.LOW_DEMAND
        if demand.competitor_gap_signal < 0.4:
            secondary.append(PriceAdjustmentReason.COMPETITOR_MATCH)

    # ── Scarcity ──────────────────────────────────────────────────────────────
    elif inventory <= 10:
        primary = PriceAdjustmentReason.LIMITED_STOCK

    # ── Competitor Match ──────────────────────────────────────────────────────
    elif demand.competitor_gap_signal < 0.35:
        primary = PriceAdjustmentReason.COMPETITOR_MATCH

    # ── No Adjustment ─────────────────────────────────────────────────────────
    else:
        primary = PriceAdjustmentReason.BASE_PRICE

    # ── Confidence Score ──────────────────────────────────────────────────────
    # Higher when signals agree; lower when they conflict
    signal_agreement = _compute_signal_agreement(demand, rules, primary)

    return PriceExplanation(
        primary_reason=primary,
        secondary_reasons=list(set(secondary)),   # Deduplicate
        user_copy=REASON_COPY[primary],
        discount_pct=discount_pct,
        demand_velocity=demand.raw_velocity,
        inventory_level=inventory,
        confidence=round(signal_agreement, 3),
        is_personalized=is_personalized,
        fairness_checked=True,
    )


def _compute_signal_agreement(
    demand: DemandSignals,
    rules: RuleCheckResult,
    primary: PriceAdjustmentReason,
) -> float:
    """
    Estimate confidence as the fraction of signals pointing in the
    same direction as the primary reason.
    """
    signals_in_agreement = 0
    total_signals = 4  # velocity, scarcity, competitor, time

    is_surge_reason = primary in {
        PriceAdjustmentReason.HIGH_DEMAND,
        PriceAdjustmentReason.LIMITED_STOCK,
        PriceAdjustmentReason.CAP_HIT,
    }
    is_discount_reason = primary in {
        PriceAdjustmentReason.LOW_DEMAND,
        PriceAdjustmentReason.COMPETITOR_MATCH,
        PriceAdjustmentReason.LOYALTY_DISCOUNT,
        PriceAdjustmentReason.NEW_VISITOR_OFFER,
        PriceAdjustmentReason.FLASH_SALE,
    }

    if is_surge_reason:
        if demand.normalised_velocity > 0.55:   signals_in_agreement += 1
        if demand.scarcity_multiplier > 1.05:   signals_in_agreement += 1
        if demand.competitor_gap_signal > 0.55: signals_in_agreement += 1
        if demand.time_multiplier > 0.95:       signals_in_agreement += 1
    elif is_discount_reason:
        if demand.normalised_velocity < 0.45:   signals_in_agreement += 1
        if demand.scarcity_multiplier <= 1.0:   signals_in_agreement += 1
        if demand.competitor_gap_signal < 0.50: signals_in_agreement += 1
        if demand.time_multiplier < 0.90:       signals_in_agreement += 1
    else:
        # Base price — all signals agree on neutrality
        if 0.4 < demand.normalised_velocity < 0.6:  signals_in_agreement += 1
        if demand.scarcity_multiplier == 1.0:        signals_in_agreement += 1
        if 0.4 < demand.competitor_gap_signal < 0.6: signals_in_agreement += 1
        if 0.85 < demand.time_multiplier < 1.05:     signals_in_agreement += 1

    # Boost confidence when no business rules had to override the model
    rule_penalty = 0.1 if rules.any_rule_applied else 0.0

    return max(0.1, min(1.0, (signals_in_agreement / total_signals) - rule_penalty))
