"use client";
// frontend/src/components/vendor/CouponCard.tsx

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { clsx } from "clsx";
import { createCoupon, redeemCoupon, CouponResponse, CouponRedeemResponse } from "@/lib/vendor-api";

type CouponTab = "create" | "redeem";

export function CouponCard() {
  const [tab, setTab] = useState<CouponTab>("create");

  // Create state
  const [code, setCode]           = useState("");
  const [discountPct, setDiscountPct] = useState("");
  const [target, setTarget]       = useState("all");
  const [targetId, setTargetId]   = useState("");
  const [maxUses, setMaxUses]     = useState("10");
  const [ttlMinutes, setTtlMinutes] = useState("1440");
  const [createStatus, setCreateStatus] = useState<"idle"|"loading"|"success"|"error">("idle");
  const [createResult, setCreateResult] = useState<CouponResponse | null>(null);
  const [createError, setCreateError]   = useState("");

  // Redeem state
  const [redeemCode, setRedeemCode]   = useState("");
  const [userId, setUserId]           = useState("");
  const [cartTotal, setCartTotal]     = useState("");
  const [redeemStatus, setRedeemStatus] = useState<"idle"|"loading"|"success"|"error">("idle");
  const [redeemResult, setRedeemResult] = useState<CouponRedeemResponse | null>(null);
  const [redeemError, setRedeemError]   = useState("");

  const handleCreate = async () => {
    if (!code || !discountPct) return;
    setCreateStatus("loading");
    setCreateError("");
    try {
      const data = await createCoupon({
        code: code.toUpperCase(),
        discount_pct: Number(discountPct),
        target,
        target_id: targetId || null,
        max_uses: Number(maxUses),
        ttl_minutes: Number(ttlMinutes),
      });
      setCreateResult(data);
      setCreateStatus("success");
    } catch (e: any) {
      setCreateError(e.message);
      setCreateStatus("error");
    }
  };

  const handleRedeem = async () => {
    if (!redeemCode || !userId || !cartTotal) return;
    setRedeemStatus("loading");
    setRedeemError("");
    try {
      const data = await redeemCoupon({
        code: redeemCode.toUpperCase(),
        user_id: userId,
        cart_total: Number(cartTotal),
      });
      setRedeemResult(data);
      setRedeemStatus("success");
    } catch (e: any) {
      setRedeemError(e.message);
      setRedeemStatus("error");
    }
  };

  return (
    <div className="p-5 bg-[#111118] border border-[#1e1e2a] rounded-2xl space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 text-base">
          🎟
        </div>
        <div>
          <h3 className="font-display text-sm font-700 text-white">Coupon Manager</h3>
          <p className="text-zinc-600 text-[10px] font-mono">Generate codes · Redis TTL · atomic redemption</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-[#0d0d14] rounded-xl border border-[#1e1e2a]">
        {(["create", "redeem"] as CouponTab[]).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={clsx(
              "flex-1 py-1.5 rounded-lg text-xs font-mono capitalize transition-all",
              tab === t ? "bg-purple-500/20 text-purple-400 border border-purple-500/20" : "text-zinc-600 hover:text-zinc-400"
            )}>
            {t}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {tab === "create" ? (
          <motion.div key="create" initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 8 }}
            className="space-y-2.5">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">Code</label>
                <input value={code} onChange={e => setCode(e.target.value.toUpperCase())}
                  placeholder="SAVE25"
                  className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2 text-purple-400 text-xs font-mono uppercase placeholder:text-zinc-700 focus:outline-none focus:border-purple-500/40 transition-colors"
                />
              </div>
              <div>
                <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">Discount %</label>
                <input value={discountPct} onChange={e => setDiscountPct(e.target.value)}
                  placeholder="25" type="number" min={1} max={90}
                  className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2 text-white text-xs font-mono placeholder:text-zinc-700 focus:outline-none focus:border-purple-500/40 transition-colors"
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">Target</label>
                <select value={target} onChange={e => setTarget(e.target.value)}
                  className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2 text-white text-xs font-mono focus:outline-none focus:border-purple-500/40 transition-colors">
                  <option value="all">All</option>
                  <option value="user">User</option>
                  <option value="segment">Segment</option>
                </select>
              </div>
              <div>
                <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">Max Uses</label>
                <input value={maxUses} onChange={e => setMaxUses(e.target.value)}
                  type="number" min={1}
                  className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2 text-white text-xs font-mono focus:outline-none focus:border-purple-500/40 transition-colors"
                />
              </div>
              <div>
                <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">TTL (min)</label>
                <input value={ttlMinutes} onChange={e => setTtlMinutes(e.target.value)}
                  type="number" min={1}
                  className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2 text-white text-xs font-mono focus:outline-none focus:border-purple-500/40 transition-colors"
                />
              </div>
            </div>

            {target !== "all" && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}>
                <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">
                  {target === "user" ? "User ID" : "Segment Name"}
                </label>
                <input value={targetId} onChange={e => setTargetId(e.target.value)}
                  placeholder={target === "user" ? "USER123" : "premium"}
                  className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2 text-white text-xs font-mono placeholder:text-zinc-700 focus:outline-none focus:border-purple-500/40 transition-colors"
                />
              </motion.div>
            )}

            <motion.button whileTap={{ scale: 0.97 }} onClick={handleCreate}
              disabled={createStatus === "loading" || !code || !discountPct}
              className={clsx(
                "w-full py-2.5 rounded-xl font-display font-700 text-sm transition-all",
                createStatus === "loading"
                  ? "bg-purple-500/20 text-purple-400 cursor-not-allowed"
                  : "bg-purple-500 text-white hover:bg-purple-400"
              )}>
              {createStatus === "loading" ? "Creating…" : "Generate Coupon"}
            </motion.button>

            <AnimatePresence>
              {createStatus === "success" && createResult && (
                <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  className="p-3 bg-purple-500/8 border border-purple-500/20 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-purple-400 font-mono font-700 text-sm tracking-widest">{createResult.code}</span>
                    <span className="text-emerald-400 text-xs font-mono">✓ Created</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    {[
                      { label: "Discount", value: `${createResult.discount_pct}%` },
                      { label: "Uses", value: createResult.uses_remaining },
                      { label: "Target", value: createResult.target },
                    ].map(item => (
                      <div key={item.label} className="bg-black/20 rounded-lg p-2">
                        <div className="text-white text-xs font-mono font-700">{item.value}</div>
                        <div className="text-zinc-600 text-[9px] font-mono">{item.label}</div>
                      </div>
                    ))}
                  </div>
                  <p className="text-zinc-600 text-[10px] font-mono">
                    Expires {new Date(createResult.expires_at).toLocaleString("en-IN")}
                  </p>
                </motion.div>
              )}
              {createStatus === "error" && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-[11px] font-mono">
                  ⚠ {createError}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        ) : (
          <motion.div key="redeem" initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }}
            className="space-y-2.5">
            <div>
              <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">Coupon Code</label>
              <input value={redeemCode} onChange={e => setRedeemCode(e.target.value.toUpperCase())}
                placeholder="LAUNCH25"
                className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2 text-purple-400 text-xs font-mono uppercase placeholder:text-zinc-700 focus:outline-none focus:border-purple-500/40 transition-colors"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">User ID</label>
                <input value={userId} onChange={e => setUserId(e.target.value)}
                  placeholder="USER123"
                  className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2 text-white text-xs font-mono placeholder:text-zinc-700 focus:outline-none focus:border-purple-500/40 transition-colors"
                />
              </div>
              <div>
                <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">Cart Total (₹)</label>
                <input value={cartTotal} onChange={e => setCartTotal(e.target.value)}
                  placeholder="1000" type="number"
                  className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2 text-white text-xs font-mono placeholder:text-zinc-700 focus:outline-none focus:border-purple-500/40 transition-colors"
                />
              </div>
            </div>

            <motion.button whileTap={{ scale: 0.97 }} onClick={handleRedeem}
              disabled={redeemStatus === "loading" || !redeemCode || !userId || !cartTotal}
              className={clsx(
                "w-full py-2.5 rounded-xl font-display font-700 text-sm transition-all",
                redeemStatus === "loading"
                  ? "bg-purple-500/20 text-purple-400 cursor-not-allowed"
                  : "bg-purple-500 text-white hover:bg-purple-400"
              )}>
              {redeemStatus === "loading" ? "Validating…" : "Redeem Coupon"}
            </motion.button>

            <AnimatePresence>
              {redeemStatus === "success" && redeemResult && (
                <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  className={clsx("p-3 rounded-xl border space-y-2",
                    redeemResult.valid
                      ? "bg-emerald-500/8 border-emerald-500/20"
                      : "bg-red-500/8 border-red-500/20")}>
                  <p className={clsx("text-xs font-mono font-700", redeemResult.valid ? "text-emerald-400" : "text-red-400")}>
                    {redeemResult.valid ? "✓ " : "✗ "}{redeemResult.message}
                  </p>
                  {redeemResult.valid && (
                    <div className="grid grid-cols-2 gap-2 text-center">
                      <div className="bg-black/20 rounded-lg p-2">
                        <div className="text-white text-xs font-mono font-700">₹{cartTotal}</div>
                        <div className="text-zinc-600 text-[9px] font-mono">Original</div>
                      </div>
                      <div className="bg-black/20 rounded-lg p-2">
                        <div className="text-emerald-400 text-xs font-mono font-700">₹{redeemResult.discounted_total}</div>
                        <div className="text-zinc-600 text-[9px] font-mono">After discount</div>
                      </div>
                    </div>
                  )}
                </motion.div>
              )}
              {redeemStatus === "error" && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-[11px] font-mono">
                  ⚠ {redeemError}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
