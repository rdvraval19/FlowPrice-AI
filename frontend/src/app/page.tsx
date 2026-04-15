"use client";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import { PERSONAS, Persona } from "@/lib/personas";
import { useSessionStore } from "@/store/session";
import { registerUser, loginUser } from "@/lib/api-client";

// ── Backend auth ──────────────────────────────────────────────────────────────
async function authenticatePersona(
  persona: Persona,
  setAuth: (token: string, role: "user" | "vendor", userId: string) => void
): Promise<void> {
  const email    = `${persona.id}@flowprice.demo`;
  const password = `demo_${persona.id}_2024`;
  const role: "user" | "vendor" = persona.id === "admin" ? "vendor" : "user";
  try {
    await registerUser({ email, password, role }).catch(() => null);
    const authData = await loginUser({ email, password });
    setAuth(authData.access_token, authData.role, authData.user_id);
  } catch {
    console.warn("Auth failed for persona", persona.id);
  }
}

// ── Backend event seeding ─────────────────────────────────────────────────────
async function seedPersonaEvents(persona: Persona, sessionId: string): Promise<void> {
  const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const events = persona.seedEvents.map((e) => ({
    session_id:      sessionId,
    event_type:      e.event_type,
    timestamp_ms:    Date.now() - Math.floor(Math.random() * 300000),
    device_type:     "desktop",
    user_segment:    persona.segment,
    referral_source: "direct",
    ...(e.product ? { product: e.product } : {}),
    ...(e.search  ? { search:  e.search  } : {}),
  }));
  try {
    await fetch(`${BASE}/api/v1/events/ingest/batch`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ events }),
    });
  } catch { /* non-fatal */ }
}

// ── System health ─────────────────────────────────────────────────────────────
function useSystemHealth() {
  const [health, setHealth] = useState({
    redis: "checking" as "ok" | "error" | "checking",
    streamLen: 0,
    p99: 0,
  });
  useEffect(() => {
    const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const check = async () => {
      try {
        const [hRes, mRes] = await Promise.all([
          fetch(`${BASE}/health`,                { signal: AbortSignal.timeout(2000) }),
          fetch(`${BASE}/api/v1/events/metrics`, { signal: AbortSignal.timeout(2000) }),
        ]);
        const h = await hRes.json();
        const m = await mRes.json();
        setHealth({
          redis:     h.redis === "connected" ? "ok" : "error",
          streamLen: m.stream_len     || 0,
          p99:       m.p99_latency_ms || 0,
        });
      } catch { setHealth(s => ({ ...s, redis: "error" })); }
    };
    check();
    const t = setInterval(check, 5000);
    return () => clearInterval(t);
  }, []);
  return health;
}

// ── Fingerprint scanner ───────────────────────────────────────────────────────
function FingerprintScanner({ active, color }: { active: boolean; color: string }) {
  return (
    <div className="flex items-end gap-[2px] h-5">
      {Array.from({ length: 12 }).map((_, i) => (
        <motion.div
          key={i}
          className="w-[2px] rounded-sm"
          style={{ backgroundColor: color }}
          animate={active
            ? { height: ["4px", `${6 + (i % 4) * 4}px`, "4px"], opacity: [0.3, 1, 0.3] }
            : { height: "2px", opacity: 0.2 }
          }
          transition={{ duration: 0.6, repeat: active ? Infinity : 0, delay: i * 0.04, ease: "easeInOut" }}
        />
      ))}
    </div>
  );
}

// ── Persona card (side-by-side) ───────────────────────────────────────────────
function PersonaCard({ persona, onSelect, isSelected, isOther, index, dark }: {
  persona: Persona; onSelect: (p: Persona) => void;
  isSelected: boolean; isOther: boolean; index: number; dark: boolean;
}) {
  const [hovered, setHovered] = useState(false);
  const active     = hovered || isSelected;
  const cardBg     = dark ? "rgba(11,11,18,0.95)"   : "rgba(255,255,255,0.97)";
  const borderIdle = dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.08)";
  const headCol    = dark ? "#ffffff"                : "#0f172a";
  const subCol     = dark ? "#71717a"                : "#6b7280";
  const intentBg   = dark ? "#27272a"                : "#e5e7eb";

  return (
    <motion.div
      initial={{ opacity: 0, y: 28 }}
      animate={{ opacity: isOther ? 0.3 : 1, y: 0, scale: isOther ? 0.97 : 1 }}
      transition={{ delay: index * 0.1, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
      onClick={() => onSelect(persona)}
      className="relative cursor-pointer rounded-2xl overflow-hidden flex flex-col"
      style={{
        background:  cardBg,
        border:      `1px solid ${active ? persona.borderHex : borderIdle}`,
        boxShadow:   active
          ? `0 0 32px ${persona.glowHex}22, 0 8px 28px rgba(0,0,0,0.18), inset 0 1px 0 ${persona.glowHex}15`
          : dark ? "0 2px 12px rgba(0,0,0,0.35)" : "0 2px 10px rgba(0,0,0,0.05)",
        transition: "box-shadow 0.3s, border-color 0.3s",
      }}
    >
      {/* Top glow line */}
      <motion.div className="absolute top-0 left-0 right-0 h-[1px]"
        style={{ background: persona.glowHex }}
        animate={{ opacity: active ? 1 : 0.2 }} transition={{ duration: 0.25 }}
      />
      <AnimatePresence>
        {hovered && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="absolute inset-0 pointer-events-none"
            style={{ background: `radial-gradient(ellipse 80% 55% at 50% 0%, ${persona.glowHex}0c 0%, transparent 70%)` }}
          />
        )}
      </AnimatePresence>

      <div className="p-6 flex flex-col gap-4 flex-1">
        {/* Icon + badge */}
        <div className="flex items-start justify-between">
          <div className="px-2 py-0.5 rounded text-[9px] font-mono font-700 tracking-widest"
            style={{ backgroundColor: `${persona.glowHex}18`, color: persona.glowHex, border: `1px solid ${persona.glowHex}30` }}>
            {persona.badge}
          </div>
          <motion.span className="text-4xl leading-none"
            animate={{ scale: active ? 1.12 : 1 }} transition={{ duration: 0.25 }}>
            {persona.icon}
          </motion.span>
        </div>

        {/* Name + tagline */}
        <div>
          <h2 className="font-display text-xl font-800 leading-tight" style={{ color: headCol }}>
            {persona.name}
          </h2>
          <p className="text-xs mt-1 leading-relaxed" style={{ color: subCol }}>{persona.tagline}</p>
        </div>

        {/* Fingerprint */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[9px] font-mono uppercase tracking-wider" style={{ color: subCol }}>
              Behavioral Fingerprint
            </span>
            <AnimatePresence>
              {hovered && (
                <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="text-[9px] font-mono" style={{ color: persona.glowHex }}>
                  ML scanning…
                </motion.span>
              )}
            </AnimatePresence>
          </div>
          <FingerprintScanner active={active} color={persona.glowHex} />
        </div>

        <div className="h-px" style={{ background: dark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.06)" }} />

        {/* Signals */}
        <div className="space-y-1.5">
          <p className="text-[9px] font-mono uppercase tracking-wider" style={{ color: subCol }}>
            Session pre-loaded with
          </p>
          {persona.signals.map((s, i) => (
            <motion.div key={i} initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 + i * 0.04 + 0.2 }}
              className="flex items-center gap-2">
              <span className="text-xs w-4 flex-shrink-0">{s.icon}</span>
              <span className="text-[10px]" style={{ color: subCol }}>{s.label}: </span>
              <span className="text-[10px] font-mono" style={{ color: dark ? "#d4d4d8" : "#374151" }}>{s.value}</span>
            </motion.div>
          ))}
        </div>

        {/* Intent bar */}
        <div className="space-y-1">
          <div className="flex justify-between">
            <span className="text-[9px] font-mono" style={{ color: subCol }}>INTENT</span>
            <span className="text-[9px] font-mono font-700" style={{ color: persona.glowHex }}>
              {persona.intentScore}%
            </span>
          </div>
          <div className="h-1 rounded-full overflow-hidden" style={{ background: intentBg }}>
            <motion.div initial={{ width: 0 }} animate={{ width: `${persona.intentScore}%` }}
              transition={{ duration: 1.1, ease: "easeOut", delay: 0.35 }}
              className="h-full rounded-full" style={{ backgroundColor: persona.glowHex }} />
          </div>
        </div>

        {/* Stats row */}
        <div className="flex gap-3 text-center">
          {[
            { val: persona.seedEvents.length, label: "seed events", highlight: true  },
            { val: persona.purchaseHistory,   label: "purchases",   highlight: false },
            { val: `${persona.intentScore}%`, label: "intent",      highlight: false },
          ].map((st, i) => (
            <div key={i} className="flex-1 relative">
              {i > 0 && <div className="absolute left-0 top-1 bottom-1 w-px"
                style={{ background: dark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.06)" }} />}
              <div className="font-display text-lg font-800"
                style={{ color: st.highlight ? persona.glowHex : headCol }}>{st.val}</div>
              <div className="text-[9px] font-mono" style={{ color: subCol }}>{st.label}</div>
            </div>
          ))}
        </div>

        {/* CTA */}
        <motion.button whileTap={{ scale: 0.96 }}
          className="w-full py-3 rounded-xl font-display font-700 text-sm mt-auto transition-all"
          style={active
            ? { backgroundColor: persona.glowHex, color: "#000", boxShadow: `0 0 20px ${persona.glowHex}50` }
            : { backgroundColor: `${persona.glowHex}15`, color: persona.glowHex, border: `1px solid ${persona.glowHex}28` }
          }>
          {isSelected ? "Authenticating…" : `Enter as ${persona.name}`}
        </motion.button>
      </div>
    </motion.div>
  );
}

// ── System health bar ─────────────────────────────────────────────────────────
function SystemHealthBar({ dark }: { dark: boolean }) {
  const health = useSystemHealth();
  const { userRole, accessToken } = useSessionStore();
  const subCol  = dark ? "#52525b" : "#9ca3af";
  const mainCol = dark ? "#fff"    : "#111";
  const divCol  = dark ? "rgba(255,255,255,0.07)" : "rgba(0,0,0,0.08)";

  const dot = (s: "ok" | "error" | "checking") => (
    <span className={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${
      s === "ok"      ? "bg-emerald-400 animate-pulse"
      : s === "error" ? "bg-red-400"
      : "bg-zinc-500 animate-pulse"}`} />
  );

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }}
      className="flex items-center justify-center gap-3 py-2 px-4 rounded-xl text-[10px] font-mono flex-wrap"
      style={{
        background: dark ? "rgba(13,13,20,0.85)" : "rgba(243,244,246,0.9)",
        border: `1px solid ${divCol}`,
      }}>
      <div className="flex items-center gap-1.5">
        {dot(health.redis)}
        <span style={{ color: health.redis === "ok" ? "#34d399" : subCol }}>
          Redis {health.redis === "ok" ? "OK" : health.redis === "error" ? "OFFLINE" : "…"}
        </span>
      </div>
      <div className="w-px h-3" style={{ background: divCol }} />
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse flex-shrink-0" />
        <span style={{ color: subCol }}>
          Stream: <span style={{ color: mainCol }}>
            {health.streamLen > 0 ? health.streamLen.toLocaleString("en-IN") : "—"} events
          </span>
        </span>
      </div>
      <div className="w-px h-3" style={{ background: divCol }} />
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
        <span style={{ color: subCol }}>
          p99: <span style={{ color: health.p99 > 0 && health.p99 < 200 ? "#34d399" : mainCol }}>
            {health.p99 > 0 ? `${health.p99.toFixed(0)}ms ✓` : "—"}
          </span>
        </span>
      </div>
      {accessToken && (
        <>
          <div className="w-px h-3" style={{ background: divCol }} />
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse flex-shrink-0" />
            <span className="text-violet-400">JWT · {userRole}</span>
          </div>
        </>
      )}
      <div className="w-px h-3 hidden sm:block" style={{ background: divCol }} />
      <span className="hidden sm:block" style={{ color: subCol }}>GRU4Rec · Collaborative Filtering · Redis Streams</span>
    </motion.div>
  );
}

// ── Theme toggle ──────────────────────────────────────────────────────────────
function ThemeToggle({ dark, onToggle }: { dark: boolean; onToggle: () => void }) {
  return (
    <motion.button onClick={onToggle} whileTap={{ scale: 0.92 }}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-mono transition-all"
      style={{
        background: dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)",
        border:     dark ? "1px solid rgba(255,255,255,0.1)" : "1px solid rgba(0,0,0,0.1)",
        color:      dark ? "#a1a1aa" : "#6b7280",
      }}>
      <motion.span key={dark ? "moon" : "sun"}
        initial={{ rotate: -20, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }}
        transition={{ duration: 0.3 }} className="text-sm">
        {dark ? "🌙" : "☀️"}
      </motion.span>
      {dark ? "Dark" : "Light"}
    </motion.button>
  );
}

// ── MAIN ──────────────────────────────────────────────────────────────────────
const CUSTOMER_PERSONA = PERSONAS.find(p => p.id === "customer")!;
const ADMIN_PERSONA    = PERSONAS.find(p => p.id === "admin")!;

export default function LoginPage() {
  const router = useRouter();
  const { setPersona, sessionId, setAuth } = useSessionStore();

  const [selectedId,  setSelectedId]  = useState<string | null>(null);
  const [seeding,     setSeeding]     = useState(false);
  const [seedingStep, setSeedingStep] = useState<"auth" | "events">("auth");
  const [dark,        setDark]        = useState(true);

  const handleSelect = async (persona: Persona) => {
    if (seeding) return;
    setSelectedId(persona.id);
    setSeeding(true);
    setSeedingStep("auth");
    setPersona(persona.id, persona.name, persona.segment);
    await authenticatePersona(persona, setAuth);
    setSeedingStep("events");
    await seedPersonaEvents(persona, sessionId);
    await new Promise(r => setTimeout(r, 600));
    router.push(persona.redirectTo);
  };

  const anySelected = selectedId !== null;

  // Theme tokens
  const pageBg     = dark ? "#080810"                : "#f8fafc";
  const headCol    = dark ? "#ffffff"                : "#0f172a";
  const subCol     = dark ? "#71717a"                : "#6b7280";
  const dividerCol = dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.08)";
  const pillBg     = dark ? "rgba(245,158,11,0.10)"  : "rgba(245,158,11,0.12)";
  const pillBorder = dark ? "rgba(245,158,11,0.20)"  : "rgba(245,158,11,0.30)";
  const gridLine   = dark ? "rgba(255,255,255,0.018)": "rgba(0,0,0,0.04)";

  const seedCount = selectedId === "customer"
    ? CUSTOMER_PERSONA.seedEvents.length
    : 1;

  return (
    <div className="min-h-screen flex flex-col" style={{ background: pageBg, transition: "background 0.4s" }}>

      {/* Grid bg */}
      <div className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage: `linear-gradient(${gridLine} 1px, transparent 1px),
                            linear-gradient(90deg, ${gridLine} 1px, transparent 1px)`,
          backgroundSize: "60px 60px",
        }}
      />
      {/* Ambient glow */}
      <div className="fixed inset-0 pointer-events-none"
        style={{ background: `radial-gradient(ellipse 80% 35% at 50% -5%, rgba(245,158,11,${dark ? "0.07" : "0.04"}) 0%, transparent 65%)` }}
      />

      <div className="relative flex flex-col min-h-screen">

        {/* ── Nav ── */}
        <nav className="flex items-center justify-between px-6 py-4">
          <motion.div initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} className="flex items-center gap-3">
            <span className="font-display text-2xl font-800 text-amber-400 tracking-tight">FlowPriceAI</span>
            <span className="hidden sm:block text-xs font-mono" style={{ color: dark ? "#3f3f46" : "#d1d5db" }}>
              / Dynamic Pricing Engine
            </span>
          </motion.div>
          <div className="flex items-center gap-3">
            <ThemeToggle dark={dark} onToggle={() => setDark(d => !d)} />
            <motion.div initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }}
              className="flex items-center gap-2 px-3 py-1.5 rounded-full border"
              style={{ background: "rgba(16,185,129,0.08)", borderColor: "rgba(16,185,129,0.2)" }}>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-emerald-400 text-xs font-mono">System Live · Real-Time ML</span>
            </motion.div>
          </div>
        </nav>

        {/* ── Hero ── */}
        <div className="text-center px-4 pt-3 pb-5">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-amber-400 text-xs font-mono mb-3 border"
            style={{ background: pillBg, borderColor: pillBorder }}>
            <span>👟</span> India's Real-Time Sneaker Pricing Engine · Sub-200ms p99
          </motion.div>

          <motion.h1 initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
            className="font-display text-3xl sm:text-4xl font-800 leading-tight" style={{ color: headCol }}>
            Choose Your <span className="text-amber-400">Profile</span>
          </motion.h1>

          <motion.p initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
            className="text-sm mt-2 max-w-lg mx-auto leading-relaxed" style={{ color: subCol }}>
            Each profile seeds real behavioral events into Redis Streams — solving cold-start{" "}
            <span className="font-600" style={{ color: headCol }}>before you see a single price</span>.
          </motion.p>
        </div>

        {/* ── Two cards side by side ── */}
        <div className="flex-1 flex flex-col justify-center px-4 pb-4 max-w-3xl mx-auto w-full gap-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <PersonaCard
              persona={CUSTOMER_PERSONA} index={0} dark={dark}
              onSelect={handleSelect}
              isSelected={selectedId === "customer"}
              isOther={anySelected && selectedId !== "customer"}
            />
            <PersonaCard
              persona={ADMIN_PERSONA} index={1} dark={dark}
              onSelect={handleSelect}
              isSelected={selectedId === "admin"}
              isOther={anySelected && selectedId !== "admin"}
            />
          </div>

          {/* Divider hint */}
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.35 }}
            className="flex items-center gap-3">
            <div className="flex-1 h-px" style={{ background: dividerCol }} />
            <span className="text-[10px] font-mono uppercase tracking-widest" style={{ color: subCol }}>
              customer → storefront &nbsp;·&nbsp; admin → dashboard
            </span>
            <div className="flex-1 h-px" style={{ background: dividerCol }} />
          </motion.div>

          {/* Health bar */}
          <SystemHealthBar dark={dark} />
        </div>
      </div>

      {/* ── Seeding overlay ── */}
      <AnimatePresence>
        {seeding && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/75 backdrop-blur-sm">
            <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
              className="text-center space-y-4">
              <motion.div animate={{ rotate: 360 }}
                transition={{ duration: 0.9, repeat: Infinity, ease: "linear" }}
                className="w-10 h-10 border-2 border-amber-400/30 border-t-amber-400 rounded-full mx-auto"
              />
              <p className="font-display text-lg text-white font-700">
                {seedingStep === "auth" ? "Authenticating…" : "Seeding your session…"}
              </p>
              <div className="space-y-1">
                <p className="text-zinc-400 text-xs font-mono">
                  {seedingStep === "auth"
                    ? "Register → Login → JWT issued"
                    : `Firing ${seedCount} behavioral events into Redis Streams`}
                </p>
                <p className="text-zinc-600 text-xs font-mono">
                  Redis Streams → Feature Store → ML Model → Personalised Prices
                </p>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}