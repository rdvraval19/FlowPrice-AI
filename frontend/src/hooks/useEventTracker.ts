"use client";
import { useCallback, useRef } from "react";
import { ingestEvent } from "@/lib/api-client";
import { useSessionStore } from "@/store/session";

export function useEventTracker() {
  const { sessionId, userSegment, incrementEvents } = useSessionStore();
  const queueRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const track = useCallback(
    (eventType: string, payload: Record<string, unknown> = {}) => {
      const event = {
        session_id: sessionId,
        event_type: eventType,
        timestamp_ms: Date.now(),
        device_type: "desktop",
        user_segment: userSegment,
        ...payload,
      };

      incrementEvents();

      // Debounce rapid-fire scroll/hover events
      if (eventType === "page_view" || eventType === "image_zoom") {
        if (queueRef.current) clearTimeout(queueRef.current);
        queueRef.current = setTimeout(() => ingestEvent(event), 300);
      } else {
        ingestEvent(event);
      }
    },
    [sessionId, userSegment, incrementEvents]
  );

  const trackProductView = useCallback(
    (productId: string, category: string, priceShown: number, basePrice: number) =>
      track("product_view", {
        product: { product_id: productId, category, price_shown: priceShown, base_price: basePrice },
      }),
    [track]
  );

  const trackCartAdd = useCallback(
    (productId: string, category: string, priceShown: number, basePrice: number) =>
      track("cart_add", {
        product: { product_id: productId, category, price_shown: priceShown, base_price: basePrice },
      }),
    [track]
  );

  const trackSearch = useCallback(
    (query: string, resultCount: number) =>
      track("search", { search: { query, result_count: resultCount, filters_applied: [] } }),
    [track]
  );

  return { track, trackProductView, trackCartAdd, trackSearch };
}
