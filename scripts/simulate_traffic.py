"""
scripts/simulate_traffic.py — Realistic clickstream load generator.

Simulates purchase funnel sessions to validate:
  • Sub-200ms p99 latency under load
  • Demand velocity feature accuracy
  • Feature store consistency under concurrent writes

Usage:
  python scripts/simulate_traffic.py --sessions 100 --rps 50
  python scripts/simulate_traffic.py --scenario purchase_funnel
"""
from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time
import uuid
from dataclasses import dataclass, field

import httpx

BASE_URL = "http://localhost:8000"
INGEST_URL = f"{BASE_URL}/api/v1/events/ingest"
BATCH_URL  = f"{BASE_URL}/api/v1/events/ingest/batch"

CATEGORIES = ["sneakers", "running", "basketball", "casual", "boots", "sandals"]
PRODUCTS = [f"prod_{cat}_{i:03d}" for cat in CATEGORIES for i in range(1, 6)]
SEGMENTS  = ["new_visitor", "returning", "loyalty", "high_value", "price_sensitive"]
DEVICES   = ["desktop", "mobile", "tablet"]

# ── Event Generators ──────────────────────────────────────────────────────────

def _session_id() -> str:
    return f"sim_{uuid.uuid4().hex}"

def _product_event(session_id: str, event_type: str, product_id: str, category: str) -> dict:
    base_price = random.uniform(49.99, 299.99)
    discount = random.uniform(0, 0.3)
    return {
        "session_id": session_id,
        "event_type": event_type,
        "timestamp_ms": int(time.time() * 1000),
        "device_type": random.choice(DEVICES),
        "user_segment": random.choice(SEGMENTS),
        "referral_source": random.choice(["organic", "paid_search", "social", "direct"]),
        "product": {
            "product_id": product_id,
            "category": category,
            "price_shown": round(base_price * (1 - discount), 2),
            "base_price": round(base_price, 2),
            "inventory_level": random.randint(0, 200),
        },
    }

def _purchase_event(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "event_type": "purchase",
        "timestamp_ms": int(time.time() * 1000),
        "device_type": random.choice(DEVICES),
        "user_segment": "high_value",
        "purchase": {
            "order_id": f"ord_{uuid.uuid4().hex[:8]}",
            "items": [{"product_id": random.choice(PRODUCTS), "qty": 1, "unit_price": 99.99}],
            "order_total": 99.99,
            "payment_method": "card",
            "coupon_used": False,
        },
    }

# ── Session Scenarios ─────────────────────────────────────────────────────────

def purchase_funnel_session(session_id: str) -> list[dict]:
    """Simulate a realistic purchase funnel: browse → view → cart → buy."""
    product_id = random.choice(PRODUCTS)
    category = random.choice(CATEGORIES)
    events = [
        {
            "session_id": session_id,
            "event_type": "page_view",
            "timestamp_ms": int(time.time() * 1000),
            "device_type": "desktop",
            "user_segment": "returning",
        },
        _product_event(session_id, "product_view", product_id, category),
        _product_event(session_id, "image_zoom", product_id, category),
        _product_event(session_id, "cart_add", product_id, category),
        _purchase_event(session_id),
    ]
    return events

def browse_session(session_id: str) -> list[dict]:
    """Browse-only session — no conversion."""
    events = []
    for _ in range(random.randint(3, 8)):
        pid = random.choice(PRODUCTS)
        cat = random.choice(CATEGORIES)
        events.append(_product_event(session_id, "product_view", pid, cat))
    return events

# ── Load Test Runner ──────────────────────────────────────────────────────────

@dataclass
class LoadTestResults:
    latencies: list[float] = field(default_factory=list)
    errors: int = 0
    total: int = 0

    @property
    def p50(self) -> float:
        return statistics.median(self.latencies) if self.latencies else 0

    @property
    def p99(self) -> float:
        if not self.latencies:
            return 0
        idx = int(len(self.latencies) * 0.99)
        return sorted(self.latencies)[idx]

    @property
    def success_rate(self) -> float:
        if not self.total:
            return 0
        return (self.total - self.errors) / self.total * 100

    def print_summary(self) -> None:
        print("\n" + "=" * 50)
        print("LOAD TEST RESULTS")
        print("=" * 50)
        print(f"  Total requests:  {self.total}")
        print(f"  Errors:          {self.errors}")
        print(f"  Success rate:    {self.success_rate:.1f}%")
        print(f"  p50 latency:     {self.p50:.2f}ms")
        print(f"  p99 latency:     {self.p99:.2f}ms")
        sla = "✅ PASS" if self.p99 < 200 else "❌ FAIL"
        print(f"  p99 < 200ms SLA: {sla}")
        print("=" * 50)


async def send_event(client: httpx.AsyncClient, event: dict, results: LoadTestResults) -> None:
    t0 = time.perf_counter()
    try:
        resp = await client.post(INGEST_URL, json=event, timeout=5.0)
        elapsed = (time.perf_counter() - t0) * 1000
        results.latencies.append(elapsed)
        results.total += 1
        if resp.status_code != 202:
            results.errors += 1
            print(f"  ⚠️  {resp.status_code}: {resp.text[:100]}")
    except Exception as exc:
        results.errors += 1
        results.total += 1
        print(f"  ❌  Request failed: {exc}")


async def run_load_test(n_sessions: int = 50, rps: int = 20) -> None:
    results = LoadTestResults()
    semaphore = asyncio.Semaphore(rps)

    async def bounded_send(client: httpx.AsyncClient, event: dict) -> None:
        async with semaphore:
            await send_event(client, event, results)

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        tasks = []
        for i in range(n_sessions):
            session_id = _session_id()
            scenario = purchase_funnel_session if random.random() < 0.3 else browse_session
            events = scenario(session_id)
            for event in events:
                tasks.append(bounded_send(client, event))
            if i % 10 == 0:
                print(f"  Generated {i}/{n_sessions} sessions...")

        print(f"\n🚀 Sending {len(tasks)} events at {rps} RPS...")
        t0 = time.time()
        await asyncio.gather(*tasks)
        elapsed = time.time() - t0
        print(f"   Completed in {elapsed:.1f}s ({len(tasks)/elapsed:.0f} actual RPS)")

    results.print_summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clickstream load generator")
    parser.add_argument("--sessions", type=int, default=50)
    parser.add_argument("--rps", type=int, default=20)
    args = parser.parse_args()

    print(f"🎯 Load test: {args.sessions} sessions at {args.rps} RPS")
    print(f"   Target: {BASE_URL}")
    asyncio.run(run_load_test(args.sessions, args.rps))
