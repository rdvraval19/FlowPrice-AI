# FlowPrice AI: Real-Time Dynamic Pricing & Personalization Engine
[![Ask DeepWiki](https://devin.ai/assets/askdeepwiki.png)](https://deepwiki.com/rdvraval19/FlowPrice-AI)

FlowPrice AI is a full-stack dynamic pricing and recommendation engine designed for e-commerce platforms. It processes real-time behavioral signals to personalize user experiences, optimize pricing strategies, and drive revenue uplift, all while maintaining sub-200ms p99 latency.

The system features a consumer-facing storefront that showcases dynamic prices with transparency explanations, and an administrative dashboard for monitoring latency, A/B tests, revenue, and system health.

## Core Features

*   **Real-Time Dynamic Pricing:** Adjusts prices based on a weighted model of demand velocity, inventory scarcity, competitor data, and user segment. Includes business rule enforcement for margin floors and surge caps.
*   **Hybrid Recommendation Engine:** Combines a session-aware GRU4Rec model (PyTorch-based) for warm sessions with contextual, popularity-based strategies for cold-start users, ensuring relevant recommendations for everyone.
*   **High-Performance Event Ingestion:** A fully asynchronous FastAPI endpoint writes behavioral events (views, cart adds, purchases) to Redis Streams with a target server-side latency of less than 15ms.
*   **A/B Testing Framework:** Built-in support for running, monitoring, and analyzing experiments with deterministic, hash-based user bucketing and live statistical significance calculations.
*   **Vendor & Loyalty Platform:** A vendor-facing panel allows for the creation of discounts, coupon codes, and sponsored product placements. A points-based loyalty system rewards user activity and provides tiered benefits.
*   **Administrative Dashboard:** A Next.js dashboard provides a real-time view of system health, including p99 latency gauges, live event streams, A/B test results, demand heatmaps, and fairness audits.
*   **System Safeguards:** A Redis-backed circuit breaker prevents catastrophic pricing errors by detecting anomalies and halting dynamic pricing if thresholds are breached.

## Technology Stack

| Area          | Technologies                                                                                             |
|---------------|----------------------------------------------------------------------------------------------------------|
| **Backend**   | **Python 3.11+**, **FastAPI**, **Redis** (Streams, Cache, Feature Store), **SQLAlchemy**, **scikit-learn** |
| **Frontend**  | **Next.js 14** (App Router), **TypeScript**, **Tailwind CSS**, **Zustand**, **Recharts**, **Framer Motion**    |
| **Infra**     | **Docker**, **Docker Compose**                                                                           |

## Getting Started

The fastest way to run the full application stack (backend, frontend, Redis) is with Docker Compose.

### Prerequisites

*   Docker & Docker Compose
*   Python 3.11+ (for running scripts)
*   Node.js 18+

### 1. Run with Docker

From the root of the repository, start all services:

```bash
docker compose -f infra/docker/docker-compose.yml up --build
```

### 2. Seed Initial Data

To populate the dashboard with realistic A/B test data, run the seeder script. This command injects pre-calculated, statistically significant results directly into Redis without needing the large `clickstream.parquet` file.

```bash
# In a new terminal, from the repository root
python scripts/seed_from_organizer_data.py --ab-seed-only
```

### 3. Access the Application

*   **Persona Login:** [http://localhost:3000](http://localhost:3000)
*   **Storefront:** [http://localhost:3000/storefront](http://localhost:3000/storefront)
*   **Admin Dashboard:** [http://localhost:3000/dashboard](http://localhost:3000/dashboard)
*   **Backend API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

## Project Structure

The repository is structured as a monorepo with distinct `frontend`, `backend`, and `infra` directories.

```
flowprice-ai/
├── frontend/                          # Next.js 14 App Router + Tailwind CSS
│   ├── src/
│   │   ├── app/
│   │   │   ├── storefront/            # Consumer-facing e-commerce UI
│   │   │   ├── dashboard/             # Admin/Judge's monitoring dashboard
│   │   │   └── vendor/                # Vendor panel for managing promotions
│   │   ├── components/
│   │   │   ├── storefront/            # Product cards, price displays, recommendations
│   │   │   └── dashboard/             # Latency gauges, A/B charts, live streams
│   │   ├── hooks/                     # Custom hooks for pricing, events, etc.
│   │   └── store/                     # Zustand for global session management
│
├── backend/                           # FastAPI (async Python 3.11+)
│   ├── app/
│   │   ├── main.py                    # FastAPI app factory and middleware
│   │   ├── api/v1/
│   │   │   └── endpoints/
│   │   │       ├── events.py          # Real-time event ingestion (Redis Streams)
│   │   │       ├── pricing.py         # Dynamic pricing endpoint
│   │   │       ├── recommendations.py # Personalization endpoint
│   │   │       ├── experiments.py     # A/B testing management
│   │   │       └── evaluation.py      # Endpoints for hackathon evaluation criteria
│   │   ├── core/
│   │   │   ├── redis_client.py        # Redis connection pool and stream helpers
│   │   │   └── config.py              # Pydantic settings for configuration
│   │   ├── services/
│   │   │   ├── pricing/
│   │   │   │   ├── engine.py          # Orchestrates pricing logic
│   │   │   │   ├── demand_model.py    # Computes scores from velocity & scarcity
│   │   │   │   ├── business_rules.py  # Enforces margin floors and surge caps
│   │   │   │   └── circuit_breaker.py # Safety valve to prevent extreme prices
│   │   │   ├── recommendations/
│   │   │   │   ├── engine.py          # Hybrid recommendation orchestrator
│   │   │   │   └── session_model.py   # GRU4Rec model inference
│   │   │   └── events/
│   │   │       ├── ingestion.py       # Handles event validation and streaming
│   │   │       └── feature_compute.py # Calculates session scores and intent
│   │   └── tests/
│   │       ├── unit/                  # Tests for individual services
│   │       └── integration/           # Tests for API endpoints and data flow
│
├── infra/
│   ├── docker/
│   │   ├── Dockerfile.backend
│   │   ├── Dockerfile.frontend
│   │   └── docker-compose.yml         # Full stack definition for all services
│   └── redis/
│       └── redis.conf                 # Redis configuration for streams and memory
│
└── scripts/
    ├── seed_from_organizer_data.py    # Populates Redis from Parquet datasets
    └── simulate_traffic.py            # Generates load to test latency and demand
