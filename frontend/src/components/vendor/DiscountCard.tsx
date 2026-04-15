"use client";
// frontend/src/components/vendor/DiscountCard.tsx

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { clsx } from "clsx";
import { applyDiscount, removeDiscount, DiscountResponse } from "@/lib/vendor-api";

export function DiscountCard() {
  const [productId, setProductId]     = useState("");
  const [originalPrice, setOriginalPrice] = useState("");
  const [discountPct, setDiscountPct] = useState("");
  const [reason, setReason]           = useState("Weekend Sale");
  const [status, setStatus]           = useState<"idle"|"loading"|"success"|"error">("idle");
  const [result, setResult]           = useState<DiscountResponse | null>(null);
  const [error, setError]             = useState("");
  const [removing, setRemoving]       = useState(false);

  const handleApply = async () => {
    if (!productId || !originalPrice || !discountPct) return;
    setStatus("loading");
    setError("");
    try {
      const data = await applyDiscount(
        { product_id: productId, discount_pct: Number(discountPct), reason },
        Number(originalPrice)
      );
      setResult(data);
      setStatus("success");
    } catch (e: any) {
      setError(e.message);
      setStatus("error");
    }
  };

  const handleRemove = async () => {
    if (!result?.product_id) return;
    setRemoving(true);
    try {
      await removeDiscount(result.product_id);
      setResult(null);
      setStatus("idle");
      setProductId("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRemoving(false);
    }
  };

  return (
    <div className="p-5 bg-[#111118] border border-[#1e1e2a] rounded-2xl space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-amber-400/10 border border-amber-400/20 flex items-center justify-center text-amber-400 text-base">
          %
        </div>
        <div>
          <h3 className="font-display text-sm font-700 text-white">Apply Discount</h3>
          <p className="text-zinc-600 text-[10px] font-mono">Set % off on any product — stored in Redis with TTL</p>
        </div>
      </div>

      {/* Form */}
      <div className="space-y-2.5">
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">Product ID</label>
            <input
              value={productId}
              onChange={e => setProductId(e.target.value)}
              placeholder="PROD001"
              className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2 text-white text-xs font-mono placeholder:text-zinc-700 focus:outline-none focus:border-amber-400/40 transition-colors"
            />
          </div>
          <div>
            <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">Original Price (₹)</label>
            <input
              value={originalPrice}
              onChange={e => setOriginalPrice(e.target.value)}
              placeholder="999.00"
              type="number"
              className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2 text-white text-xs font-mono placeholder:text-zinc-700 focus:outline-none focus:border-amber-400/40 transition-colors"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">Discount %</label>
            <input
              value={discountPct}
              onChange={e => setDiscountPct(e.target.value)}
              placeholder="20"
              type="number"
              min={1}
              max={90}
              className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2 text-white text-xs font-mono placeholder:text-zinc-700 focus:outline-none focus:border-amber-400/40 transition-colors"
            />
          </div>
          <div>
            <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">Reason</label>
            <select
              value={reason}
              onChange={e => setReason(e.target.value)}
              className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2 text-white text-xs font-mono focus:outline-none focus:border-amber-400/40 transition-colors"
            >
              <option>Weekend Sale</option>
              <option>Flash Sale</option>
              <option>Clearance</option>
              <option>Seasonal Offer</option>
              <option>Loyalty Reward</option>
            </select>
          </div>
        </div>

        {/* Preview */}
        {productId && originalPrice && discountPct && (
          <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
            className="flex items-center justify-between px-3 py-2 bg-amber-400/5 border border-amber-400/15 rounded-lg">
            <span className="text-zinc-400 text-[11px] font-mono line-through">₹{Number(originalPrice).toFixed(2)}</span>
            <span className="text-amber-400 text-[10px] font-mono">−{discountPct}%</span>
            <span className="text-emerald-400 text-sm font-display font-700">
              ₹{(Number(originalPrice) * (1 - Number(discountPct) / 100)).toFixed(2)}
            </span>
          </motion.div>
        )}

        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={handleApply}
          disabled={status === "loading" || !productId || !originalPrice || !discountPct}
          className={clsx(
            "w-full py-2.5 rounded-xl font-display font-700 text-sm transition-all",
            status === "loading"
              ? "bg-amber-400/20 text-amber-400 cursor-not-allowed"
              : "bg-amber-400 text-black hover:bg-amber-300"
          )}
        >
          {status === "loading" ? "Applying…" : "Apply Discount"}
        </motion.button>
      </div>

      {/* Result */}
      <AnimatePresence>
        {status === "success" && result && (
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="p-3 bg-emerald-500/8 border border-emerald-500/20 rounded-xl space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-emerald-400 text-xs font-mono font-700">✓ Discount Applied</span>
              <button
                onClick={handleRemove}
                disabled={removing}
                className="text-red-400 text-[10px] font-mono hover:text-red-300 transition-colors"
              >
                {removing ? "Removing…" : "✕ Remove"}
              </button>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              {[
                { label: "Product", value: result.product_id },
                { label: "Was", value: `₹${result.original_price}` },
                { label: "Now", value: `₹${result.discounted_price.toFixed(2)}` },
              ].map(item => (
                <div key={item.label} className="bg-black/20 rounded-lg p-2">
                  <div className="text-white text-xs font-mono font-700">{item.value}</div>
                  <div className="text-zinc-600 text-[9px] font-mono">{item.label}</div>
                </div>
              ))}
            </div>
            <p className="text-zinc-600 text-[10px] font-mono">
              Applied at {new Date(result.applied_at).toLocaleTimeString("en-IN")}
            </p>
          </motion.div>
        )}

        {status === "error" && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-[11px] font-mono">
            ⚠ {error}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
