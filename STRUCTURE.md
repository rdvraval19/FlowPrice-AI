# Dynamic Pricing & Personalization Engine — Monorepo Structure

```
pricing-engine/
├── README.md
├── docker-compose.yml
├── .env.example
│
├── backend/                          # FastAPI Python Backend
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── main.py                       # FastAPI app entrypoint
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                   # Shared dependencies (Redis, DB)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py             # Aggregates all v1 routes
│   │       ├── events.py             # ★ Real-time event ingestion (Redis Streams)
│   │       ├── pricing.py            # Dynamic pricing endpoints
│   │       ├── recommendations.py    # Recommendation engine endpoints
│   │       ├── products.py           # Product catalog (Redis-cached)
│   │       ├── experiments.py        # A/B testing framework
│   │       └── dashboard.py          # Admin metrics/analytics
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                 # Settings (pydantic-settings)
│   │   ├── redis_client.py           # Async Redis connection pool
│   │   └── logging.py               # Structured JSON logging
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── event_processor.py        # Stream consumer + feature computation
│   │   ├── feature_store.py          # Redis feature store (session/user features)
│   │   ├── pricing_engine.py         # Demand-responsive pricing algorithm
│   │   ├── recommendation_engine.py  # Hybrid CF + session-based recs
│   │   ├── ab_testing.py             # Experiment assignment & metric tracking
│   │   └── fairness_auditor.py       # Bias detection & price parity checks
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py                # Pydantic request/response schemas
│   │   ├── pricing_model.py          # Scikit-learn pricing model wrapper
│   │   └── recommendation_model.py   # PyTorch GRU4Rec / Transformer model
│   │
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── gru4rec.py                # GRU4Rec session-based model (PyTorch)
│   │   ├── collaborative_filter.py   # Matrix factorization (sklearn/implicit)
│   │   ├── cold_start.py             # Contextual bandit for cold-start users
│   │   ├── demand_elasticity.py      # Price elasticity estimation
│   │   └── training/
│   │       ├── train_gru4rec.py
│   │       └── train_pricing.py
│   │
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── stream_consumer.py        # Background Redis Streams consumer
│   │   └── feature_aggregator.py     # Periodic feature aggregation worker
│   │
│   └── tests/
│       ├── conftest.py
│       ├── test_events.py
│       ├── test_pricing.py
│       └── test_recommendations.py
│
├── frontend/                         # Next.js 14 App Router Frontend
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   │
│   ├── app/
│   │   ├── layout.tsx                # Root layout (fonts, providers)
│   │   ├── page.tsx                  # Storefront homepage
│   │   ├── globals.css
│   │   │
│   │   ├── products/
│   │   │   ├── page.tsx              # Product listing with dynamic prices
│   │   │   └── [id]/
│   │   │       └── page.tsx          # Product detail + price explanation badge
│   │   │
│   │   ├── cart/
│   │   │   └── page.tsx
│   │   │
│   │   └── dashboard/                # Judge's Admin Dashboard
│   │       ├── layout.tsx
│   │       ├── page.tsx              # Dashboard overview
│   │       ├── ab-tests/
│   │       │   └── page.tsx          # A/B test results & live graphs
│   │       ├── pricing/
│   │       │   └── page.tsx          # Pricing engine monitor
│   │       └── latency/
│   │           └── page.tsx          # p99 latency & system health
│   │
│   ├── components/
│   │   ├── ui/                       # Design system primitives
│   │   │   ├── Button.tsx
│   │   │   ├── Badge.tsx
│   │   │   ├── Skeleton.tsx
│   │   │   ├── Tooltip.tsx
│   │   │   └── Card.tsx
│   │   │
│   │   ├── storefront/
│   │   │   ├── ProductCard.tsx       # Card with dynamic price + micro-interactions
│   │   │   ├── PriceDisplay.tsx      # ★ Price + pulsing explanation badge
│   │   │   ├── PriceExplanationTooltip.tsx
│   │   │   ├── CartDrawer.tsx        # Slide-in cart with animations
│   │   │   ├── ProductGrid.tsx       # Grid with skeleton loaders
│   │   │   └── RecommendationRail.tsx
│   │   │
│   │   └── dashboard/
│   │       ├── MetricCard.tsx
│   │       ├── LatencyChart.tsx      # Real-time p99 latency graph
│   │       ├── ABTestPanel.tsx       # Live A/B test comparison
│   │       ├── RevenueChart.tsx
│   │       └── FairnessAudit.tsx
│   │
│   ├── hooks/
│   │   ├── useEventTracking.ts       # Fires clickstream events to backend
│   │   ├── useDynamicPrice.ts        # Polls/SSE for live price updates
│   │   ├── useRecommendations.ts
│   │   └── useABTest.ts
│   │
│   ├── lib/
│   │   ├── api.ts                    # Typed API client
│   │   ├── analytics.ts              # Client-side event batching
│   │   └── constants.ts
│   │
│   └── types/
│       ├── product.ts
│       ├── pricing.ts
│       └── events.ts
│
└── infra/
    ├── redis/
    │   └── redis.conf                # Redis Streams + feature store config
    └── nginx/
        └── nginx.conf                # Reverse proxy, gzip, headers
```
