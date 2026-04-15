// lib/currency.ts — Indian Rupee formatting + USD→INR conversion
// The organizer dataset uses USD. We display in INR (Indian market story).
// Conversion rate: 1 USD = 83 INR (approximate, mid-2024)

export const USD_TO_INR = 83;

/** Convert a USD price to INR */
export const usdToInr = (usd: number): number => Math.round(usd * USD_TO_INR);

/** Format a number already in INR */
export const formatINR = (amount: number): string =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);

/** Convert USD → INR and format in one call */
export const formatUSDasINR = (usd: number): string => formatINR(usdToInr(usd));

/** Compact: ₹1.5L, ₹25K — for revenue tickers and dashboard KPIs */
export const formatINRCompact = (amount: number): string => {
  if (amount >= 10_00_000) return `₹${(amount / 10_00_000).toFixed(2)}Cr`;
  if (amount >= 1_00_000)  return `₹${(amount / 1_00_000).toFixed(1)}L`;
  if (amount >= 1_000)     return `₹${(amount / 1_000).toFixed(0)}K`;
  return formatINR(amount);
};

/** Signed diff: +₹1,200 or -₹800 */
export const formatINRDiff = (diff: number): string =>
  `${diff >= 0 ? "+" : ""}${formatINR(diff)}`;

export const INR_SYMBOL = "₹";
