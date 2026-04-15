// lib/loyalty-api.ts — Typed API client for Phase 4 loyalty endpoints

import type { ActivityFeed, PointsBalance, TierInfo } from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function authHeaders(token: string | null): HeadersInit {
  return token
    ? { "Content-Type": "application/json", Authorization: `Bearer ${token}` }
    : { "Content-Type": "application/json" };
}

// ── Points balance ────────────────────────────────────────────────────────────

export async function fetchMyPoints(
  token: string,
  sessionId?: string,
): Promise<PointsBalance> {
  const url = new URL(`${BASE}/api/v1/loyalty/points`);
  if (sessionId) url.searchParams.set("session_id", sessionId);
  const res = await fetch(url.toString(), {
    headers: authHeaders(token),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Points API ${res.status}`);
  return res.json();
}

// ── Activity feed ─────────────────────────────────────────────────────────────

export async function fetchMyActivity(
  token: string,
  page = 1,
  perPage = 20,
): Promise<ActivityFeed> {
  const url = new URL(`${BASE}/api/v1/loyalty/activity`);
  url.searchParams.set("page", String(page));
  url.searchParams.set("per_page", String(perPage));
  const res = await fetch(url.toString(), {
    headers: authHeaders(token),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Activity API ${res.status}`);
  return res.json();
}

// ── Tier info (public) ────────────────────────────────────────────────────────

export async function fetchTiers(): Promise<{ tiers: TierInfo[] }> {
  const res = await fetch(`${BASE}/api/v1/loyalty/tiers`, { cache: "force-cache" });
  if (!res.ok) throw new Error("Tiers API error");
  return res.json();
}

// ── Leaderboard (vendor) ──────────────────────────────────────────────────────

export async function fetchLeaderboard(token: string, topK = 10) {
  const url = new URL(`${BASE}/api/v1/loyalty/leaderboard`);
  url.searchParams.set("top_k", String(topK));
  const res = await fetch(url.toString(), {
    headers: authHeaders(token),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Leaderboard API ${res.status}`);
  return res.json();
}