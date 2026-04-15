"use client";
// hooks/useLoyalty.ts — Fetches and caches loyalty data for the current user

import { useEffect, useState, useCallback } from "react";
import { fetchMyPoints, fetchMyActivity } from "@/lib/loyalty-api";
import type { PointsBalance, ActivityFeed } from "@/types";

interface UseLoyaltyOptions {
  token: string | null;       // JWT — null = not logged in
  sessionId?: string;         // adds real-time session points to balance
  autoRefreshMs?: number;     // default 30s
}

interface UseLoyaltyReturn {
  balance: PointsBalance | null;
  activity: ActivityFeed | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function useLoyalty({
  token,
  sessionId,
  autoRefreshMs = 30_000,
}: UseLoyaltyOptions): UseLoyaltyReturn {
  const [balance, setBalance]   = useState<PointsBalance | null>(null);
  const [activity, setActivity] = useState<ActivityFeed | null>(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);

  const fetch_ = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const [bal, act] = await Promise.all([
        fetchMyPoints(token, sessionId),
        fetchMyActivity(token, 1, 10),
      ]);
      setBalance(bal);
      setActivity(act);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load loyalty data");
    } finally {
      setLoading(false);
    }
  }, [token, sessionId]);

  useEffect(() => {
    fetch_();
    if (!token) return;
    const t = setInterval(fetch_, autoRefreshMs);
    return () => clearInterval(t);
  }, [fetch_, autoRefreshMs, token]);

  return { balance, activity, loading, error, refresh: fetch_ };
}