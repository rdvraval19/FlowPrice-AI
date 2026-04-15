"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { PricingResponse } from "@/types";
import { fetchPrice, getSSEUrl } from "@/lib/api-client";

interface UseDynamicPriceOptions {
  productId: string;
  sessionId: string;
  userSegment: string;
  basePrice: number;
  costPrice: number;
  inventoryLevel: number;
  competitorPrice?: number;
  subscribeToUpdates?: boolean;
}

interface UseDynamicPriceResult {
  pricing: PricingResponse | null;
  loading: boolean;
  error: string | null;
  priceFlash: boolean; // true for 600ms when price updates
  refetch: () => void;
}

export function useDynamicPrice(opts: UseDynamicPriceOptions): UseDynamicPriceResult {
  const [pricing, setPricing] = useState<PricingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [priceFlash, setPriceFlash] = useState(false);
  const prevPriceRef = useRef<number | null>(null);

  const flash = useCallback(() => {
    setPriceFlash(true);
    setTimeout(() => setPriceFlash(false), 600);
  }, []);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchPrice(opts);
      if (prevPriceRef.current !== null && prevPriceRef.current !== data.final_price) {
        flash();
      }
      prevPriceRef.current = data.final_price;
      setPricing(data);
    } catch (e) {
      setError("Price unavailable");
      // Graceful fallback — show base price
      setPricing({
        product_id: opts.productId,
        session_id: opts.sessionId,
        final_price: opts.basePrice,
        base_price: opts.basePrice,
        discount_pct: 0,
        explanation: {
          primary_reason: "base_price",
          secondary_reasons: [],
          user_copy: "Standard pricing.",
          discount_pct: 0,
          demand_velocity: 0,
          inventory_level: opts.inventoryLevel,
          confidence: 1,
          is_personalized: false,
          fairness_checked: true,
        },
        variant_id: null,
        computed_in_ms: 0,
        cached: false,
      } as PricingResponse);
    } finally {
      setLoading(false);
    }
  }, [opts.productId, opts.sessionId, opts.userSegment, opts.basePrice]);

  useEffect(() => { load(); }, [load]);

  // SSE subscription for live price updates
  useEffect(() => {
    if (!opts.subscribeToUpdates || !opts.sessionId) return;

    const url = getSSEUrl(
      `/api/v1/pricing/stream/${opts.sessionId}?product_id=${opts.productId}&base_price=${opts.basePrice}&cost_price=${opts.costPrice}`
    );
    const es = new EventSource(url);

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === "price_update") {
          flash();
          setPricing((prev) =>
            prev
              ? {
                  ...prev,
                  final_price: data.final_price,
                  discount_pct: data.discount_pct,
                  explanation: {
                    ...prev.explanation,
                    primary_reason: data.reason,
                    user_copy: data.user_copy,
                    demand_velocity: data.demand_velocity,
                  },
                }
              : prev
          );
        }
      } catch {}
    };

    es.onerror = () => es.close();

    return () => es.close();
  }, [opts.subscribeToUpdates, opts.sessionId, opts.productId]);

  return { pricing, loading, error, priceFlash, refetch: load };
}
