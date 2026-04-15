"use client";
import { motion } from "framer-motion";
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip } from "recharts";
import { clsx } from "clsx";

const FAIRNESS_DATA = [
  { metric: "Seg. Parity",  score: 94 },
  { metric: "Price Range",  score: 88 },
  { metric: "Margin Equal", score: 97 },
  { metric: "No Demo Bias", score: 100 },
  { metric: "Audit Trail",  score: 100 },
  { metric: "Rule Coverage",score: 96 },
];

const SEGMENT_AUDIT = [
  { segment: "New Visitor",    avgDiscount: 4.2,  sampleSize: 1284 },
  { segment: "Returning",      avgDiscount: 2.1,  sampleSize: 3891 },
  { segment: "Member",         avgDiscount: 7.8,  sampleSize: 945  },
  { segment: "VIP",            avgDiscount: 0.0,  sampleSize: 234  },
  { segment: "Saver",          avgDiscount: 8.9,  sampleSize: 567  },
];

export function FairnessPanel() {
  const overallScore = Math.round(
    FAIRNESS_DATA.reduce((s, d) => s + d.score, 0) / FAIRNESS_DATA.length
  );

  return (
    <div className="p-5 bg-[#111118] border border-[#1e1e2a] rounded-2xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-display text-sm font-700 text-white">Fairness Audit</h3>
          <p className="text-zinc-600 text-[11px] font-mono mt-0.5">Pricing equity check</p>
        </div>
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="flex flex-col items-center"
        >
          <span className="font-display text-3xl font-800 text-emerald-400">{overallScore}</span>
          <span className="text-emerald-600 text-[10px] font-mono">/ 100</span>
        </motion.div>
      </div>

      {/* Radar */}
      <ResponsiveContainer width="100%" height={180}>
        <RadarChart data={FAIRNESS_DATA}>
          <PolarGrid stroke="#1e1e2a" />
          <PolarAngleAxis
            dataKey="metric"
            tick={{ fill: "#52525b", fontSize: 10, fontFamily: "var(--font-mono)" }}
          />
          <Radar
            dataKey="score"
            stroke="#10b981"
            fill="#10b981"
            fillOpacity={0.15}
            strokeWidth={1.5}
          />
        </RadarChart>
      </ResponsiveContainer>

      {/* Per-segment discount table */}
      <div>
        <p className="text-zinc-600 text-[10px] font-mono uppercase tracking-wider mb-2">
          Avg Discount by Behavioural Segment
        </p>
        <div className="space-y-1.5">
          {SEGMENT_AUDIT.map(({ segment, avgDiscount, sampleSize }) => (
            <div key={segment} className="flex items-center gap-2">
              <span className="text-zinc-400 text-[11px] w-24 flex-shrink-0">{segment}</span>
              <div className="flex-1 h-1.5 bg-[#1a1a26] rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${(avgDiscount / 15) * 100}%` }}
                  transition={{ duration: 0.6, ease: "easeOut", delay: 0.1 }}
                  className="h-full bg-emerald-500 rounded-full"
                />
              </div>
              <span className="text-emerald-400 font-mono text-[11px] w-10 text-right">
                -{avgDiscount.toFixed(1)}%
              </span>
              <span className="text-zinc-700 font-mono text-[10px] w-12 text-right">
                n={sampleSize}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Compliance badges */}
      <div className="flex flex-wrap gap-1.5 pt-2 border-t border-[#1e1e2a]">
        {[
          "No demographic signals",
          "Business rules enforced",
          "All prices explainable",
          "Audit log complete",
        ].map((label) => (
          <span
            key={label}
            className="px-2 py-0.5 bg-emerald-500/10 text-emerald-600 border border-emerald-500/15 rounded-full text-[10px] font-mono"
          >
            ✓ {label}
          </span>
        ))}
      </div>
    </div>
  );
}
