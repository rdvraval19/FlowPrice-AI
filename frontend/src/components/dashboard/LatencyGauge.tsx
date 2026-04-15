"use client";
import { motion } from "framer-motion";
import { clsx } from "clsx";

interface LatencyGaugeProps {
  p50: number;
  p95: number;
  p99: number;
  count: number;
  slaTarget?: number;
  loading?: boolean;
}

function Arc({ value, max, color, radius = 52 }: { value: number; max: number; color: string; radius?: number }) {
  const circumference = 2 * Math.PI * radius;
  const half = circumference / 2;
  const pct = Math.min(value / max, 1);
  const filled = pct * half;

  return (
    <svg width={radius * 2 + 20} height={radius + 16} viewBox={`0 0 ${radius * 2 + 20} ${radius + 16}`} className="overflow-visible">
      {/* Track */}
      <path
        d={`M 10 ${radius + 8} A ${radius} ${radius} 0 0 1 ${radius * 2 + 10} ${radius + 8}`}
        fill="none" stroke="#1e1e2a" strokeWidth="6" strokeLinecap="round"
      />
      {/* Fill */}
      <motion.path
        d={`M 10 ${radius + 8} A ${radius} ${radius} 0 0 1 ${radius * 2 + 10} ${radius + 8}`}
        fill="none" stroke={color} strokeWidth="6" strokeLinecap="round"
        strokeDasharray={`${half} ${half}`}
        initial={{ strokeDashoffset: half }}
        animate={{ strokeDashoffset: half - filled }}
        transition={{ duration: 1, ease: "easeOut" }}
      />
    </svg>
  );
}

function GaugePill({
  label, value, target, color,
}: { label: string; value: number; target: number; color: string }) {
  const pct = Math.min(value / target, 2);  // 2x target = full bar
  const overSLA = value > target;

  return (
    <div className="flex-1 min-w-0">
      <div className="flex justify-between items-baseline mb-1.5">
        <span className="text-zinc-500 text-[11px] font-mono uppercase">{label}</span>
        <span className={clsx("font-mono text-sm font-600", overSLA ? "text-red-400" : color)}>
          {value.toFixed(1)}<span className="text-[10px] text-zinc-600">ms</span>
        </span>
      </div>
      <div className="h-1.5 bg-[#1a1a26] rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(pct * 50, 100)}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="h-full rounded-full"
          style={{ backgroundColor: overSLA ? "#ef4444" : color }}
        />
      </div>
    </div>
  );
}

export function LatencyGauge({
  p50, p95, p99, count, slaTarget = 200, loading = false,
}: LatencyGaugeProps) {
  const meetsSLA = p99 < slaTarget;
  const p99Color = p99 < slaTarget * 0.5 ? "#10b981" : p99 < slaTarget ? "#f59e0b" : "#ef4444";

  if (loading) {
    return (
      <div className="p-5 bg-[#111118] border border-[#1e1e2a] rounded-2xl space-y-4">
        <div className="skeleton h-4 w-32 rounded" />
        <div className="skeleton h-24 w-full rounded-xl" />
        <div className="space-y-2">
          <div className="skeleton h-8 w-full rounded" />
          <div className="skeleton h-8 w-full rounded" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-5 bg-[#111118] border border-[#1e1e2a] rounded-2xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-display text-sm font-700 text-white">API Latency</h3>
          <p className="text-zinc-600 text-[11px] font-mono mt-0.5">{count.toLocaleString()} samples</p>
        </div>
        <div className={clsx(
          "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono border",
          meetsSLA
            ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
            : "bg-red-500/10 border-red-500/20 text-red-400"
        )}>
          <span className={clsx("w-1.5 h-1.5 rounded-full animate-pulse-dot", meetsSLA ? "bg-emerald-400" : "bg-red-400")} />
          {meetsSLA ? "SLA ✓" : "SLA ✗"}
        </div>
      </div>

      {/* p99 Arc Gauge */}
      <div className="flex flex-col items-center mb-4">
        <div className="relative">
          <Arc value={p99} max={slaTarget} color={p99Color} radius={56} />
          <div className="absolute inset-0 flex flex-col items-center justify-end pb-1">
            <motion.span
              key={p99}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="font-display text-2xl font-800"
              style={{ color: p99Color }}
            >
              {p99.toFixed(0)}
            </motion.span>
            <span className="text-zinc-600 text-[10px] font-mono">ms p99</span>
          </div>
        </div>
        <div className="flex justify-between w-full text-[10px] text-zinc-600 font-mono -mt-1">
          <span>0ms</span>
          <span className="text-zinc-700">SLA {slaTarget}ms</span>
          <span>{slaTarget * 2}ms</span>
        </div>
      </div>

      {/* p50 / p95 bars */}
      <div className="space-y-2.5">
        <GaugePill label="p50" value={p50} target={slaTarget} color="#10b981" />
        <GaugePill label="p95" value={p95} target={slaTarget} color="#f59e0b" />
        <GaugePill label="p99" value={p99} target={slaTarget} color={p99Color} />
      </div>
    </div>
  );
}
