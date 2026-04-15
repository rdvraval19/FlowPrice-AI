"""tests/unit/test_pricing_engine.py — Unit tests for pricing + business rules."""
import pytest
from app.services.pricing.business_rules import BusinessRulesEngine
from app.services.pricing.demand_model import compute_demand_score, velocity_to_adjustment_pct
from app.services.pricing.explainer import generate_explanation


class TestBusinessRules:
    def setup_method(self):
        self.engine = BusinessRulesEngine()

    def test_margin_floor_enforced(self):
        result = self.engine.apply(proposed_price=50.0, base_price=100.0, cost_price=90.0)
        assert result.final_price >= 90.0 * 1.10
        assert result.margin_floor_applied

    def test_discount_cap_enforced(self):
        result = self.engine.apply(proposed_price=40.0, base_price=100.0, cost_price=20.0)
        assert result.final_price >= 100.0 * 0.60   # max 40% discount
        assert result.discount_cap_applied

    def test_surge_cap_enforced(self):
        result = self.engine.apply(proposed_price=200.0, base_price=100.0, cost_price=20.0)
        assert result.final_price <= 100.0 * 1.25   # max 25% surge
        assert result.surge_cap_applied

    def test_no_rule_fires_on_fair_price(self):
        result = self.engine.apply(proposed_price=95.0, base_price=100.0, cost_price=50.0)
        assert not result.any_rule_applied
        assert result.final_price == 95.0

    def test_margin_floor_takes_priority_over_discount_cap(self):
        # Cost is very high — margin floor > discount cap
        result = self.engine.apply(proposed_price=40.0, base_price=100.0, cost_price=85.0)
        floor = 85.0 * 1.10
        assert result.final_price >= floor
        assert result.margin_floor_applied

    def test_price_rounded_to_two_decimals(self):
        result = self.engine.apply(proposed_price=99.999, base_price=100.0, cost_price=20.0)
        assert result.final_price == round(result.final_price, 2)


class TestDemandModel:
    def test_high_velocity_gives_high_score(self):
        signals = compute_demand_score(velocity=100, inventory=50, base_price=100, competitor_price=None)
        assert signals.demand_score > 0.6

    def test_low_velocity_gives_low_score(self):
        signals = compute_demand_score(velocity=1, inventory=200, base_price=100, competitor_price=None)
        assert signals.demand_score < 0.5

    def test_low_inventory_boosts_score(self):
        low = compute_demand_score(velocity=20, inventory=3, base_price=100, competitor_price=None)
        high = compute_demand_score(velocity=20, inventory=200, base_price=100, competitor_price=None)
        assert low.demand_score > high.demand_score

    def test_adjustment_pct_within_bounds(self):
        for score in [0.0, 0.25, 0.5, 0.75, 1.0]:
            adj = velocity_to_adjustment_pct(score, max_surge=0.25, max_discount=0.40)
            assert -0.40 <= adj <= 0.25

    def test_neutral_score_gives_zero_adjustment(self):
        adj = velocity_to_adjustment_pct(0.5, max_surge=0.25, max_discount=0.40)
        assert abs(adj) < 0.01  # Approximately zero at midpoint
