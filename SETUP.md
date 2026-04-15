# 🚀 VELOCITY — Setup Guide & Known Hurdles

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.11+ | `python --version` |
| Node.js | 18+ | `node --version` |
| Redis | 7.x | `redis-server --version` |
| Docker (optional) | 24+ | `docker --version` |

---

## Option A — Docker Compose (Recommended, Fastest)

```bash
# 1. Clone / unzip the project
cd pricing-engine

# 2. Start all services (Redis + Backend + Frontend)
docker compose -f infra/docker/docker-compose.yml up --build

# ✅ Access points:
#   Storefront:  http://localhost:3000/storefront
#   Dashboard:   http://localhost:3000/dashboard
#   API docs:    http://localhost:8000/docs
#   Health:      http://localhost:8000/health
```

---

## Option B — Bare Metal (Faster iteration)

### Step 1 — Start Redis
```bash
# macOS
brew install redis && brew services start redis

# Ubuntu/Debian
sudo apt install redis-server && sudo systemctl start redis

# Windows (WSL2 recommended)
sudo service redis-server start

# Verify
redis-cli ping   # → PONG
```

### Step 2 — Backend
```bash
cd pricing-engine/backend

# Create virtualenv
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — defaults work for local dev, no changes needed

# Start the API server
uvicorn app.main:app --reload --port 8000

# ✅ API live at http://localhost:8000
# ✅ Swagger UI at http://localhost:8000/docs
```

### Step 3 — Frontend
```bash
cd pricing-engine/frontend

# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local
# NEXT_PUBLIC_API_URL=http://localhost:8000  (already set)

# Start dev server
npm run dev

# ✅ Storefront: http://localhost:3000/storefront
# ✅ Dashboard:  http://localhost:3000/dashboard
```

### Step 4 — Verify the system is working
```bash
# Hit the health endpoint
curl http://localhost:8000/health

# Fire a test event
curl -X POST http://localhost:8000/api/v1/events/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_test_abcdef1234567890",
    "event_type": "product_view",
    "timestamp_ms": '"$(date +%s000)"',
    "device_type": "desktop",
    "user_segment": "returning",
    "product": {
      "product_id": "prod_snk_001",
      "category": "sneakers",
      "price_shown": 129.99,
      "base_price": 149.99,
      "inventory_level": 12
    }
  }'

# Get a dynamic price
curl "http://localhost:8000/api/v1/pricing/prod_snk_001?session_id=sess_test_abcdef1234567890&user_segment=loyalty&base_price=149.99&cost_price=58.00&inventory_level=12"

# Run load test to validate p99 SLA
cd pricing-engine
python scripts/simulate_traffic.py --sessions 100 --rps 30
```

---

## ⚠️ Known Hurdles & How to Fix Them

### 1. PyTorch Installation (Most Common Issue)

**Problem:** `pip install torch` downloads ~2GB and may fail on slow connections or low-disk machines.

**Fix Options:**
```bash
# Option A: CPU-only torch (much smaller, fine for hackathon)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Option B: Skip torch entirely — the system falls back to random-weight GRU4Rec
# Comment out torch in requirements.txt and the engine still works with the
# contextual cold-start + trending fallback.

# Option C: Use the pre-built wheel matching your Python version
pip install torch==2.5.1+cpu -f https://download.pytorch.org/whl/torch_stable.html
```

**Why it still works without trained weights:** `SessionModelRegistry._bootstrap_random_model()`
creates a random-weight GRU4Rec at startup. The hybrid engine blends it with the
contextual cold-start source, so recommendations still function — just less accurate.

---

### 2. Redis Not Running / Connection Refused

**Symptom:** `redis.exceptions.ConnectionError: Error connecting to localhost:6379`

**Fix:**
```bash
# Check if Redis is running
redis-cli ping

# If not:
redis-server &         # Start in background
# OR via brew/apt as shown above
```

**Why it matters:** The entire event pipeline, feature store, and pricing cache
depend on Redis. The app will start but all API calls will return 503 until Redis is up.

---

### 3. CORS Errors (Frontend ↔ Backend)

**Symptom:** Browser console shows `CORS policy: No 'Access-Control-Allow-Origin'`

**Fix:** In `backend/.env`, ensure your frontend origin is listed:
```
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```
After changing, restart the backend. The CORS middleware reads this on startup.

---

### 4. SSE (Server-Sent Events) Blocked by Proxy/Nginx

**Symptom:** Dashboard live stream and price update stream don't receive events.

**Fix:** Add these headers to your reverse proxy config:
```nginx
proxy_set_header  Connection '';
proxy_http_version 1.1;
chunked_transfer_encoding on;
proxy_buffering off;
proxy_cache off;
```
The `X-Accel-Buffering: no` header is already set in all SSE endpoints to signal nginx.

---

### 5. `aiosqlite` / SQLAlchemy Version Conflicts

**Symptom:** `ImportError: cannot import name 'AsyncSession'`

**Fix:** Ensure you have SQLAlchemy 2.x (not 1.4):
```bash
pip install "sqlalchemy[asyncio]>=2.0" aiosqlite
```
SQLAlchemy 1.4 had different async APIs. The requirements.txt pins `sqlalchemy==2.0.36`.

---

### 6. Next.js `useSessionStore` Hydration Error

**Symptom:** `Hydration failed because the initial UI does not match` in browser console.

**Root cause:** Zustand reads `localStorage` in the store initializer, which differs
between server (no localStorage) and client.

**Fix already applied:** The session store uses a lazy initializer that only reads
`localStorage` in `typeof window !== "undefined"` branches. If you still see it,
add `'use client'` to the top of any component using the store.

---

### 7. Docker: `permission denied` on Redis data volume

**Symptom:** Redis container exits with `Fatal error, can't open config file`

**Fix:**
```bash
# Remove stale volume and recreate
docker compose -f infra/docker/docker-compose.yml down -v
docker compose -f infra/docker/docker-compose.yml up --build
```

---

### 8. Port Conflicts

Default ports used:
| Service | Port |
|---------|------|
| Frontend (Next.js) | 3000 |
| Backend (FastAPI) | 8000 |
| Redis | 6379 |

Change in `docker-compose.yml` or pass `--port XXXX` to uvicorn/next.

---

## 🔌 API Integration Notes

### What's Real vs Simulated

| Feature | Status | Notes |
|---------|--------|-------|
| Event ingestion → Redis Streams | ✅ Real | Full pipeline |
| Feature store (Redis) | ✅ Real | Live reads/writes |
| Demand velocity (Redis ZSet) | ✅ Real | 5-min rolling window |
| Business rules enforcement | ✅ Real | Margin floor, caps, fairness |
| Price explanation | ✅ Real | Signal-driven copy |
| A/B assignment (SHA-256) | ✅ Real | Deterministic |
| GRU4Rec model | ⚠️ Random weights | Needs training data |
| Collaborative filtering | ⚠️ Not implemented | Replaced by cold-start |
| Competitor price data | ⚠️ Hardcoded | See integration below |
| A/B metrics (impressions/conv) | ⚠️ Empty until traffic | Run load test |

### Competitor Price Integration

In `services/pricing/demand_model.py`, the `competitor_price` parameter is passed
in from the API call. To wire in a real data source:

```python
# Option 1: SerpAPI / Google Shopping (real-time)
# GET https://serpapi.com/search?engine=google_shopping&q={product_name}
# Cost: ~$0.01 per call — cache aggressively

# Option 2: Oxylabs / Bright Data (e-commerce scraper)
# Scheduled batch job → writes to Redis → pricing engine reads cached value

# Option 3: Skrapp / Prisync (competitor pricing SaaS)
# Webhook-based — pushes updates to your competitor_price Redis key
```

The pricing engine already handles `competitor_price=None` gracefully (neutral signal).

### Payment / Checkout Integration

The cart drawer's "Checkout" button currently has no backend. To add Stripe:
```bash
npm install @stripe/stripe-js @stripe/react-stripe-js
pip install stripe
```
Wire the purchase event → `POST /api/v1/events/ingest` with `event_type: "purchase"`
to feed the recommendation model and A/B conversion tracking.

### Email / Notification on Price Drop

When `demand_score` drops below `LOW_DEMAND_THRESHOLD`, you can trigger an email:
```python
# In services/events/consumer.py _process_stream_message():
if event_type == "product_view" and demand_velocity < settings.LOW_DEMAND_THRESHOLD:
    await send_price_alert_email(product_id, session_id)
```
Use SendGrid (`pip install sendgrid`) or Resend (`pip install resend`).

---

## Running Tests

```bash
cd pricing-engine/backend
source .venv/bin/activate

# Unit tests (no Redis needed)
pytest tests/unit/ -v

# Integration tests (requires Redis)
pytest tests/integration/ -v

# All tests with coverage
pytest --cov=app --cov-report=term-missing

# Load test (requires running backend + Redis)
python ../scripts/simulate_traffic.py --sessions 200 --rps 50
```

---

## Production Checklist

- [ ] Change `SECRET_KEY` in `.env`
- [ ] Change `AB_SALT` in `.env`
- [ ] Set `ENVIRONMENT=production` (disables Swagger UI)
- [ ] Set `DEBUG=false`
- [ ] Switch `DATABASE_URL` to PostgreSQL
- [ ] Set `requirepass` in `infra/redis/redis.conf`
- [ ] Add rate limiting (nginx or `slowapi`)
- [ ] Set up Redis persistence (`appendonly yes`)
- [ ] Configure `MAX_SURGE_PCT` per legal requirements in your jurisdiction
- [ ] Run `scripts/run_fairness_audit.py` before launch
