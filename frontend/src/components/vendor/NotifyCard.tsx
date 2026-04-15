"use client";
// frontend/src/components/vendor/NotifyCard.tsx

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { clsx } from "clsx";
import { notifyUser, NotifyResponse } from "@/lib/vendor-api";

export function NotifyCard() {
  const [email, setEmail]       = useState("");
  const [couponCode, setCouponCode] = useState("");
  const [status, setStatus]     = useState<"idle"|"loading"|"success"|"error">("idle");
  const [result, setResult]     = useState<NotifyResponse | null>(null);
  const [error, setError]       = useState("");

  const isValidEmail = (e: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);

  const handleSend = async () => {
    if (!email || !couponCode || !isValidEmail(email)) return;
    setStatus("loading");
    setError("");
    try {
      const data = await notifyUser({ user_email: email, coupon_code: couponCode.toUpperCase() });
      setResult(data);
      setStatus(data.sent ? "success" : "error");
      if (!data.sent) setError(data.message);
    } catch (e: any) {
      setError(e.message);
      setStatus("error");
    }
  };

  const handleReset = () => {
    setStatus("idle");
    setResult(null);
    setError("");
    setEmail("");
    setCouponCode("");
  };

  return (
    <div className="p-5 bg-[#111118] border border-[#1e1e2a] rounded-2xl space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 text-base">
          ✉
        </div>
        <div>
          <h3 className="font-display text-sm font-700 text-white">Send Coupon via Email</h3>
          <p className="text-zinc-600 text-[10px] font-mono">SMTP delivery · Gmail free tier</p>
        </div>
      </div>

      <AnimatePresence mode="wait">
        {status !== "success" ? (
          <motion.div key="form" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="space-y-2.5">
            <div>
              <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">
                Recipient Email
              </label>
              <div className="relative">
                <input
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="customer@gmail.com"
                  type="email"
                  className={clsx(
                    "w-full bg-[#0d0d14] border rounded-lg px-3 py-2 text-white text-xs font-mono placeholder:text-zinc-700 focus:outline-none transition-colors",
                    email && !isValidEmail(email)
                      ? "border-red-500/40 focus:border-red-500/60"
                      : "border-[#1e1e2a] focus:border-blue-500/40"
                  )}
                />
                {email && isValidEmail(email) && (
                  <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-emerald-400 text-xs">✓</span>
                )}
              </div>
              {email && !isValidEmail(email) && (
                <p className="text-red-400 text-[10px] font-mono mt-1">Invalid email format</p>
              )}
            </div>

            <div>
              <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">
                Coupon Code
              </label>
              <input
                value={couponCode}
                onChange={e => setCouponCode(e.target.value.toUpperCase())}
                placeholder="LAUNCH25"
                className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2 text-blue-400 text-xs font-mono uppercase placeholder:text-zinc-700 focus:outline-none focus:border-blue-500/40 transition-colors"
              />
            </div>

            {/* Preview */}
            {email && isValidEmail(email) && couponCode && (
              <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
                className="p-3 bg-blue-500/5 border border-blue-500/15 rounded-lg space-y-1">
                <p className="text-zinc-500 text-[10px] font-mono">Email preview</p>
                <p className="text-white text-xs font-mono">To: <span className="text-blue-400">{email}</span></p>
                <p className="text-white text-xs font-mono">
                  Coupon: <span className="text-purple-400 font-700">{couponCode}</span>
                </p>
              </motion.div>
            )}

            <motion.button whileTap={{ scale: 0.97 }} onClick={handleSend}
              disabled={status === "loading" || !email || !couponCode || !isValidEmail(email)}
              className={clsx(
                "w-full py-2.5 rounded-xl font-display font-700 text-sm transition-all relative overflow-hidden",
                status === "loading"
                  ? "bg-blue-500/20 text-blue-400 cursor-not-allowed"
                  : (!email || !couponCode || !isValidEmail(email))
                    ? "bg-zinc-800 text-zinc-600 cursor-not-allowed"
                    : "bg-blue-500 text-white hover:bg-blue-400"
              )}>
              {status === "loading" ? (
                <span className="flex items-center justify-center gap-2">
                  <motion.span
                    animate={{ rotate: 360 }}
                    transition={{ duration: 0.8, repeat: Infinity, ease: "linear" }}
                    className="inline-block w-4 h-4 border-2 border-blue-400/40 border-t-blue-400 rounded-full"
                  />
                  Sending via SMTP…
                </span>
              ) : "✉ Send Coupon Email"}
            </motion.button>

            <AnimatePresence>
              {status === "error" && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-[11px] font-mono">
                  ⚠ {error}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        ) : (
          <motion.div key="success" initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
            className="space-y-3">
            {/* Success animation */}
            <div className="flex flex-col items-center py-4 gap-3">
              <motion.div
                initial={{ scale: 0 }} animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 400, damping: 20 }}
                className="w-14 h-14 rounded-full bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-2xl">
                ✉
              </motion.div>
              <div className="text-center">
                <p className="text-emerald-400 font-display font-700 text-sm">Email Delivered!</p>
                <p className="text-zinc-500 text-[11px] font-mono mt-0.5">{result?.recipient}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-center">
              <div className="bg-[#0d0d14] rounded-lg p-2 border border-[#1e1e2a]">
                <div className="text-purple-400 text-xs font-mono font-700">{result?.coupon_code}</div>
                <div className="text-zinc-600 text-[9px] font-mono">Coupon sent</div>
              </div>
              <div className="bg-[#0d0d14] rounded-lg p-2 border border-[#1e1e2a]">
                <div className="text-emerald-400 text-xs font-mono font-700">Delivered</div>
                <div className="text-zinc-600 text-[9px] font-mono">SMTP status</div>
              </div>
            </div>

            <button onClick={handleReset}
              className="w-full py-2 rounded-xl text-xs font-mono text-zinc-500 border border-[#1e1e2a] hover:text-zinc-300 hover:border-zinc-600 transition-all">
              Send Another →
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
