"use client";
// components/storefront/LoyaltyBadge.tsx
// Shows tier badge, points total, and progress to next tier.
// Drop anywhere in the storefront — it reads token from sessionStore.

import { motion } from "framer-motion";
import { useLoyalty } from "@/hooks/useLoyalty";
import type { LoyaltyTier } from "@/types";

const TIER_COLORS: Record<LoyaltyTier, { bg: string; text: string; border: string; icon: string }> = {
  bronze:   { bg: "#7c3f1f22", text: "#cd7f32", border: "#cd7f3240", icon: "🥉" },
  silver:   { bg: "#c0c0c022", text: "#a8a9ad", border: "#c0c0c040", icon: "🥈" },
  gold:     { bg: "#ffd70022", text: "#ffd700", border: "#ffd70040", icon: "🥇" },
  platinum: { bg: "#e5e4e222", text: "#e5e4e2", border: "#e5e4e240", icon: "💎" },
};

interface LoyaltyBadgeProps {
  token: string | null;
  sessionId?: string;
  compact?: boolean; // true = small inline badge, false = full card
}

export function LoyaltyBadge({ token, sessionId, compact = false }: LoyaltyBadgeProps) {
  const { balance, loading } = useLoyalty({ token, sessionId });

  // Guard against missing or invalid tokens
  if (!token || token.length < 10) return null;

  // Loading skeleton
  if (loading && !balance) {
    return (
      <div 
        aria-busy="true"
        style={{
          width: compact ? 80 : 180, 
          height: compact ? 24 : 72,
          borderRadius: 8, 
          background: "#1e1e2a", 
          opacity: 0.6,
          animation: "pulse 1.5s ease-in-out infinite",
        }} 
      />
    );
  }

  // Guard against missing balance data after loading
  if (!balance) return null;

  const colors = TIER_COLORS[balance.tier] ?? TIER_COLORS.bronze;
  
  // Safely calculate progress percentage to avoid NaN (division by zero)
  const totalRequired = balance.total_points + (balance.points_to_next_tier ?? 0);
  const progressPct = balance.points_to_next_tier != null && totalRequired > 0
    ? Math.min(100, (balance.total_points / totalRequired) * 100)
    : 100;

  // Compact layout
  if (compact) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          padding: "3px 10px", borderRadius: 20,
          background: colors.bg, border: `1px solid ${colors.border}`,
          color: colors.text, fontSize: 11, fontFamily: "monospace",
          fontWeight: 600, cursor: "default",
        }}
        title={`${balance.total_points} pts · ${balance.tier_benefit}`}
      >
        <span>{colors.icon}</span>
        <span style={{ textTransform: "capitalize" }}>{balance.tier}</span>
        <span style={{ opacity: 0.7 }}>· {balance.total_points} pts</span>
      </motion.div>
    );
  }

  // Full card layout
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        padding: "14px 16px", borderRadius: 14,
        background: colors.bg, border: `1px solid ${colors.border}`,
        minWidth: 200,
      }}
    >
      {/* Tier header */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 20 }} aria-hidden="true">{colors.icon}</span>
        <div>
          <p style={{
            color: colors.text, fontWeight: 700, fontSize: 13,
            textTransform: "capitalize", margin: 0,
          }}>
            {balance.tier} Member
          </p>
          <p style={{ color: colors.text, opacity: 0.7, fontSize: 10, fontFamily: "monospace", margin: 0 }}>
            {balance.total_points.toLocaleString("en-IN")} pts total
          </p>
        </div>
        
        {/* Session points badge */}
        {balance.session_points > 0 && (
          <motion.span
            initial={{ opacity: 0, x: 4 }}
            animate={{ opacity: 1, x: 0 }}
            style={{
              marginLeft: "auto", padding: "2px 8px", borderRadius: 10,
              background: "#10b98122", color: "#10b981",
              fontSize: 10, fontFamily: "monospace", fontWeight: 600,
            }}
          >
            +{balance.session_points} today
          </motion.span>
        )}
      </div>

      {/* Progress bar */}
      {balance.points_to_next_tier != null && (
        <div>
          <div 
            role="progressbar" 
            aria-valuenow={progressPct} 
            aria-valuemin={0} 
            aria-valuemax={100}
            style={{
              height: 4, background: "#ffffff15", borderRadius: 2, overflow: "hidden",
            }}
          >
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${progressPct}%` }}
              transition={{ duration: 0.8, ease: "easeOut" }}
              style={{ height: "100%", background: colors.text, borderRadius: 2 }}
            />
          </div>
          <p style={{ color: colors.text, opacity: 0.6, fontSize: 10, fontFamily: "monospace", marginTop: 4, marginBottom: 0 }}>
            {balance.points_to_next_tier} pts to next tier
          </p>
        </div>
      )}

      {/* Platinum / Max tier fallback */}
      {balance.points_to_next_tier == null && (
        <p style={{ color: colors.text, opacity: 0.7, fontSize: 10, fontFamily: "monospace", margin: 0 }}>
          ✦ Max tier — {balance.tier_benefit}
        </p>
      )}
    </motion.div>
  );
}