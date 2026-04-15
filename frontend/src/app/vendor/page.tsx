"use client";
// frontend/src/app/vendor/page.tsx

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { clsx } from "clsx";
import { DiscountCard } from "@/components/vendor/DiscountCard";
import { CouponCard }   from "@/components/vendor/CouponCard";
import { SponsorCard }  from "@/components/vendor/SponsorCard";
import { NotifyCard }   from "@/components/vendor/NotifyCard";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getTokenPayload(): { sub: string; role: string } | null {
  try {
    const token = localStorage.getItem("vendor_token");
    if (!token) return null;
    return JSON.parse(atob(token.split(".")[1]));
  } catch { return null; }
}

// ── Login Form ────────────────────────────────────────────────────────────────
function VendorLogin({ onLogin }: { onLogin: () => void }) {
  const [email, setEmail]       = useState("vendor@test.com");
  const [password, setPassword] = useState("");
  const [status, setStatus]     = useState<"idle"|"loading"|"error">("idle");
  const [error, setError]       = useState("");
  const [registering, setRegistering] = useState(false);

  const doLogin = async () => {
    if (!email || !password) return;
    setStatus("loading"); setError("");
    try {
      const res  = await fetch(`${BASE}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Login failed");
      if (data.role !== "vendor") throw new Error(`Account role is "${data.role}" — login with a vendor account.`);
      localStorage.setItem("vendor_token", data.access_token);
      onLogin();
    } catch (e: any) { setError(e.message); setStatus("error"); }
  };

  const doRegister = async () => {
    if (!email || !password) return;
    setRegistering(true); setError("");
    try {
      const res  = await fetch(`${BASE}/api/v1/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, role: "vendor" }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Register failed");
      await doLogin();
    } catch (e: any) { setError(e.message); }
    finally { setRegistering(false); }
  };

  return (
    <div className="min-h-screen dashboard-dark flex items-center justify-center p-4" style={{ background: "var(--dash-bg)" }}>
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-sm space-y-5">

        <div className="text-center">
          <Link href="/" className="font-display text-2xl font-800 text-amber-400">FlowPriceAI</Link>
          <p className="text-zinc-500 text-xs font-mono mt-1">Vendor Panel · Phase 3</p>
        </div>

        <div className="p-6 bg-[#111118] border border-[#1e1e2a] rounded-2xl space-y-4">
          <div className="flex items-center gap-3 pb-4 border-b border-[#1e1e2a]">
            <div className="w-10 h-10 rounded-xl bg-amber-400/10 border border-amber-400/20 flex items-center justify-center text-amber-400 font-display font-800">V</div>
            <div>
              <p className="text-white font-display font-700 text-sm">Vendor Login</p>
              <p className="text-zinc-600 text-[10px] font-mono">Requires role: vendor</p>
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">Email</label>
              <input value={email} onChange={e => setEmail(e.target.value)} type="email"
                onKeyDown={e => e.key === "Enter" && doLogin()}
                className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2.5 text-white text-sm font-mono placeholder:text-zinc-700 focus:outline-none focus:border-amber-400/40 transition-colors"
              />
            </div>
            <div>
              <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">Password</label>
              <input value={password} onChange={e => setPassword(e.target.value)} type="password"
                placeholder="••••••••"
                onKeyDown={e => e.key === "Enter" && doLogin()}
                className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2.5 text-white text-sm font-mono placeholder:text-zinc-700 focus:outline-none focus:border-amber-400/40 transition-colors"
              />
            </div>
          </div>

          <AnimatePresence>
            {error && (
              <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                className="px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-[11px] font-mono">
                ⚠ {error}
              </motion.div>
            )}
          </AnimatePresence>

          <div className="space-y-2">
            <motion.button whileTap={{ scale: 0.97 }} onClick={doLogin}
              disabled={status === "loading" || !email || !password}
              className={clsx("w-full py-2.5 rounded-xl font-display font-700 text-sm transition-all",
                status === "loading" ? "bg-amber-400/20 text-amber-400 cursor-not-allowed"
                : !email || !password ? "bg-zinc-800 text-zinc-600 cursor-not-allowed"
                : "bg-amber-400 text-black hover:bg-amber-300")}>
              {status === "loading" ? (
                <span className="flex items-center justify-center gap-2">
                  <motion.span animate={{ rotate: 360 }} transition={{ duration: 0.8, repeat: Infinity, ease: "linear" }}
                    className="inline-block w-4 h-4 border-2 border-amber-400/40 border-t-amber-400 rounded-full" />
                  Signing in…
                </span>
              ) : "Sign In as Vendor"}
            </motion.button>

            <button onClick={doRegister} disabled={registering || !email || !password}
              className="w-full py-2 rounded-xl text-xs font-mono text-zinc-500 border border-[#1e1e2a] hover:text-zinc-300 hover:border-zinc-600 transition-all disabled:opacity-40">
              {registering ? "Registering…" : "No vendor account? Register →"}
            </button>
          </div>
        </div>

        <div className="p-3 bg-[#0d0d14] border border-[#1e1e2a] rounded-xl">
          <p className="text-zinc-600 text-[10px] font-mono">
            💡 Tip: Use the same email/password you registered with role "vendor" in Swagger. This login is separate from the storefront session.
          </p>
        </div>
      </motion.div>
    </div>
  );
}

// ── Vendor Banner ─────────────────────────────────────────────────────────────
function VendorBanner({ vendorId, onLogout }: { vendorId: string; onLogout: () => void }) {
  return (
    <div className="p-4 bg-amber-400/5 border border-amber-400/15 rounded-2xl flex items-center gap-4">
      <div className="w-10 h-10 rounded-xl bg-amber-400/15 border border-amber-400/25 flex items-center justify-center text-amber-400 font-display font-800 text-lg">V</div>
      <div className="flex-1">
        <p className="text-white font-display font-700 text-sm">Vendor Panel</p>
        <p className="text-zinc-500 text-[10px] font-mono">
          ID: <span className="text-amber-400">{vendorId}</span> · Role: <span className="text-emerald-400">vendor</span>
        </p>
      </div>
      <span className="px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-400 text-[10px] font-mono">✓ Authenticated</span>
      <button onClick={onLogout} className="px-3 py-1.5 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-[10px] font-mono hover:bg-red-500/20 transition-all">
        Logout
      </button>
    </div>
  );
}

function StatCard({ label, value, sub, color = "text-white" }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="p-4 bg-[#111118] border border-[#1e1e2a] rounded-xl">
      <p className="text-zinc-600 text-[10px] font-mono uppercase tracking-wider mb-1">{label}</p>
      <div className={clsx("font-display text-2xl font-800", color)}>{value}</div>
      {sub && <p className="text-zinc-600 text-[10px] font-mono mt-1">{sub}</p>}
    </div>
  );
}

// ── MAIN ──────────────────────────────────────────────────────────────────────
export default function VendorPage() {
  const [authed, setAuthed]   = useState(false);
  const [vendorId, setVendorId] = useState("");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const payload = getTokenPayload();
    if (payload?.role === "vendor") {
      setAuthed(true);
      setVendorId(payload.sub?.slice(0, 8) + "…");
    }
  }, []);

  const handleLogin = () => {
    const payload = getTokenPayload();
    if (payload?.role === "vendor") { setAuthed(true); setVendorId(payload.sub?.slice(0, 8) + "…"); }
  };

  const handleLogout = () => { localStorage.removeItem("vendor_token"); setAuthed(false); setVendorId(""); };

  if (!mounted) return null;
  if (!authed)  return <VendorLogin onLogin={handleLogin} />;

  return (
    <div className="min-h-screen dashboard-dark" style={{ background: "var(--dash-bg)" }}>
      <header className="sticky top-0 z-30 glass border-b border-[#181828]">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 h-14 flex items-center gap-4">
          <Link href="/" className="font-display text-xl font-800 text-amber-400 tracking-tight">FlowPriceAI</Link>
          <div className="h-4 w-px bg-[#1e1e2e]" />
          <h1 className="font-display text-sm font-600 text-zinc-300">Vendor Panel</h1>
          <div className="flex items-center gap-2 ml-auto">
            <Link href="/dashboard" className="px-2.5 py-1 rounded-lg text-xs font-mono bg-[#11111e] text-zinc-400 border border-[#1e1e2e] hover:text-white transition-colors">Dashboard ↗</Link>
            <Link href="/storefront" className="px-2.5 py-1 rounded-lg text-xs font-mono bg-amber-400/10 text-amber-400 border border-amber-400/20 hover:bg-amber-400/20 transition-colors">Storefront ↗</Link>
          </div>
        </div>
      </header>

      <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-6 space-y-5">
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <VendorBanner vendorId={vendorId} onLogout={handleLogout} />
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
          className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="Phase" value="3" sub="Vendor Panel" color="text-amber-400" />
          <StatCard label="Endpoints" value="6" sub="All tested ✓" color="text-emerald-400" />
          <StatCard label="Email" value="SMTP" sub="Gmail free tier" color="text-blue-400" />
          <StatCard label="Coupon TTL" value="Redis" sub="Atomic counter" color="text-purple-400" />
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}><DiscountCard /></motion.div>
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}><CouponCard /></motion.div>
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}><SponsorCard /></motion.div>
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}><NotifyCard /></motion.div>
        </div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}
          className="p-5 bg-[#111118] border border-[#1e1e2a] rounded-2xl">
          <h3 className="font-display text-sm font-700 text-white mb-4">Phase 3 — API Status</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {[
              { endpoint: "POST /vendor/discount",       detail: "Redis TTL · decoupled from catalog" },
              { endpoint: "DELETE /vendor/discount/:id", detail: "Early removal before TTL" },
              { endpoint: "POST /vendor/coupon",         detail: "Unique check · DB + Redis" },
              { endpoint: "POST /vendor/coupon/redeem",  detail: "Atomic incr · race-safe" },
              { endpoint: "POST /vendor/sponsor",        detail: "Badge · 201 response" },
              { endpoint: "POST /vendor/notify",         detail: "SMTP Gmail · App Password" },
            ].map(item => (
              <div key={item.endpoint} className="p-3 bg-[#0d0d14] rounded-xl border border-[#1e1e2a] space-y-0.5">
                <div className="text-zinc-500 text-[9px] font-mono">{item.endpoint}</div>
                <div className="text-emerald-400 font-display font-600 text-xs">✓ Live</div>
                <div className="text-zinc-600 text-[9px] font-mono">{item.detail}</div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}