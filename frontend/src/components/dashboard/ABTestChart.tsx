"use client";
import { motion } from "framer-motion";
import {
  BarChart, Bar, XAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { ExperimentResult } from "@/types";
import { formatINR, formatINRCompact, usdToInr } from "@/lib/currency";
import { clsx } from "clsx";

const VARIANT_COLORS: Record<string, string> = {
  control:   "#52525b",
  treatment: "#f59e0b",
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass px-3 py-2 rounded-xl border border-white/8 text-xs space-y-1">
      <p className="text-zinc-400 font-mono">{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ color: p.color }} className="font-mono">
          {p.name}: {p.name === "Conv. Rate" ? `${Number(p.value).toFixed(2)}%` : formatINR(p.value)}
        </p>
      ))}
    </div>
  );
};

// Compute lift % between treatment and control
function computeLift(treatment: number, control: number): string {
  if (control === 0) return "—";
  const lift = ((treatment - control) / control) * 100;
  return `${lift >= 0 ? "+" : ""}${lift.toFixed(1)}%`;
}

interface ABTestChartProps {
  experiment: ExperimentResult;
  loading?: boolean;
}

export function ABTestChart({ experiment, loading = false }: ABTestChartProps) {
  if (loading) {
    return (
      <div className="p-5 bg-[#111118] border border-[#1e1e2a] rounded-2xl space-y-4">
        <div className="skeleton h-4 w-48 rounded" />
        <div className="skeleton h-40 w-full rounded-xl" />
      </div>
    );
  }

  const variantIds = Object.keys(experiment.variants);
  const sig        = experiment.statistical_significance;
  const hasData    = variantIds.some(id => experiment.variants[id].impressions > 0);

  const control   = experiment.variants["control"];
  const treatment = experiment.variants["treatment"];

  // Convert USD metrics → INR for display
  const convData = variantIds.map(id => ({
    name: id,
    "Conv. Rate": +(experiment.variants[id].conversion_rate * 100).toFixed(2),
  }));
  const aovData = variantIds.map(id => ({
    name: id,
    AOV: usdToInr(experiment.variants[id].aov),
  }));
  const rpsData = variantIds.map(id => ({
    name: id,
    RPS: usdToInr(experiment.variants[id].rps),
  }));

  return (
    <div className="p-5 bg-[#111118] border border-[#1e1e2a] rounded-2xl space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-sm font-700 text-white">{experiment.name}</h3>
          <div className="flex items-center gap-2 mt-0.5">
            <span className={clsx("w-1.5 h-1.5 rounded-full",
              experiment.status === "running" ? "bg-emerald-400 animate-pulse" : "bg-zinc-500")} />
            <p className="text-zinc-600 text-[10px] font-mono capitalize">{experiment.status}</p>
          </div>
        </div>

        <div className="flex flex-col items-end gap-1">
          {!hasData ? (
            <div className="flex flex-col items-end gap-1">
              <span className="px-2.5 py-1 bg-zinc-800/80 text-zinc-400 text-[10px] font-mono rounded-full border border-zinc-700/50">
                ⏳ Collecting data…
              </span>
              <span className="text-zinc-600 text-[9px] font-mono">
                Run: python scripts/seed_from_organizer_data.py --ab-seed-only
              </span>
            </div>
          ) : sig.is_significant ? (
            <span className="px-2.5 py-1 bg-emerald-500/15 text-emerald-400 text-[10px] font-mono rounded-full border border-emerald-500/20">
              ✓ Significant · {sig.confidence.toFixed(0)}% confidence
            </span>
          ) : (
            <span className="px-2.5 py-1 bg-zinc-800 text-zinc-500 text-[10px] font-mono rounded-full">
              p={sig.p_value != null ? sig.p_value.toFixed(3) : "—"} · need more data
            </span>
          )}
          {experiment.winner && (
            <span className="text-amber-400 text-[10px] font-mono">🏆 Winner: {experiment.winner}</span>
          )}
        </div>
      </div>

      {/* Variant metric cards */}
      <div className="grid grid-cols-2 gap-2">
        {variantIds.map(id => {
          const m        = experiment.variants[id];
          const isWinner = experiment.winner === id;
          const aovInr   = usdToInr(m.aov);
          const rpsInr   = usdToInr(m.rps);
          return (
            <div key={id}
              className={clsx("p-3 rounded-xl border text-center",
                isWinner ? "bg-amber-400/5 border-amber-400/20" : "bg-[#161620] border-[#1e1e2a]")}>
              <div className="text-[10px] font-mono text-zinc-500 mb-1.5 capitalize">
                {id} {isWinner && "★"}
              </div>
              <div className="font-display text-2xl font-800"
                style={{ color: VARIANT_COLORS[id] || "#f59e0b" }}>
                {m.impressions > 0 ? `${(m.conversion_rate * 100).toFixed(1)}%` : "—"}
              </div>
              <div className="text-zinc-600 text-[9px] font-mono">conversion rate</div>
              <div className="mt-2 space-y-0.5">
                <div className="text-xs font-mono text-white">
                  {aovInr > 0 ? formatINR(aovInr) : "—"} AOV
                </div>
                <div className="text-[10px] font-mono text-zinc-500">
                  {rpsInr > 0 ? formatINR(rpsInr) : "—"} / session
                </div>
                <div className="text-[10px] font-mono text-zinc-600">
                  {m.impressions.toLocaleString("en-IN")} impressions
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Lift indicators */}
      {hasData && control && treatment && (
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: "Conv. Lift",  value: computeLift(treatment.conversion_rate, control.conversion_rate) },
            { label: "AOV Lift",    value: computeLift(treatment.aov, control.aov) },
            { label: "Revenue/Ses", value: computeLift(treatment.rps, control.rps) },
          ].map(item => {
            const positive = item.value.startsWith("+");
            const neutral  = item.value === "—";
            return (
              <div key={item.label}
                className={clsx("text-center p-2 rounded-lg border",
                  neutral ? "bg-zinc-800/50 border-zinc-700/30" :
                  positive ? "bg-emerald-500/10 border-emerald-500/20" :
                             "bg-red-500/10 border-red-500/20")}>
                <div className={clsx("font-display text-base font-700",
                  neutral ? "text-zinc-500" : positive ? "text-emerald-400" : "text-red-400")}>
                  {item.value}
                </div>
                <div className="text-zinc-600 text-[9px] font-mono mt-0.5">{item.label}</div>
              </div>
            );
          })}
        </div>
      )}

      {/* Bar charts */}
      {hasData && (
        <div className="grid grid-cols-3 gap-2">
          {[
            { data: convData, key: "Conv. Rate", label: "Conv. Rate (%)" },
            { data: aovData,  key: "AOV",        label: "Avg Order Value" },
            { data: rpsData,  key: "RPS",        label: "Revenue/Session" },
          ].map(({ data, key, label }) => (
            <div key={key}>
              <p className="text-zinc-600 text-[9px] font-mono mb-1 text-center">{label}</p>
              <ResponsiveContainer width="100%" height={70}>
                <BarChart data={data} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                  <XAxis dataKey="name" tick={{ fill: "#52525b", fontSize: 8 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                  <Bar dataKey={key} radius={[3, 3, 0, 0]}>
                    {variantIds.map(id => (
                      <Cell key={id} fill={VARIANT_COLORS[id] || "#f59e0b"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ))}
        </div>
      )}

      {!hasData && (
        <div className="py-6 text-center">
          <p className="text-zinc-600 text-xs font-mono mb-2">No data yet</p>
          <p className="text-zinc-700 text-[10px] font-mono">
            Quick fix: <code className="bg-black/30 px-1 rounded">python scripts/seed_from_organizer_data.py --ab-seed-only</code>
          </p>
        </div>
      )}
    </div>
  );
}

//abtestchart