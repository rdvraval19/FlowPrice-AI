"use client";
import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { getMockProductImage } from "@/lib/images";
import { formatINR, usdToInr } from "@/lib/currency";
import { getSSEUrl } from "@/lib/api-client";
import { clsx } from "clsx";

// ── Types ─────────────────────────────────────────────────────────────────────
interface RecItem {
  product_id: string;
  score:      number;
  source:     "session_intent" | "long_term_history" | "cold_start" | "trending";
  category:   string;
  brand:      string;
  price:      number;  // USD
  rank:       number;
}

interface SliderProps {
  sessionId:  string;
  userId?:    string;
  title?:     string;
  /** If provided, triggers the "Milk & Cookies" effect on item view/add */
  lastViewedProductId?: string;
  lastViewedCategory?:  string;
}

// Source label + color map
const SOURCE_META: Record<string, { label: string; color: string; bg: string }> = {
  session_intent:    { label: "Session Intent",  color: "var(--purple)", bg: "var(--purple-bg)" },
  long_term_history: { label: "Your History",    color: "var(--indigo)", bg: "var(--indigo-light)" },
  cold_start:        { label: "Trending",         color: "#F97316",      bg: "#FFF7ED" },
  trending:          { label: "Popular",          color: "#64748B",      bg: "#F8FAFC" },
};

// ── Single recommendation card in the slider ──────────────────────────────────
function RecCard({ item, isNew }: { item: RecItem; isNew: boolean }) {
  const meta    = SOURCE_META[item.source] || SOURCE_META.trending;
  const imgSrc  = getMockProductImage(item.product_id, item.category);
  const priceInr = usdToInr(item.price || 50);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 32, scale: 0.96 }}
      animate={{ opacity: 1, x: 0,  scale: 1 }}
      exit={{ opacity: 0, x: -24, scale: 0.96 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className={clsx(
        "flex-shrink-0 w-40 rounded-2xl overflow-hidden cursor-pointer transition-all",
        "hover:shadow-lg hover:-translate-y-1",
        isNew && "ring-2 ring-offset-1 rec-slide-in"
      )}
      style={{
        border: isNew ? `2px solid var(--purple)` : "1px solid var(--border-light)",
        background: "#FFFFFF",
        ringColor: "var(--purple)",
      }}
    >
      {/* Image */}
      <div className="relative overflow-hidden" style={{ aspectRatio: "1/1", background: "#F8FAFC" }}>
        <img src={imgSrc} alt={item.product_id}
          className="w-full h-full object-cover transition-transform duration-500 hover:scale-110"
          loading="lazy" />
        {isNew && (
          <div className="absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded-full text-[9px] font-700"
            style={{ background: "var(--purple)", color: "#fff" }}>
            NEW
          </div>
        )}
      </div>

      {/* Body */}
      <div className="p-2.5">
        <p className="text-[10px] font-mono truncate mb-0.5" style={{ color: "var(--text-muted)" }}>
          {item.brand || item.category}
        </p>
        <p className="text-xs font-display font-700 truncate" style={{ color: "var(--text-primary)" }}>
          {item.product_id.replace(/^(SKU|PROD|prod)_?/i, "").replace(/_/g, " ")}
        </p>
        <div className="flex items-center justify-between mt-1.5">
          <span className="text-xs font-display font-700" style={{ color: "var(--indigo)" }}>
            {priceInr > 83 ? formatINR(priceInr) : "—"}
          </span>
          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-full"
            style={{ background: meta.bg, color: meta.color }}>
            {meta.label}
          </span>
        </div>
      </div>
    </motion.div>
  );
}

// ── Main Slider Component ─────────────────────────────────────────────────────
export function RecommendationSlider({
  sessionId, userId, title = "Recommended for You",
  lastViewedProductId, lastViewedCategory,
}: SliderProps) {
  const [items, setItems]           = useState<RecItem[]>([]);
  const [loading, setLoading]       = useState(true);
  const [newItemIds, setNewItemIds] = useState<Set<string>>(new Set());
  const [trigger, setTrigger]       = useState<string | null>(null);
  const scrollRef                   = useRef<HTMLDivElement>(null);
  const prevItemsRef                = useRef<Set<string>>(new Set());

  // Fetch recommendations from the hybrid engine API
  const fetchRecs = async (force = false) => {
    if (!sessionId) return;
    const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    try {
      const url = new URL(`${BASE}/api/v1/recommendations/${sessionId}`);
      if (userId) url.searchParams.set("user_id", userId);
      url.searchParams.set("top_k", "10");

      const res  = await fetch(url.toString(), { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      const newItems: RecItem[] = (data.items || []).map((i: any) => ({
        product_id: i.product_id,
        score:      i.score,
        source:     i.source,
        category:   i.category || "Electronics",
        brand:      i.brand    || "FlowBrand",
        price:      i.price    || 50,
        rank:       i.rank,
      }));

      // Detect truly new items for the "slide-in" animation
      const prevIds    = prevItemsRef.current;
      const newlyAdded = new Set(newItems.filter(i => !prevIds.has(i.product_id)).map(i => i.product_id));
      prevItemsRef.current = new Set(newItems.map(i => i.product_id));

      if (newlyAdded.size > 0) {
        setNewItemIds(newlyAdded);
        setTimeout(() => setNewItemIds(new Set()), 3000);
        // Auto-scroll to start when new items arrive
        scrollRef.current?.scrollTo({ left: 0, behavior: "smooth" });
      }

      setItems(newItems);
    } catch { /* silent fail */ }
    finally   { setLoading(false); }
  };

  // Initial load
  useEffect(() => { fetchRecs(); }, [sessionId]);

  // The "Milk & Cookies" trigger: when the viewed product changes, refresh recs
  useEffect(() => {
    if (!lastViewedProductId) return;
    const newTrigger = `${lastViewedProductId}:${lastViewedCategory}`;
    if (newTrigger !== trigger) {
      setTrigger(newTrigger);
      // Small delay so the event has time to reach the backend
      setTimeout(() => fetchRecs(true), 800);
    }
  }, [lastViewedProductId, lastViewedCategory]);

  // Periodic refresh every 20s
  useEffect(() => {
    const t = setInterval(() => fetchRecs(), 20000);
    return () => clearInterval(t);
  }, [sessionId]);

  if (loading) {
    return (
      <div>
        <div className="skeleton h-5 w-48 rounded mb-4" />
        <div className="flex gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex-shrink-0 w-40 rounded-2xl overflow-hidden"
              style={{ border: "1px solid var(--border-light)" }}>
              <div className="skeleton" style={{ aspectRatio: "1/1" }} />
              <div className="p-2.5 space-y-1.5">
                <div className="skeleton h-3 w-20 rounded" />
                <div className="skeleton h-4 w-full rounded" />
                <div className="skeleton h-3 w-16 rounded" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!items.length) return null;

  // Group by source for the header explanation
  const sessionCount  = items.filter(i => i.source === "session_intent").length;
  const historyCount  = items.filter(i => i.source === "long_term_history").length;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="font-display text-base font-700" style={{ color: "var(--text-primary)" }}>
            {lastViewedProductId ? "🍪 You might also like" : title}
          </h2>
          <p className="text-xs font-mono mt-0.5" style={{ color: "var(--text-muted)" }}>
            {lastViewedProductId
              ? `Customers who viewed this also bought • ${sessionCount} session matches`
              : `Hybrid engine • ${sessionCount} session + ${historyCount} history signals`
            }
          </p>
        </div>
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono"
          style={{ background: "var(--purple-bg)", color: "var(--purple)", border: "1px solid rgba(139,92,246,0.2)" }}>
          ✦ AI-Powered
        </div>
      </div>

      {/* "Milk & Cookies" trigger banner */}
      <AnimatePresence>
        {lastViewedProductId && newItemIds.size > 0 && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-3 px-3 py-2 rounded-xl text-xs font-mono overflow-hidden"
            style={{ background: "var(--purple-bg)", color: "var(--purple)", border: "1px solid rgba(139,92,246,0.15)" }}>
            ✦ Session intent detected from {lastViewedCategory} — {newItemIds.size} new recommendations added
          </motion.div>
        )}
      </AnimatePresence>

      {/* Scrollable slider */}
      <div ref={scrollRef}
        className="flex gap-3 overflow-x-auto pb-2"
        style={{ scrollbarWidth: "none", WebkitScrollbar: { display: "none" } as any }}>
        <AnimatePresence mode="popLayout" initial={false}>
          {items.map(item => (
            <RecCard
              key={item.product_id}
              item={item}
              isNew={newItemIds.has(item.product_id)}
            />
          ))}
        </AnimatePresence>
      </div>

      {/* Source legend */}
      <div className="flex items-center gap-4 mt-3 flex-wrap">
        {Object.entries(SOURCE_META).map(([key, meta]) => {
          const count = items.filter(i => i.source === key).length;
          if (!count) return null;
          return (
            <div key={key} className="flex items-center gap-1.5 text-[10px] font-mono"
              style={{ color: "var(--text-muted)" }}>
              <div className="w-2 h-2 rounded-full" style={{ background: meta.color }} />
              {meta.label}: {count}
            </div>
          );
        })}
      </div>
    </div>
  );
}
