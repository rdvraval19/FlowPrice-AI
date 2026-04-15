"use client";
// frontend/src/components/vendor/SponsorCard.tsx
//
// FIX: Added live product search/autocomplete so vendors always pick a real
// SKU ID (e.g. "SKU001000") instead of typing freeform text like "NEW PRODUCT".
// The root bug was: sponsor Redis key = "sponsor:NEW PRODUCT" but catalog
// checks "sponsor:SKU001000" — they never matched, so no badge appeared.

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { clsx } from "clsx";
import { sponsorProduct, revokeSponsor, SponsorResponse } from "@/lib/vendor-api";
import { fetchCatalog } from "@/lib/api-client";
import { CatalogProduct } from "@/types";

// ── Product search autocomplete ───────────────────────────────────────────────
function ProductSearch({
  value,
  onChange,
}: {
  value: string;
  onChange: (id: string, name: string) => void;
}) {
  const [query, setQuery]           = useState(value);
  const [results, setResults]       = useState<CatalogProduct[]>([]);
  const [open, setOpen]             = useState(false);
  const [searching, setSearching]   = useState(false);
  const [selectedName, setSelectedName] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const wrapperRef  = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const search = async (q: string) => {
    if (!q.trim()) { setResults([]); setOpen(false); return; }
    setSearching(true);
    try {
      // Fetch up to 50 products, then filter client-side by name/id
      const data = await fetchCatalog({ page: 1, perPage: 50 });
      const filtered: CatalogProduct[] = (data.products || []).filter(
        (p: CatalogProduct) =>
          p.id.toLowerCase().includes(q.toLowerCase()) ||
          p.name.toLowerCase().includes(q.toLowerCase()) ||
          p.brand.toLowerCase().includes(q.toLowerCase())
      );
      setResults(filtered.slice(0, 8));
      setOpen(filtered.length > 0);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const q = e.target.value;
    setQuery(q);
    setSelectedName("");
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(q), 300);
  };

  const handleSelect = (p: CatalogProduct) => {
    setQuery(p.id);
    setSelectedName(p.name);
    setOpen(false);
    onChange(p.id, p.name);
  };

  return (
    <div ref={wrapperRef} className="relative">
      <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">
        Product ID
      </label>
      <div className="relative">
        <input
          value={query}
          onChange={handleInput}
          onFocus={() => query && results.length > 0 && setOpen(true)}
          placeholder="Search by name, brand or SKU…"
          className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2 text-white text-xs font-mono placeholder:text-zinc-700 focus:outline-none focus:border-yellow-500/40 transition-colors pr-8"
        />
        {searching && (
          <div className="absolute right-2.5 top-1/2 -translate-y-1/2">
            <div className="w-3 h-3 border border-yellow-400/40 border-t-yellow-400 rounded-full animate-spin" />
          </div>
        )}
      </div>

      {/* Validated SKU pill */}
      {selectedName && (
        <p className="text-yellow-400/70 text-[10px] font-mono mt-1">
          ✓ {selectedName}
        </p>
      )}

      {/* Dropdown */}
      <AnimatePresence>
        {open && results.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="absolute z-50 top-full mt-1 w-full bg-[#111118] border border-[#1e1e2a] rounded-xl overflow-hidden shadow-xl"
          >
            {results.map((p) => (
              <button
                key={p.id}
                onClick={() => handleSelect(p)}
                className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-yellow-500/5 transition-colors text-left group"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-white text-[11px] font-mono truncate group-hover:text-yellow-300 transition-colors">
                    {p.name}
                  </p>
                  <p className="text-zinc-600 text-[9px] font-mono">
                    {p.id} · {p.brand} · {p.category}
                  </p>
                </div>
                <span className="text-zinc-700 text-[9px] font-mono shrink-0">
                  ₹{Math.round(p.base_price * 83).toLocaleString("en-IN")}
                </span>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Main SponsorCard ──────────────────────────────────────────────────────────
export function SponsorCard() {
  const [productId, setProductId]         = useState("");
  const [productName, setProductName]     = useState("");
  const [durationHours, setDurationHours] = useState("24");
  const [badgeLabel, setBadgeLabel]       = useState("Sponsored");
  const [status, setStatus]               = useState<"idle"|"loading"|"success"|"error">("idle");
  const [result, setResult]               = useState<SponsorResponse | null>(null);
  const [error, setError]                 = useState("");
  const [revoking, setRevoking]           = useState(false);

  const handleSelect = (id: string, name: string) => {
    setProductId(id);
    setProductName(name);
    // Reset state if vendor picks a new product
    if (id !== productId) {
      setResult(null);
      setStatus("idle");
    }
  };

  const handleSponsor = async () => {
    if (!productId) return;
    setStatus("loading");
    setError("");
    try {
      const data = await sponsorProduct({
        product_id: productId,
        duration_hours: Number(durationHours),
        badge_label: badgeLabel,
      });
      setResult(data);
      setStatus("success");
    } catch (e: any) {
      setError(e.message);
      setStatus("error");
    }
  };

  const handleRevoke = async () => {
    if (!result?.product_id) return;
    setRevoking(true);
    try {
      await revokeSponsor(result.product_id);
      setResult(null);
      setStatus("idle");
      setProductId("");
      setProductName("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRevoking(false);
    }
  };

  const BADGE_OPTIONS = ["Sponsored", "Featured", "Hot Deal", "Top Pick", "Staff Pick"];
  const isReady = !!productId && productId.startsWith("SKU");

  return (
    <div className="p-5 bg-[#111118] border border-[#1e1e2a] rounded-2xl space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-yellow-500/10 border border-yellow-500/20 flex items-center justify-center text-yellow-400 text-base">
          ⭐
        </div>
        <div>
          <h3 className="font-display text-sm font-700 text-white">Sponsor Product</h3>
          <p className="text-zinc-600 text-[10px] font-mono">Add badge · shown with priority in storefront</p>
        </div>
      </div>

      {/* Form */}
      <div className="space-y-2.5">
        {/* 🔑 FIX: Live product search instead of freeform text input */}
        <ProductSearch value={productId} onChange={handleSelect} />

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">
              Duration (hours)
            </label>
            <input
              value={durationHours}
              onChange={e => setDurationHours(e.target.value)}
              type="number" min={1} max={720}
              className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2 text-white text-xs font-mono focus:outline-none focus:border-yellow-500/40 transition-colors"
            />
          </div>
          <div>
            <label className="text-zinc-500 text-[10px] font-mono uppercase tracking-wider block mb-1">
              Badge Label
            </label>
            <select
              value={badgeLabel}
              onChange={e => setBadgeLabel(e.target.value)}
              className="w-full bg-[#0d0d14] border border-[#1e1e2a] rounded-lg px-3 py-2 text-white text-xs font-mono focus:outline-none focus:border-yellow-500/40 transition-colors"
            >
              {BADGE_OPTIONS.map(b => <option key={b}>{b}</option>)}
            </select>
          </div>
        </div>

        {/* Badge Preview */}
        {productId && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className={clsx(
              "flex items-center gap-3 px-3 py-2.5 rounded-lg border",
              isReady
                ? "bg-yellow-500/5 border-yellow-500/15"
                : "bg-red-500/5 border-red-500/15"
            )}
          >
            <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center text-zinc-600 text-xs font-mono">
              IMG
            </div>
            <div className="flex-1">
              <p className="text-white text-xs font-mono">{productName || productId}</p>
              <p className={clsx("text-[10px] font-mono", isReady ? "text-zinc-600" : "text-red-400/70")}>
                {isReady
                  ? `${productId} · ${durationHours}h sponsorship`
                  : "⚠ Select a product from the search above"}
              </p>
            </div>
            {isReady && (
              <span className="px-2 py-0.5 bg-yellow-400/20 text-yellow-400 text-[10px] font-mono rounded-full border border-yellow-400/30">
                ⭐ {badgeLabel}
              </span>
            )}
          </motion.div>
        )}

        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={handleSponsor}
          disabled={status === "loading" || !isReady}
          className={clsx(
            "w-full py-2.5 rounded-xl font-display font-700 text-sm transition-all",
            status === "loading" || !isReady
              ? "bg-yellow-500/20 text-yellow-400/50 cursor-not-allowed"
              : "bg-yellow-400 text-black hover:bg-yellow-300"
          )}
        >
          {status === "loading" ? "Sponsoring…" : "⭐ Mark as Sponsored"}
        </motion.button>

        {/* Hint when no valid product selected */}
        {productId && !isReady && (
          <p className="text-center text-red-400/60 text-[10px] font-mono">
            Product ID must start with SKU — use the search above
          </p>
        )}
      </div>

      {/* Result */}
      <AnimatePresence>
        {status === "success" && result && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="p-3 bg-yellow-500/8 border border-yellow-500/20 rounded-xl space-y-2"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-yellow-400 text-xs font-mono font-700">✓ {result.badge_label}</span>
                <span className="px-2 py-0.5 bg-yellow-400/20 text-yellow-400 text-[10px] font-mono rounded-full border border-yellow-400/30">
                  LIVE
                </span>
              </div>
              <button
                onClick={handleRevoke}
                disabled={revoking}
                className="text-red-400 text-[10px] font-mono hover:text-red-300 transition-colors"
              >
                {revoking ? "Revoking…" : "✕ Revoke"}
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2 text-center">
              <div className="bg-black/20 rounded-lg p-2">
                <div className="text-white text-xs font-mono font-700">{result.product_id}</div>
                <div className="text-zinc-600 text-[9px] font-mono">Product ID</div>
              </div>
              <div className="bg-black/20 rounded-lg p-2">
                <div className="text-yellow-400 text-xs font-mono font-700">
                  {new Date(result.sponsored_until).toLocaleDateString("en-IN")}
                </div>
                <div className="text-zinc-600 text-[9px] font-mono">Active until</div>
              </div>
            </div>
          </motion.div>
        )}
        {status === "error" && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-[11px] font-mono"
          >
            ⚠ {error}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}