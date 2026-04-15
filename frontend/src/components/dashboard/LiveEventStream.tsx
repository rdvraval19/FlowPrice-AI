"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { StreamEvent } from "@/types";
import { clsx } from "clsx";

const API_BASE =
  typeof window !== "undefined"
    ? process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
    : "http://localhost:8000";

const EVENT_COLORS: Record<string, string> = {
  product_view:   "text-blue-400",
  cart_add:       "text-amber-400",
  purchase:       "text-emerald-400",
  checkout_start: "text-orange-400",
  search:         "text-purple-400",
  page_view:      "text-zinc-500",
  cart_remove:    "text-red-400",
  wishlist_add:   "text-pink-400",
};

const EVENT_ICONS: Record<string, string> = {
  product_view:   "👁",
  cart_add:       "◻+",
  purchase:       "✓",
  checkout_start: "→",
  search:         "◎",
  page_view:      "·",
  cart_remove:    "◻-",
  wishlist_add:   "♡",
};

const SEGMENT_BADGE: Record<string, { bg: string; text: string }> = {
  loyalty:         { bg: "bg-amber-500/20",   text: "text-amber-400" },
  high_value:      { bg: "bg-emerald-500/20", text: "text-emerald-400" },
  new_visitor:     { bg: "bg-blue-500/20",    text: "text-blue-400" },
  price_sensitive: { bg: "bg-orange-500/20",  text: "text-orange-400" },
  returning:       { bg: "bg-zinc-700",       text: "text-zinc-400" },
  new_user:        { bg: "bg-blue-500/20",    text: "text-blue-400" },
  loyal:           { bg: "bg-amber-500/20",   text: "text-amber-400" },
};

// Demo events shown when backend is offline — so dashboard is never blank
const DEMO_EVENTS: Omit<StreamEvent, "id">[] = [
  { session_id: "demo_a1b2c3...", event_type: "product_view",   timestamp_ms: Date.now(), device_type: "mobile",  user_segment: "high_value",      category: "Electronics",    price_shown: 89.99 },
  { session_id: "demo_d4e5f6...", event_type: "cart_add",       timestamp_ms: Date.now(), device_type: "desktop", user_segment: "loyal",           category: "Gaming",         price_shown: 74.99 },
  { session_id: "demo_g7h8i9...", event_type: "purchase",       timestamp_ms: Date.now(), device_type: "mobile",  user_segment: "returning",       category: "Cameras",        price_shown: 599.99 },
  { session_id: "demo_j1k2l3...", event_type: "checkout_start", timestamp_ms: Date.now(), device_type: "tablet",  user_segment: "price_sensitive", category: "Cookware",       price_shown: 129.99 },
  { session_id: "demo_m4n5o6...", event_type: "product_view",   timestamp_ms: Date.now(), device_type: "desktop", user_segment: "new_user",        category: "Beauty & Health",price_shown: 29.99 },
  { session_id: "demo_p7q8r9...", event_type: "wishlist_add",   timestamp_ms: Date.now(), device_type: "mobile",  user_segment: "high_value",      category: "Clothing",       price_shown: 54.99 },
];

function makeDemoEvent(): StreamEvent {
  const base = DEMO_EVENTS[Math.floor(Math.random() * DEMO_EVENTS.length)];
  return {
    ...base,
    id: Math.random().toString(36).slice(2),
    timestamp_ms: Date.now(),
  };
}

type ConnectionState = "connecting" | "live" | "demo" | "error";

export function LiveEventStream() {
  const [events, setEvents]       = useState<StreamEvent[]>([]);
  const [connState, setConnState] = useState<ConnectionState>("connecting");
  const [totalSeen, setTotalSeen] = useState(0);
  const esRef        = useRef<EventSource | null>(null);
  const demoRef      = useRef<ReturnType<typeof setInterval> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const retryCount   = useRef(0);
  const retryTimer   = useRef<ReturnType<typeof setTimeout> | null>(null);

  const pushEvent = useCallback((event: StreamEvent) => {
    setEvents((prev) => [event, ...prev].slice(0, 50));
    setTotalSeen((n) => n + 1);
    if (containerRef.current) containerRef.current.scrollTop = 0;
  }, []);

  // Demo mode: simulate events when backend is offline
  const startDemoMode = useCallback(() => {
    if (demoRef.current) return; // already running
    setConnState("demo");
    // Seed with a few events immediately
    for (let i = 0; i < 4; i++) {
      setTimeout(() => pushEvent(makeDemoEvent()), i * 300);
    }
    // Then trickle in events
    demoRef.current = setInterval(() => {
      pushEvent(makeDemoEvent());
    }, 2500 + Math.random() * 2000);
  }, [pushEvent]);

  const stopDemoMode = useCallback(() => {
    if (demoRef.current) {
      clearInterval(demoRef.current);
      demoRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    // Clean up existing connection
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    const url = `${API_BASE}/api/v1/events/stream/live`;
    let connected = false;

    try {
      const es = new EventSource(url);
      esRef.current = es;

      es.onopen = () => {
        connected = true;
        retryCount.current = 0;
        setConnState("live");
        stopDemoMode(); // stop demo when real stream arrives
      };

      es.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === "connected" || data.type === "error") return;

          const event: StreamEvent = {
            id:           data.id || String(Date.now()),
            session_id:   data.session_id || "unknown",
            event_type:   data.event_type || "unknown",
            timestamp_ms: data.timestamp_ms,
            device_type:  data.device_type || "desktop",
            user_segment: data.user_segment || "unknown",
            product_id:   data.product_id,
            category:     data.category,
            price_shown:  data.price_shown,
          };

          pushEvent(event);
        } catch {
          // ignore parse errors
        }
      };

      es.onerror = () => {
        es.close();
        esRef.current = null;
        setConnState("error");

        // Start demo mode if not already running so panel isn't blank
        if (!connected) {
          startDemoMode();
        }

        // Exponential back-off retry: 3s → 6s → 12s → max 30s
        retryCount.current += 1;
        const delay = Math.min(3000 * Math.pow(1.5, retryCount.current - 1), 30000);
        retryTimer.current = setTimeout(connect, delay);
      };
    } catch {
      // EventSource constructor failed (e.g., invalid URL in SSR)
      startDemoMode();
    }
  }, [pushEvent, startDemoMode, stopDemoMode]);

  useEffect(() => {
    // Small delay so Next.js hydration finishes first
    const t = setTimeout(connect, 500);
    return () => {
      clearTimeout(t);
      if (retryTimer.current) clearTimeout(retryTimer.current);
      if (esRef.current) esRef.current.close();
      stopDemoMode();
    };
  }, [connect, stopDemoMode]);

  const statusConfig = {
    connecting: { dot: "bg-zinc-600",              pill: "bg-zinc-800 border-zinc-700 text-zinc-500",              label: "Connecting…" },
    live:       { dot: "bg-emerald-400 animate-pulse", pill: "bg-emerald-500/10 border-emerald-500/20 text-emerald-400", label: "LIVE" },
    demo:       { dot: "bg-amber-400 animate-pulse",   pill: "bg-amber-500/10 border-amber-500/20 text-amber-400",      label: "DEMO" },
    error:      { dot: "bg-red-400",               pill: "bg-red-500/10 border-red-500/20 text-red-400",            label: "Reconnecting…" },
  }[connState];

  return (
    <div className="p-5 bg-[#111118] border border-[#1e1e2a] rounded-2xl flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-display text-sm font-700 text-white">Live Event Stream</h3>
          <p className="text-zinc-600 text-[11px] font-mono mt-0.5">
            {totalSeen.toLocaleString()} total · {connState === "demo" ? "simulated" : "real"} events
          </p>
        </div>
        <div className={clsx(
          "flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-mono border",
          statusConfig.pill,
        )}>
          <span className={clsx("w-1.5 h-1.5 rounded-full", statusConfig.dot)} />
          {statusConfig.label}
        </div>
      </div>

      {/* Stream */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto space-y-1.5 min-h-0"
        style={{ maxHeight: 340 }}
      >
        <AnimatePresence initial={false}>
          {events.length === 0 ? (
            <div className="text-center py-8 text-zinc-700 text-xs font-mono">
              Waiting for events…
            </div>
          ) : (
            events.map((event) => {
              const color = EVENT_COLORS[event.event_type] || "text-zinc-500";
              const icon  = EVENT_ICONS[event.event_type]  || "·";
              const badge = SEGMENT_BADGE[event.user_segment] || { bg: "bg-zinc-800", text: "text-zinc-500" };

              return (
                <motion.div
                  key={event.id}
                  initial={{ opacity: 0, x: -8, height: 0 }}
                  animate={{ opacity: 1, x: 0, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.18 }}
                  className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-[#0d0d14] border border-[#181820] text-xs"
                >
                  <span className={clsx("font-mono text-sm w-5 text-center flex-shrink-0", color)}>
                    {icon}
                  </span>
                  <span className={clsx("font-mono font-500 flex-shrink-0 w-24 truncate", color)}>
                    {event.event_type.replace(/_/g, " ")}
                  </span>
                  <span className="text-zinc-600 font-mono text-[10px] flex-shrink-0 w-20 truncate">
                    {event.session_id}
                  </span>
                  {event.category && (
                    <span className="text-zinc-600 text-[10px] hidden sm:block truncate max-w-[80px]">
                      {event.category}
                    </span>
                  )}
                  {event.price_shown != null && (
                    <span className="text-zinc-400 font-mono text-[10px] ml-auto flex-shrink-0">
                      ${Number(event.price_shown).toFixed(2)}
                    </span>
                  )}
                  <span className={clsx(
                    "px-1.5 py-0.5 rounded text-[9px] font-mono flex-shrink-0 ml-auto",
                    badge.bg, badge.text,
                  )}>
                    {event.user_segment}
                  </span>
                </motion.div>
              );
            })
          )}
        </AnimatePresence>
      </div>

      {/* Demo mode notice */}
      {connState === "demo" && (
        <p className="text-zinc-700 text-[10px] font-mono mt-2 text-center">
          Backend offline — showing simulated events. Start the server to see real data.
        </p>
      )}
    </div>
  );
}