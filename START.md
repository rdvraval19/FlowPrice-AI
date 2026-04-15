# FlowPriceAI — Complete Startup Guide
## Deadline: Tomorrow. Follow these steps exactly.

---

## STEP 0 — Prerequisites (one-time)

```powershell
# Install Python deps
cd pricing-engine\backend
pip install -r requirements.txt

# Install torch separately (CPU-only, smaller download)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install pandas + pyarrow for the seeder
pip install pandas pyarrow

# Install Node deps
cd ..\frontend
npm install
```

---

## STEP 1 — Start Redis

```powershell
# Option A: Docker (recommended)
docker run -d -p 6379:6379 --name flowprice-redis redis:7-alpine

# Option B: Windows native
# Download from https://github.com/tporadowski/redis/releases
# Then: redis-server

# Verify
redis-cli ping   # → PONG
```

---

## STEP 2 — Seed All Organizer Data

Sample Data by Judges - https://drive.google.com/drive/folders/1LBtsip0hcXfn-WTJUV5AZ-1pco4kPSPD

```powershell
cd pricing-engine

# FULL SEED (you have all 4 parquet files — use this):
python scripts/seed_from_organizer_data.py --data-dir C:\path\to\parquets --clickstream-limit 100000

# QUICK SEED (instant, no parquet needed — use if demo is in < 1 hour):
python scripts/seed_from_organizer_data.py --ab-seed-only

# PARTIAL SEED (you have 3 files, not clickstream):
python scripts/seed_from_organizer_data.py --data-dir C:\path\to\parquets --skip-clickstream
```

---

## STEP 3 — Start Backend

```powershell
cd pricing-engine\backend
python -m uvicorn app.main:app --reload --port 8000
```

Look for:
```
✅  Redis connected: redis://localhost:6379/0
✅  Background stream consumer started
INFO:     Uvicorn running on http://127.0.0.1:8000
```

---

## STEP 4 — Start Frontend

```powershell
# New terminal
cd pricing-engine\frontend
npm run dev
```

---

## STEP 5 — Verify Everything Works

```powershell
# Backend health
curl http://localhost:8000/health

# Evaluation summary (the judge scorecard — print this out)
curl http://localhost:8000/api/v1/evaluation/summary

# NDCG score
curl http://localhost:8000/api/v1/evaluation/ndcg

# Revenue uplift
curl http://localhost:8000/api/v1/evaluation/revenue-uplift
```

---

## Access Points

| URL | What it is |
|-----|-----------|
| http://localhost:3000 | Persona login (start here for demo) |
| http://localhost:3000/storefront | Live dynamic pricing storefront |
| http://localhost:3000/dashboard | Judge's dashboard |
| http://localhost:8000/docs | FastAPI Swagger — all 30+ endpoints |
| http://localhost:8000/api/v1/evaluation/summary | **All 5 evaluation criteria in one JSON** |

---

## Demo Script (2-minute judge walkthrough)

1. **Open login page** → explain cold-start solved by persona seeding
2. **Click "Deal Seeker"** → show seeding overlay → arrive at storefront
3. **Point at any price badge** → hover tooltip → explain transparency requirement
4. **Switch segment to "Loyal"** → watch ALL prices update → explain personalization
5. **Open dashboard** → point at p99 gauge (< 200ms) → explain latency requirement
6. **Click "Simulate Demand Spike"** → watch revenue ticker accelerate → watch event stream
7. **Point at A/B chart** → highlight "+X% conversion, p < 0.05" → explain statistical validity
8. **Click Fairness Score** → modal opens → explain what's excluded
9. **Run in browser console**: `fetch('http://localhost:8000/api/v1/evaluation/summary').then(r=>r.json()).then(console.log)`
   → Shows all 5 evaluation criteria live

---

## If Something Breaks

| Problem | Fix |
|---------|-----|
| `No module named 'redis'` | `pip install -r requirements.txt` |
| `torch not found` | App still works — recs use cold-start fallback |
| A/B shows $0.00 | `python scripts/seed_from_organizer_data.py --ab-seed-only` |
| Catalog empty | `python scripts/seed_from_organizer_data.py --data-dir .` |
| Port 8000 in use | `uvicorn app.main:app --port 8001` + update `.env.local` |
| Redis connection refused | `docker run -d -p 6379:6379 redis:7-alpine` |
