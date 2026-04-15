# ⚡ Dynamic Pricing & Personalization Engine

> Real-time behavioral signal processing · Sub-200ms p99 latency · Session-aware recommendations

---

## Repository Structure

```
pricing-engine/
├── frontend/                          # Next.js 14 App Router + Tailwind + Framer Motion
│   ├── src/
│   │   ├── app/
│   │   │   ├── storefront/            # Consumer-facing e-commerce UI
│   │   │   │   ├── page.tsx           # Product catalog with dynamic pricing
│   │   │   │   ├── product/[id]/      # PDP with price explanation badges
│   │   │   │   └── cart/              # Cart with real-time price updates
│   │   │   ├── dashboard/             # Admin/Judge's dashboard
│   │   │   │   ├── page.tsx           # Overview: latency, revenue, A/B status
│   │   │   │   ├── experiments/       # A/B test management & live results
│   │   │   │   ├── pricing/           # Pricing rule editor & audit log
│   │   │   │   └── fairness/          # Fairness audit visualization
│   │   │   └── api/                   # Next.js API routes (proxy layer)
│   │   ├── components/
│   │   │   ├── ui/                    # Primitives: Button, Badge, Tooltip, Skeleton
│   │   │   ├── storefront/
│   │   │   │   ├── ProductCard.tsx    # Card with dynamic price + transparency badge
│   │   │   │   ├── PriceDisplay.tsx   # Animated price with explanation tooltip
│   │   │   │   ├── RecommendationRow.tsx
│   │   │   │   └── CartDrawer.tsx
│   │   │   └── dashboard/
│   │   │       ├── LatencyGauge.tsx   # Real-time p50/p95/p99 gauges
│   │   │       ├── ABTestChart.tsx    # Conversion / AOV comparison charts
│   │   │       ├── EventStream.tsx    # Live clickstream feed
│   │   │       └── FairnessRadar.tsx  # Demographic fairness radar chart
│   │   ├── lib/
│   │   │   ├── api-client.ts          # Typed fetch wrapper with retry logic
│   │   │   ├── event-tracker.ts       # Behavioral event emitter (debounced)
│   │   │   └── constants.ts
│   │   ├── hooks/
│   │   │   ├── useDynamicPrice.ts     # SSE hook for live price updates
│   │   │   ├── useRecommendations.ts  # Recommendation fetcher with skeleton state
│   │   │   └── useEventTracker.ts     # Auto-fires clickstream events
│   │   ├── store/
│   │   │   └── session.ts             # Zustand: session ID, cart, user segment
│   │   └── types/
│   │       └── index.ts               # Shared TypeScript interfaces
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   └── package.json
│
├── backend/                           # FastAPI — fully async Python 3.11+
│   ├── app/
│   │   ├── main.py                    # FastAPI app factory, CORS, middleware mounts
│   │   ├── api/v1/
│   │   │   ├── router.py              # Aggregates all v1 endpoint routers
│   │   │   └── endpoints/
│   │   │       ├── events.py          # ← POST /events/ingest  (Redis Streams)
│   │   │       ├── pricing.py         # GET  /pricing/{product_id}
│   │   │       ├── recommendations.py # GET  /recommendations/{session_id}
│   │   │       ├── experiments.py     # CRUD /experiments + metrics read
│   │   │       ├── stream.py          # GET  /stream/prices  (SSE)
│   │   │       └── health.py          # GET  /health  (latency probe)
│   │   ├── core/
│   │   │   ├── config.py              # Pydantic Settings — env-driven
│   │   │   ├── redis_client.py        # Async Redis pool + Stream helpers
│   │   │   ├── feature_store.py       # Redis-backed real-time feature store
│   │   │   └── security.py            # API key / JWT middleware
│   │   ├── models/
│   │   │   ├── event.py               # SQLModel: raw event persistence
│   │   │   ├── product.py             # Product + inventory
│   │   │   └── experiment.py          # A/B experiment + variant assignments
│   │   ├── schemas/
│   │   │   ├── event.py               # Pydantic: ClickstreamEvent, EventBatch
│   │   │   ├── pricing.py             # PricingRequest, PricingResponse
│   │   │   └── recommendation.py      # RecommendationResponse
│   │   ├── services/
│   │   │   ├── events/
│   │   │   │   ├── ingestion.py       # Stream writer + feature computation trigger
│   │   │   │   ├── consumer.py        # Background consumer group worker
│   │   │   │   └── feature_compute.py # Session score, affinity, intent probability
│   │   │   ├── pricing/
│   │   │   │   ├── engine.py          # Demand-responsive pricing orchestrator
│   │   │   │   ├── demand_model.py    # Sklearn velocity + elasticity model
│   │   │   │   ├── business_rules.py  # Margin floors, discount caps, parity
│   │   │   │   └── explainer.py       # Price change reason generator
│   │   │   ├── recommendations/
│   │   │   │   ├── engine.py          # Hybrid CF + session-based orchestrator
│   │   │   │   ├── collaborative.py   # Matrix factorization (sklearn / scipy)
│   │   │   │   ├── session_model.py   # GRU4Rec PyTorch model + inference
│   │   │   │   └── cold_start.py      # Context-signal fallback for new users
│   │   │   └── experiments/
│   │   │       ├── framework.py       # Bucket assignment + metric tracking
│   │   │       └── metrics.py         # Conversion rate, AOV, RPS calculator
│   │   ├── ml/
│   │   │   ├── pricing/
│   │   │   │   └── train_demand.py    # Offline demand elasticity trainer
│   │   │   └── recommendations/
│   │   │       ├── train_cf.py        # Collaborative filtering trainer
│   │   │       └── train_gru4rec.py   # GRU4Rec session model trainer
│   │   ├── db/
│   │   │   ├── session.py             # Async SQLAlchemy engine + session factory
│   │   │   └── init_db.py             # Schema creation + seed data
│   │   └── middleware/
│   │       ├── latency.py             # X-Response-Time header + p99 tracking
│   │       └── ab_router.py           # Experiment bucket injection per request
│   └── tests/
│       ├── unit/
│       │   ├── test_pricing_engine.py
│       │   ├── test_business_rules.py
│       │   └── test_feature_compute.py
│       └── integration/
│           ├── test_event_ingestion.py
│           └── test_recommendations.py
│
├── infra/
│   ├── redis/
│   │   └── redis.conf                 # Stream maxlen, persistence, ACL config
│   └── docker/
│       ├── Dockerfile.backend
│       ├── Dockerfile.frontend
│       └── docker-compose.yml         # Full stack: backend + frontend + Redis
│
├── scripts/
│   ├── seed_products.py               # Populate catalog + pricing seeds
│   ├── simulate_traffic.py            # Load-test clickstream generator
│   └── run_fairness_audit.py          # Demographic parity checker
│
└── .github/workflows/
    └── ci.yml                         # Lint + test + latency regression gate
```
