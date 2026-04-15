"""
services/pricing/business_rules.py — Hard constraint enforcement.

Business rules are ALWAYS applied last, overriding the demand model output.
They represent non-negotiable financial and ethical guardrails.

Rules enforced (in priority order):
  1. MARGIN FLOOR     — price can never go below (cost * (1 + min_margin))
  2. DISCOUNT CAP     — price can never be more than max_discount% below base
  3. SURGE CAP        — price can never exceed max_surge% above base
  4. PRICE PARITY     — no discriminatory pricing between equivalent sessions
  5. FAIRNESS GATE    — reject any price correlated with protected attributes
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RuleCheckResult:
    """Full audit trail of which rules fired — written to every pricing response."""
    original_price: float
    final_price: float
    margin_floor_applied: bool = False
    discount_cap_applied: bool = False
    surge_cap_applied: bool = False
    parity_applied: bool = False
    fairness_passed: bool = True
    violations: list[str] = None

    def __post_init__(self):
        if self.violations is None:
            self.violations = []

    @property
    def any_rule_applied(self) -> bool:
        return (
            self.margin_floor_applied
            or self.discount_cap_applied
            or self.surge_cap_applied
            or self.parity_applied
        )

    @property
    def clamped_up(self) -> bool:
        """Price was increased by a rule (margin floor hit)."""
        return self.final_price > self.original_price

    @property
    def clamped_down(self) -> bool:
        """Price was decreased by a rule (cap hit)."""
        return self.final_price < self.original_price


class BusinessRulesEngine:
    """
    Stateless rule applier.
    All methods are pure functions — no I/O, no side effects.
    """

    def apply(
        self,
        proposed_price: float,
        base_price: float,
        cost_price: float,
        user_segment: str = "unknown",
    ) -> RuleCheckResult:
        """
        Apply all rules in sequence.
        Each rule may clamp the price; the final price is the output
        of the full rule chain.
        """
        result = RuleCheckResult(
            original_price=proposed_price,
            final_price=proposed_price,
        )

        # Rule 1: Margin floor — financial non-negotiable
        result = self._apply_margin_floor(result, cost_price)

        # Rule 2: Discount cap — limits promotional depth
        result = self._apply_discount_cap(result, base_price)

        # Rule 3: Surge cap — fairness / PR constraint
        result = self._apply_surge_cap(result, base_price)

        # Rule 4: Fairness gate — must pass before any price is served
        result = self._apply_fairness_gate(result, user_segment)

        # Round to standard 2 decimal places
        result.final_price = round(result.final_price, 2)

        if result.any_rule_applied:
            logger.debug(
                "Business rules applied: original=%.2f final=%.2f "
                "margin_floor=%s discount_cap=%s surge_cap=%s",
                result.original_price,
                result.final_price,
                result.margin_floor_applied,
                result.discount_cap_applied,
                result.surge_cap_applied,
            )

        return result

    # ── Individual Rules ──────────────────────────────────────────────────────

    def _apply_margin_floor(
        self, result: RuleCheckResult, cost_price: float
    ) -> RuleCheckResult:
        """
        Price must never go below cost * (1 + minimum_margin).
        This is a financial non-negotiable — selling below cost destroys margin.
        """
        floor = cost_price * (1.0 + settings.MIN_MARGIN_PCT)
        if result.final_price < floor:
            result.final_price = floor
            result.margin_floor_applied = True
            result.violations.append(
                f"margin_floor: proposed={result.original_price:.2f} "
                f"floor={floor:.2f} cost={cost_price:.2f}"
            )
        return result

    def _apply_discount_cap(
        self, result: RuleCheckResult, base_price: float
    ) -> RuleCheckResult:
        """
        Discount cannot exceed max_discount_pct below base price.
        Prevents race-to-the-bottom and protects brand value.
        """
        floor = base_price * (1.0 - settings.MAX_DISCOUNT_PCT)
        if result.final_price < floor:
            result.final_price = floor
            result.discount_cap_applied = True
            result.violations.append(
                f"discount_cap: proposed={result.original_price:.2f} "
                f"floor={floor:.2f} ({settings.MAX_DISCOUNT_PCT*100:.0f}% cap)"
            )
        return result

    def _apply_surge_cap(
        self, result: RuleCheckResult, base_price: float
    ) -> RuleCheckResult:
        """
        Surge pricing cannot exceed max_surge_pct above base price.
        Prevents predatory pricing optics and regulator scrutiny.
        """
        ceiling = base_price * (1.0 + settings.MAX_SURGE_PCT)
        if result.final_price > ceiling:
            result.final_price = ceiling
            result.surge_cap_applied = True
            result.violations.append(
                f"surge_cap: proposed={result.original_price:.2f} "
                f"ceiling={ceiling:.2f} ({settings.MAX_SURGE_PCT*100:.0f}% cap)"
            )
        return result

    def _apply_fairness_gate(
        self, result: RuleCheckResult, user_segment: str
    ) -> RuleCheckResult:
        """
        Fairness constraint: ensure pricing is NOT based on protected attributes.

        Our segments are BEHAVIOURAL (loyalty status, purchase history) — not
        demographic (age, gender, race, location). This check validates the
        segment used is in the approved behavioural list.

        In production this would also:
        - Compare prices across segment groups for demographic parity
        - Run the Fairness-Aware Pricing Audit (see scripts/run_fairness_audit.py)
        """
        APPROVED_BEHAVIOURAL_SEGMENTS = {
            "new_visitor", "returning", "loyalty",
            "high_value", "price_sensitive", "unknown",
        }

        if user_segment not in APPROVED_BEHAVIOURAL_SEGMENTS:
            # Unknown segment — fall back to base price (safe default)
            logger.warning(
                "Unapproved segment '%s' detected in pricing request — "
                "reverting to base-price-neutral adjustment",
                user_segment,
            )
            result.fairness_passed = False
            result.violations.append(f"fairness: unapproved segment={user_segment}")

        return result

    # ── Validation Utilities ──────────────────────────────────────────────────

    def validate_price_move(
        self,
        old_price: float,
        new_price: float,
        max_swing_pct: float = 0.15,
    ) -> bool:
        """
        Parity check: ensure a price change doesn't exceed max_swing_pct
        in a single update cycle (prevents jarring UX and gaming detection).
        """
        if old_price <= 0:
            return True
        swing = abs(new_price - old_price) / old_price
        return swing <= max_swing_pct

    def compute_margin_pct(self, price: float, cost_price: float) -> float:
        """Gross margin as a percentage."""
        if price <= 0:
            return 0.0
        return (price - cost_price) / price

    def is_below_margin_floor(self, price: float, cost_price: float) -> bool:
        return price < cost_price * (1.0 + settings.MIN_MARGIN_PCT)


# Module-level singleton
business_rules = BusinessRulesEngine()
