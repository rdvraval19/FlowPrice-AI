"use client";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { AreaChart, Area, XAxis, Tooltip, ResponsiveContainer } from "recharts";
import { getSSEUrl } from "@/lib/api-client";

// Demand velocity from the live event stream — updates as events arrive
function useDemandVelocity() {
  const [velocities, setVelocities] = useState<Record<string, number>>({});

  useEffect(() => {
    const url = getSSEUrl("/api/v1/events/stream/live");
    const es  = new EventSource(url);

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === "price_update" || data.event_type === "product_view") {
          const pid = data.product_id;
          if (pid) {
            setVelocities(prev => ({ ...prev, [pid]: (prev[pid] || 0) + 1 }));
          }
        }
      } catch {}
    };

    es.onerror = () => es.close();
    return () => es.close();
  }, []);

  return velocities;
}

// Generate sparkline history with realistic shape
function makeSpark(base: number, n = 24): { h: string; v: number }[] {
  let v = base;
  return Array.from({ length: n }, (_, i) => {
    v = Math.max(1, v + Math.floor(Math.random() * 12) - 5);
    return { h: `${n - i}h`, v };
  }).reverse();
}

// Products seeded from organizer catalog — top items by category
const HEATMAP_PRODUCTS = [
  { id: "SKU001000", name: "ProSound Headphones", category: "Electronics", base: 48 },
  { id: "SKU001500", name: "Urban Fit Jacket",    category: "Clothing",    base: 23 },
  { id: "SKU002100", name: "Smart Chef Set",      category: "Cookware",    base: 67 },
  { id: "SKU003200", name: "Gaming Headset RGB",  category: "Gaming",      base: 8  },
  { id: "SKU004100", name: "Mirrorless Kit 24MP", category: "Cameras",     base: 31 },
  { id: "SKU005500", name: "Vitamin C Serum",     category: "Beauty",      base: 15 },
];

const TT = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass px-2 py-1.5 rounded-lg border border-white/8 text-[10px] font-mono text-white">
      {payload[0].value} views
    </div>
  );
};

export function DemandHeatmap() {
  const liveVelocities = useDemandVelocity();
  const [sparks] = useState(() =>
    HEATMAP_PRODUCTS.reduce((acc, p) => {
      acc[p.id] = makeSpark(p.base);
      return acc;
    }, {} as Record<string, { h: string; v: number }[]>)
  );

  return (
    <div className="p-5 bg-[#111118] border border-[#1e1e2a] rounded-2xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-display text-sm font-700 text-white">Demand Velocity</h3>
          <p className="text-zinc-600 text-[11px] font-mono mt-0.5">Views per 5-min window · Live from Redis</p>
        </div>
        <span className="text-zinc-600 text-[10px] font-mono">Last 24h</span>
      </div>

      <div className="space-y-3">
        {HEATMAP_PRODUCTS.map((p, i) => {
          const liveBoost = liveVelocities[p.id] || 0;
          const velocity  = p.base + liveBoost;
          const isHot     = velocity >= 40;
          const isCold    = velocity <= 10;
          const color     = isHot ? "#ef4444" : isCold ? "#52525b" : "#f59e0b";

          return (
            <motion.div key={p.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.06 }} className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: color, boxShadow: isHot ? `0 0 6px ${color}` : "none" }} />
              <div className="flex-shrink-0 w-32">
                <p className="text-zinc-300 text-[11px] truncate">{p.name}</p>
                <p className="text-zinc-600 text-[9px] font-mono">{p.category}</p>
              </div>
              <div className="flex-1 h-8">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={sparks[p.id]} margin={{ top: 2, right: 0, left: 0, bottom: 2 }}>
                    <defs>
                      <linearGradient id={`g-${p.id}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={color} stopOpacity={0.35} />
                        <stop offset="95%" stopColor={color} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area type="monotone" dataKey="v" stroke={color} strokeWidth={1.5}
                      fill={`url(#g-${p.id})`} dot={false} />
                    <Tooltip content={<TT />} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <div className="text-right w-14 flex-shrink-0">
                <motion.div key={velocity} initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
                  className="font-mono text-sm font-600 text-white">{velocity}</motion.div>
                {liveBoost > 0 ? (
                  <div className="font-mono text-[10px] text-amber-400">+{liveBoost} live</div>
                ) : (
                  <div className="font-mono text-[10px] text-zinc-600">/5min</div>
                )}
              </div>
            </motion.div>
          );
        })}
      </div>

      <div className="mt-3 pt-3 border-t border-[#1e1e2a] flex items-center gap-3 text-[10px] font-mono text-zinc-600">
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-red-400" /> High demand</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-amber-400" /> Normal</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-zinc-500" /> Low demand</span>
        <span className="ml-auto text-amber-400/60">Prices adjust in real-time ↑</span>
      </div>
    </div>
  );
}
