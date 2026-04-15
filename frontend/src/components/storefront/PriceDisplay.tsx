"use client";
import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { PricingResponse, PriceAdjustmentReason } from "@/types";
import { formatINR, usdToInr } from "@/lib/currency";
import { getDemandContext } from "@/lib/catalog";
import { clsx } from "clsx";

const REASON_META: Record<PriceAdjustmentReason, { label: string; type: "surge"|"discount"|"ai"|"neutral" }> = {
  high_demand:       { label: "High Demand",    type: "surge"    },
  limited_stock:     { label: "Limited Stock",  type: "surge"    },
  cap_hit:           { label: "Demand Cap",     type: "surge"    },
  low_demand:        { label: "Low Demand",     type: "discount" },
  flash_sale:        { label: "Flash Sale",     type: "discount" },
  loyalty_discount:  { label: "Member Price",   type: "ai"       },
  new_visitor_offer: { label: "Welcome Offer",  type: "ai"       },
  competitor_match:  { label: "Price Matched",  type: "discount" },
  base_price:        { label: "Standard",       type: "neutral"  },
  margin_floor_hit:  { label: "Best Price",     type: "neutral"  },
};

const TYPE_STYLES = {
  surge:    { text: "var(--red)",    bg: "var(--red-bg)",    dot: "#EF4444", border: "rgba(239,68,68,0.25)"    },
  discount: { text: "var(--green)",  bg: "var(--green-bg)",  dot: "#10B981", border: "rgba(16,185,129,0.25)"   },
  ai:       { text: "var(--purple)", bg: "var(--purple-bg)", dot: "#8B5CF6", border: "rgba(139,92,246,0.25)"   },
  neutral:  { text: "#64748B",       bg: "#F8FAFC",          dot: "#94A3B8", border: "rgba(148,163,184,0.25)"  },
};

interface PriceDisplayProps {
  pricing:    PricingResponse;
  productId:  string;
  flash?:     boolean;
  size?:      "sm"|"md"|"lg";
  showBadge?: boolean;
  className?: string;
}

export function PriceDisplay({ pricing, productId, flash=false, size="md", showBadge=true, className }: PriceDisplayProps) {
  const [tooltipOpen, setTooltipOpen] = useState(false);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (tooltipRef.current && !tooltipRef.current.contains(e.target as Node)) setTooltipOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const reason  = pricing.explanation.primary_reason;
  const meta    = REASON_META[reason] ?? REASON_META.base_price;
  const styles  = TYPE_STYLES[meta.type];
  const hasAdj  = Math.abs(pricing.discount_pct) > 0.5;
  const priceInr     = usdToInr(pricing.final_price);
  const basePriceInr = usdToInr(pricing.base_price);

  const sizeCls: Record<string, string> = {
    sm: "text-xl font-700", md: "text-2xl font-700", lg: "text-3xl font-800",
  };

  return (
    <div className={clsx("flex items-baseline gap-1.5 flex-wrap", className)}>
      {/* Animated price */}
      <motion.span
        key={pricing.final_price}
        initial={{ y: -4, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
        className={clsx("font-display tabular-nums", sizeCls[size])}
        style={{ color: hasAdj ? styles.text : "var(--text-primary)" }}
      >
        {formatINR(priceInr)}
      </motion.span>

      {/* Strike-through */}
      {hasAdj && pricing.final_price !== pricing.base_price && (
        <span className="text-sm line-through" style={{ color: "var(--text-muted)" }}>
          {formatINR(basePriceInr)}
        </span>
      )}

      {/* Discount pill */}
      {hasAdj && pricing.discount_pct > 0 && (
        <motion.span initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
          className="text-[10px] px-1.5 py-0.5 rounded-full font-mono font-600"
          style={{ background: "var(--green-bg)", color: "var(--green)" }}>
          -{pricing.discount_pct.toFixed(0)}%
        </motion.span>
      )}

      {/* AI transparency badge — purple = "AI working for you" */}
      {showBadge && hasAdj && (
        <div className="relative" ref={tooltipRef}>
          <button
            onClick={() => setTooltipOpen(o => !o)}
            onMouseEnter={() => setTooltipOpen(true)}
            onMouseLeave={() => setTooltipOpen(false)}
            className="ai-badge"
          >
            <span className="w-1.5 h-1.5 rounded-full animate-pulse-dot"
              style={{ background: styles.dot }} />
            {meta.label}
          </button>

          <AnimatePresence>
            {tooltipOpen && (
              <motion.div
                initial={{ opacity: 0, y: 6, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 4, scale: 0.97 }}
                transition={{ duration: 0.15 }}
                className="absolute z-50 bottom-full mb-2 left-1/2 -translate-x-1/2 w-72"
              >
                <div className="rounded-2xl p-4 shadow-xl"
                  style={{ background: "#fff", border: "1px solid var(--border-light)", boxShadow: "0 20px 60px rgba(0,0,0,0.12)" }}>
                  {/* Header */}
                  <div className="flex items-center gap-2 mb-2.5">
                    <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px]"
                      style={{ background: styles.bg, color: styles.text }}>✦</div>
                    <span className="text-sm font-display font-700" style={{ color: "var(--text-primary)" }}>
                      {meta.label}
                    </span>
                    <span className="ml-auto text-[10px] font-mono" style={{ color: "var(--green)" }}>✓ Fairness audited</span>
                  </div>

                  <p className="text-sm leading-relaxed mb-3" style={{ color: "var(--text-secondary)" }}>
                    {pricing.explanation.user_copy}
                  </p>

                  {/* Indian-market demand context */}
                  {(() => {
                    const ctx = getDemandContext(productId.includes("SKU") ? "Electronics" : "default");
                    return ctx ? (
                      <div className="mb-3 px-3 py-2 rounded-xl text-xs"
                        style={{ background: "var(--purple-bg)", color: "var(--purple)", border: "1px solid rgba(139,92,246,0.15)" }}>
                        ✦ {ctx}
                      </div>
                    ) : null;
                  })()}

                  {/* Stats row */}
                  <div className="grid grid-cols-3 gap-2 pt-2.5"
                    style={{ borderTop: "1px solid var(--border-light)" }}>
                    <div className="text-center">
                      <div className="text-sm font-mono font-700" style={{ color: "var(--text-primary)" }}>
                        {pricing.explanation.demand_velocity}
                      </div>
                      <div className="text-[9px]" style={{ color: "var(--text-muted)" }}>views/5min</div>
                    </div>
                    {pricing.explanation.inventory_level != null && (
                      <div className="text-center">
                        <div className="text-sm font-mono font-700"
                          style={{ color: pricing.explanation.inventory_level <= 10 ? "var(--red)" : "var(--text-primary)" }}>
                          {pricing.explanation.inventory_level}
                        </div>
                        <div className="text-[9px]" style={{ color: "var(--text-muted)" }}>in stock</div>
                      </div>
                    )}
                    <div className="text-center">
                      <div className="text-sm font-mono font-700" style={{ color: "var(--text-primary)" }}>
                        {Math.round(pricing.explanation.confidence * 100)}%
                      </div>
                      <div className="text-[9px]" style={{ color: "var(--text-muted)" }}>confidence</div>
                    </div>
                  </div>

                  {pricing.explanation.is_personalized && (
                    <div className="mt-2.5 text-[10px] flex items-center gap-1 font-mono"
                      style={{ color: "var(--purple)" }}>
                      ✦ Personalised for your membership tier
                    </div>
                  )}
                </div>
                {/* Arrow */}
                <div className="w-2.5 h-2.5 mx-auto -mt-1 rotate-45 rounded-sm"
                  style={{ background: "#fff", border: "1px solid var(--border-light)", borderTop: "none", borderLeft: "none" }} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}

export function PriceDisplaySkeleton({ size = "md" }: { size?: "sm"|"md"|"lg" }) {
  const w = { sm: "w-20", md: "w-28", lg: "w-36" };
  const h = { sm: "h-6", md: "h-8", lg: "h-10" };
  return (
    <div className="flex items-baseline gap-2">
      <div className={clsx("skeleton rounded", w[size], h[size])} />
      <div className="skeleton rounded w-12 h-4" />
    </div>
  );
}
