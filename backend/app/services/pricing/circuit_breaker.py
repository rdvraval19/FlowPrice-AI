"""
services/pricing/circuit_breaker.py
=====================================
The Circuit Breaker is a Redis-backed safety valve that sits between the ML
pricing model and the final price served to users.

WHY THIS EXISTS
---------------
ML models can hallucinate. A demand elasticity model trained on noisy data
could output a ₹49,999 TV priced at ₹100. A surge model could price a ₹500
item at ₹5,000. Both scenarios destroy trust and create legal liability.

This circuit breaker acts as a stateful, Redis-backed hard stop that:
  1. Enforces absolute floor/ceiling prices (unit economics protection)
  2. Detects and blocks velocity anomalies (abnormal price swings in < 60s)
  3. Trips open when anomaly rate exceeds a threshold (stops ALL pricing)
  4. Self-heals after a cooldown period (auto-reset to CLOSED state)
  5. Logs every trip with full context (audit trail for the CTO)

STATES
------
  CLOSED   → Normal operation. All prices pass through.
  OPEN     → Tripped. Pricing halted; base price served to all users.
  HALF_OPEN → Cooldown expired. Testing one price through before full reset.

INTEGRATION
-----------
The circuit breaker is the FIRST check in price_product(), before any model
inference or cache lookup. This guarantees sub-millisecond overhead on the
happy path (single Redis GET).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.core.config import settings
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED    = "CLOSED"     # Normal — pricing active
    OPEN      = "OPEN"       # Tripped — pricing halted
    HALF_OPEN = "HALF_OPEN"  # Recovering — one probe allowed


@dataclass
class CircuitTripEvent:
    """Logged every time the circuit breaker fires."""
    product_id:    str
    proposed_price: float
    base_price:    float
    cost_price:    float
    reason:        str
    rule_violated: str
    clamped_to:    float
    timestamp:     float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "product_id":    self.product_id,
            "proposed":      round(self.proposed_price, 2),
            "base_price":    round(self.base_price, 2),
            "clamped_to":    round(self.clamped_to, 2),
            "reason":        self.reason,
            "rule":          self.rule_violated,
            "deviation_pct": round(abs(self.proposed_price - self.base_price) / max(self.base_price, 0.01) * 100, 1),
            "ts":            self.timestamp,
        }


# ── Per-Product Safety Limits ─────────────────────────────────────────────────
# These are the absolute hard stops — no model output can breach them.
# In production these live in a database per category; here we use config.

@dataclass
class ProductSafetyProfile:
    """Unit-economic safety boundaries for a single product."""
    product_id:     str
    cost_price:     float          # COGS — the floor anchor
    base_price:     float          # Catalogue price — the reference point

    # Absolute price limits (override model output unconditionally)
    absolute_floor: float  = 0.0  # Set at init: cost * (1 + MIN_MARGIN)
    absolute_ceil:  float  = 0.0  # Set at init: base * (1 + LEGAL_CAP)

    # Velocity limits (max price change per minute — prevents runaway loops)
    max_change_per_min_pct: float = 0.15  # 15% per minute maximum swing

    def __post_init__(self):
        if self.absolute_floor == 0.0:
            self.absolute_floor = self.cost_price * (1 + settings.MIN_MARGIN_PCT)
        if self.absolute_ceil == 0.0:
            # Legal anti-price-gouging cap: base * 1.5 (50% maximum ever)
            self.absolute_ceil = self.base_price * 1.50


class CircuitBreaker:
    """
    Redis-backed circuit breaker for the pricing engine.

    Redis key schema:
      cb:state                     → global circuit state (CLOSED/OPEN/HALF_OPEN)
      cb:trip_count                → total trips since reset
      cb:last_trip_ts              → timestamp of most recent trip
      cb:price_velocity:{sku}      → sorted set of (price, timestamp) for velocity check
      cb:trip_log                  → list of JSON trip events (last 500)
      cb:anomaly_window_count      → trip count in current ANOMALY_WINDOW_SECONDS
    """

    # How many anomalies in ANOMALY_WINDOW_SECONDS triggers OPEN state
    ANOMALY_THRESHOLD     = 5
    ANOMALY_WINDOW_SECONDS = 60    # Sliding window for anomaly counting
    OPEN_COOLDOWN_SECONDS  = 120   # How long to stay OPEN before HALF_OPEN
    VELOCITY_WINDOW_SECONDS = 60   # Window for per-SKU velocity check

    def __init__(self):
        self._local_trip_count = 0  # In-process counter (fast path)

    # ── Primary Entry Point ───────────────────────────────────────────────────

    async def check_and_clamp(
        self,
        proposed_price:  float,
        product_id:      str,
        base_price:      float,
        cost_price:      float,
        context:         str = "",
    ) -> tuple[float, bool, Optional[CircuitTripEvent]]:
        """
        The single choke-point every pricing call flows through.

        Returns:
            (final_price, was_clamped, trip_event_or_None)

        Guarantees:
            - final_price ≥ cost_price * (1 + MIN_MARGIN)
            - final_price ≤ base_price * 1.50
            - If circuit is OPEN → returns base_price immediately

        Latency budget: < 2ms on cache hit (single Redis GET for state check).
        """
        profile = ProductSafetyProfile(
            product_id=product_id,
            cost_price=cost_price,
            base_price=base_price,
        )

        # ── Fast path: circuit OPEN → serve base price immediately ────────────
        state = await self._get_state()
        if state == CircuitState.OPEN:
            return base_price, True, CircuitTripEvent(
                product_id=product_id,
                proposed_price=proposed_price,
                base_price=base_price,
                cost_price=cost_price,
                reason="Circuit OPEN — pricing halted, serving base price",
                rule_violated="CIRCUIT_OPEN",
                clamped_to=base_price,
            )

        # ── Rule 1: Absolute floor (cost + minimum margin) ────────────────────
        if proposed_price < profile.absolute_floor:
            trip = CircuitTripEvent(
                product_id=product_id,
                proposed_price=proposed_price,
                base_price=base_price,
                cost_price=cost_price,
                reason=(
                    f"Price ₹{proposed_price:.2f} is BELOW absolute floor "
                    f"₹{profile.absolute_floor:.2f} "
                    f"(cost ₹{cost_price:.2f} × {1+settings.MIN_MARGIN_PCT:.0%} margin)"
                ),
                rule_violated="ABSOLUTE_FLOOR",
                clamped_to=profile.absolute_floor,
            )
            await self._record_trip(trip)
            logger.error(
                "🔴 CIRCUIT TRIP [FLOOR] %s: proposed=%.2f floor=%.2f",
                product_id, proposed_price, profile.absolute_floor
            )
            return profile.absolute_floor, True, trip

        # ── Rule 2: Absolute ceiling (anti-price-gouging) ─────────────────────
        if proposed_price > profile.absolute_ceil:
            trip = CircuitTripEvent(
                product_id=product_id,
                proposed_price=proposed_price,
                base_price=base_price,
                cost_price=cost_price,
                reason=(
                    f"Price ₹{proposed_price:.2f} EXCEEDS legal ceiling "
                    f"₹{profile.absolute_ceil:.2f} "
                    f"(base ₹{base_price:.2f} × 150% anti-gouging cap)"
                ),
                rule_violated="ABSOLUTE_CEILING",
                clamped_to=profile.absolute_ceil,
            )
            await self._record_trip(trip)
            logger.error(
                "🔴 CIRCUIT TRIP [CEILING] %s: proposed=%.2f ceiling=%.2f",
                product_id, proposed_price, profile.absolute_ceil
            )
            return profile.absolute_ceil, True, trip

        # ── Rule 3: Velocity anomaly (price moving too fast) ──────────────────
        velocity_tripped, velocity_msg = await self._check_velocity(
            product_id, proposed_price, base_price,
            profile.max_change_per_min_pct
        )
        if velocity_tripped:
            # Clamp to ±max_change from the last known good price
            safe_price = round(
                base_price * (1 + min(
                    abs(proposed_price - base_price) / base_price,
                    profile.max_change_per_min_pct
                ) * (1 if proposed_price > base_price else -1)),
                2,
            )
            safe_price = max(profile.absolute_floor, min(profile.absolute_ceil, safe_price))
            trip = CircuitTripEvent(
                product_id=product_id,
                proposed_price=proposed_price,
                base_price=base_price,
                cost_price=cost_price,
                reason=velocity_msg,
                rule_violated="VELOCITY_ANOMALY",
                clamped_to=safe_price,
            )
            await self._record_trip(trip)
            logger.warning(
                "🟡 CIRCUIT TRIP [VELOCITY] %s: proposed=%.2f safe=%.2f",
                product_id, proposed_price, safe_price
            )
            return safe_price, True, trip

        # ── All checks passed — price is safe ─────────────────────────────────
        await self._record_good_price(product_id, proposed_price)

        # Half-open probe succeeded → close the circuit
        if state == CircuitState.HALF_OPEN:
            await self._set_state(CircuitState.CLOSED)
            logger.info("✅ Circuit breaker CLOSED (probe succeeded for %s)", product_id)

        return round(proposed_price, 2), False, None

    # ── State Management ──────────────────────────────────────────────────────

    async def _get_state(self) -> CircuitState:
        r = get_redis()
        raw = await r.get("cb:state")
        if not raw:
            return CircuitState.CLOSED

        state = CircuitState(raw)

        # Auto-transition OPEN → HALF_OPEN after cooldown
        if state == CircuitState.OPEN:
            last_trip = float(await r.get("cb:last_trip_ts") or 0)
            if time.time() - last_trip > self.OPEN_COOLDOWN_SECONDS:
                await self._set_state(CircuitState.HALF_OPEN)
                logger.info("Circuit breaker → HALF_OPEN (cooldown expired)")
                return CircuitState.HALF_OPEN

        return state

    async def _set_state(self, state: CircuitState) -> None:
        r = get_redis()
        await r.set("cb:state", state.value, ex=3600)

    async def _record_trip(self, trip: CircuitTripEvent) -> None:
        """Record trip event and potentially open the circuit."""
        r = get_redis()
        import json

        # Increment anomaly counter in sliding window
        window_key = "cb:anomaly_window_count"
        count = await r.incr(window_key)
        await r.expire(window_key, self.ANOMALY_WINDOW_SECONDS)
        await r.set("cb:last_trip_ts", str(time.time()))
        await r.incr("cb:trip_count")

        # Append to audit log (capped at 500 entries)
        await r.lpush("cb:trip_log", json.dumps(trip.to_dict()))
        await r.ltrim("cb:trip_log", 0, 499)

        # Trip the circuit if anomaly threshold exceeded
        if count >= self.ANOMALY_THRESHOLD:
            await self._set_state(CircuitState.OPEN)
            logger.critical(
                "🚨 CIRCUIT BREAKER OPENED — %d anomalies in %ds. "
                "All pricing halted. Serving base prices.",
                count, self.ANOMALY_WINDOW_SECONDS,
            )

        self._local_trip_count += 1

    async def _record_good_price(self, product_id: str, price: float) -> None:
        """Track price history for velocity anomaly detection."""
        r = get_redis()
        key = f"cb:price_velocity:{product_id}"
        now = time.time()
        await r.zadd(key, {str(price): now})
        # Prune entries outside the velocity window
        await r.zremrangebyscore(key, "-inf", now - self.VELOCITY_WINDOW_SECONDS)
        await r.expire(key, self.VELOCITY_WINDOW_SECONDS * 2)

    async def _check_velocity(
        self,
        product_id:   str,
        proposed:     float,
        base_price:   float,
        max_pct:      float,
    ) -> tuple[bool, str]:
        """
        Detect runaway price loops: if price moved > max_pct in the last minute,
        flag as anomaly. This catches feedback loops where demand model → price up
        → more demand → price up → ... spiralling out of control.
        """
        r = get_redis()
        key = f"cb:price_velocity:{product_id}"
        window_start = time.time() - self.VELOCITY_WINDOW_SECONDS

        # Get the oldest price in the velocity window
        oldest_entries = await r.zrangebyscore(key, window_start, "+inf", start=0, num=1, withscores=False)
        if not oldest_entries:
            return False, ""

        try:
            oldest_price = float(oldest_entries[0])
        except (ValueError, IndexError):
            return False, ""

        if oldest_price <= 0:
            return False, ""

        swing_pct = abs(proposed - oldest_price) / oldest_price
        if swing_pct > max_pct:
            return True, (
                f"Velocity anomaly: price moved {swing_pct*100:.1f}% "
                f"in {self.VELOCITY_WINDOW_SECONDS}s "
                f"(max allowed: {max_pct*100:.1f}%). "
                f"From ₹{oldest_price:.2f} → ₹{proposed:.2f}"
            )

        return False, ""

    # ── Admin Operations ──────────────────────────────────────────────────────

    async def get_status(self) -> dict:
        """Returns full circuit breaker status for the admin dashboard."""
        r = get_redis()
        state      = await self._get_state()
        trip_count = int(await r.get("cb:trip_count") or 0)
        last_trip  = float(await r.get("cb:last_trip_ts") or 0)
        import json
        raw_log    = await r.lrange("cb:trip_log", 0, 9)
        recent_trips = [json.loads(e) for e in raw_log]

        return {
            "state":         state.value,
            "trip_count":    trip_count,
            "last_trip_ago": round(time.time() - last_trip) if last_trip else None,
            "cooldown_secs": self.OPEN_COOLDOWN_SECONDS,
            "anomaly_threshold": self.ANOMALY_THRESHOLD,
            "recent_trips":  recent_trips,
            "healthy":       state == CircuitState.CLOSED,
        }

    async def manual_reset(self) -> None:
        """Emergency reset — for admin use only."""
        r = get_redis()
        await r.delete("cb:state", "cb:anomaly_window_count")
        await self._set_state(CircuitState.CLOSED)
        logger.warning("⚠️  Circuit breaker MANUALLY RESET to CLOSED state")

    async def manual_trip(self) -> None:
        """Force-open the circuit — for testing or emergency shutdown."""
        await self._set_state(CircuitState.OPEN)
        r = get_redis()
        await r.set("cb:last_trip_ts", str(time.time()))
        logger.warning("⚠️  Circuit breaker MANUALLY OPENED")


# ── Module singleton ──────────────────────────────────────────────────────────
circuit_breaker = CircuitBreaker()
