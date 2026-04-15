"use client";
// lib/api-client.ts — Typed fetch wrapper for all backend API calls

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Auth helper — attaches Bearer token if available ──────────────────────────

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("velocity_token");
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
}

// Generic authenticated fetch — use this for any protected endpoint
export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...authHeaders(),
      ...(init.headers as Record<string, string> || {}),
    },
    cache: "no-store",
  });
}

// ── Auth endpoints (Phase 1) ──────────────────────────────────────────────────

export async function registerUser(params: {
  email: string;
  password: string;
  role: "user" | "vendor";
}) {
  const res = await fetch(`${BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Register failed: ${res.status}`);
  }
  return res.json();
}

export async function loginUser(params: { email: string; password: string }) {
  const res = await fetch(`${BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Login failed: ${res.status}`);
  }
  return res.json() as Promise<{
    access_token: string;
    token_type: string;
    expires_in: number;
    role: "user" | "vendor";
    user_id: string;
  }>;
}

export async function fetchMe() {
  const res = await authFetch("/api/v1/auth/me");
  if (!res.ok) throw new Error("Not authenticated");
  return res.json();
}

// ── Catalog ───────────────────────────────────────────────────────────────────

export async function fetchCatalog(params: {
  category?: string;
  page?: number;
  perPage?: number;
}) {
  const url = new URL(`${BASE}/api/v1/catalog/`);
  if (params.category) url.searchParams.set("category", params.category);
  if (params.page)     url.searchParams.set("page", String(params.page));
  if (params.perPage)  url.searchParams.set("per_page", String(params.perPage));
  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error(`Catalog API ${res.status}`);
  return res.json();
}

export async function fetchCategories() {
  const res = await fetch(`${BASE}/api/v1/catalog/categories`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Categories API ${res.status}`);
  return res.json();
}

export async function fetchCompetitorPrice(skuId: string) {
  const res = await fetch(`${BASE}/api/v1/catalog/competitor/${skuId}`, { cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
}

// ── Pricing ───────────────────────────────────────────────────────────────────

export async function fetchPrice(params: {
  productId: string;
  sessionId: string;
  userSegment: string;
  basePrice: number;
  costPrice: number;
  inventoryLevel: number;
  competitorPrice?: number;
}) {
  const url = new URL(`${BASE}/api/v1/pricing/${params.productId}`);
  url.searchParams.set("session_id", params.sessionId);
  url.searchParams.set("user_segment", params.userSegment);
  url.searchParams.set("base_price", String(params.basePrice));
  url.searchParams.set("cost_price", String(params.costPrice));
  url.searchParams.set("inventory_level", String(params.inventoryLevel));
  if (params.competitorPrice)
    url.searchParams.set("competitor_price", String(params.competitorPrice));

  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error(`Pricing API ${res.status}`);
  return res.json();
}

export async function fetchBulkPrices(params: {
  sessionId: string;
  userSegment: string;
  products: Array<{
    product_id: string;
    base_price: number;
    cost_price: number;
    inventory_level: number;
    competitor_price?: number;
  }>;
}) {
  const res = await fetch(`${BASE}/api/v1/pricing/bulk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    body: JSON.stringify({
      session_id: params.sessionId,
      user_segment: params.userSegment,
      products: params.products,
    }),
  });
  if (!res.ok) throw new Error(`Bulk pricing API ${res.status}`);
  return res.json();
}

// ── Events ────────────────────────────────────────────────────────────────────

export async function ingestEvent(event: Record<string, unknown>) {
  try {
    await fetch(`${BASE}/api/v1/events/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event),
      keepalive: true,
    });
  } catch { /* never let analytics break the UI */ }
}

// ── Experiments ───────────────────────────────────────────────────────────────

export async function fetchExperiments() {
  const res = await fetch(`${BASE}/api/v1/experiments/dashboard/summary`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Experiments API error");
  return res.json();
}

// ── Metrics ───────────────────────────────────────────────────────────────────

export async function fetchLatencyMetrics() {
  const res = await fetch(`${BASE}/api/v1/events/metrics/latency`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Latency API error");
  return res.json();
}

export async function fetchStreamMetrics() {
  const res = await fetch(`${BASE}/api/v1/events/metrics`, { cache: "no-store" });
  if (!res.ok) throw new Error("Stream metrics error");
  return res.json();
}

// ── SSE ───────────────────────────────────────────────────────────────────────

export function getSSEUrl(path: string) {
  return `${BASE}${path}`;
}