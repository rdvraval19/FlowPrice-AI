"use client";
import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { clsx } from "clsx";
import { Product, PricingResponse } from "@/types";
import { PriceDisplay, PriceDisplaySkeleton } from "./PriceDisplay";
import { useSessionStore } from "@/store/session";
import { useEventTracker } from "@/hooks/useEventTracker";
import { formatINR, usdToInr } from "@/lib/currency";
import { getMockProductImage } from "@/lib/images";

// ── Drop Countdown (scarce items only) ───────────────────────────────────────
function DropTimer({ inventoryLevel }: { inventoryLevel: number }) {
  const [secs, setSecs] = useState(480);
  useEffect(() => {
  // Runs only on client, after hydration — safe to randomize here
  setSecs(180 + Math.floor(Math.random() * 600));
  }, []);
  useEffect(() => {
    if (inventoryLevel > 15) return;
    const t = setInterval(() => setSecs(s => Math.max(0, s - 1)), 1000);
    return () => clearInterval(t);
  }, [inventoryLevel]);
  if (inventoryLevel > 15) return null;
  const m = Math.floor(secs / 60), s = secs % 60;
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg"
      style={{ background: "var(--orange-bg)", color: "var(--orange)" }}>
      <span className="w-1 h-1 rounded-full animate-pulse" style={{ background: "var(--orange)" }} />
      <span className="text-[10px] font-mono font-600">
        Price locks in {m}:{String(s).padStart(2, "0")}
      </span>
    </div>
  );
}

interface ProductCardProps {
  product: Product;
  pricing: PricingResponse | null;
  pricingLoading?: boolean;
  index?: number;
  onProductClick?: (product: Product) => void;
}

export function ProductCard({
  product, pricing, pricingLoading = false, index = 0, onProductClick,
}: ProductCardProps) {
  const [addedToCart, setAddedToCart]   = useState(false);
  const [selectedSize, setSelectedSize] = useState<string | null>(null);
  const [flashClass, setFlashClass]     = useState("");
  const [imgError, setImgError]         = useState(false);
  const prevPriceRef = useRef<number | null>(null);
  const { addToCart } = useSessionStore();
  const { trackCartAdd, trackProductView } = useEventTracker();

  // Determine image: use catalog url if valid, else deterministic from category pool
  const imageSrc = (!imgError && product.image_url && !product.image_url.includes("placeholder"))
    ? product.image_url
    : getMockProductImage(product.id, product.category);

  // Price direction flash animation
  useEffect(() => {
    if (!pricing) return;
    if (prevPriceRef.current !== null && prevPriceRef.current !== pricing.final_price) {
      const cls = pricing.final_price < prevPriceRef.current ? "animate-flash-green" : "animate-flash-red";
      setFlashClass(cls);
      setTimeout(() => setFlashClass(""), 800);
    }
    prevPriceRef.current = pricing.final_price;
  }, [pricing?.final_price]);

  const handleAdd = (e: React.MouseEvent) => {
    e.stopPropagation();
    const size  = selectedSize || product.sizes[Math.floor(product.sizes.length / 2)] || "One Size";
    const price = pricing?.final_price ?? product.base_price;
    addToCart(product, size, price);
    trackCartAdd(product.id, product.category, price, product.base_price);
    setAddedToCart(true);
    setTimeout(() => setAddedToCart(false), 2000);
  };

  const handleClick = () => {
    const price = pricing?.final_price ?? product.base_price;
    trackProductView(product.id, product.category, price, product.base_price);
    onProductClick?.(product);
  };

  const inventoryLow  = product.inventory_level > 0 && product.inventory_level <= 10;
  const isSurge       = (pricing?.discount_pct ?? 0) < -0.5;
  const isDiscount    = (pricing?.discount_pct ?? 0) > 0.5;
  const priceInr      = pricing ? usdToInr(pricing.final_price) : usdToInr(product.base_price);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
      onClick={handleClick}
      className={clsx("product-card cursor-pointer overflow-hidden", flashClass)}
    >
      {/* ── Image container ─────────────────────────────────────────────── */}
      <div className="relative overflow-hidden" style={{ aspectRatio: "1/1", background: "#F8FAFC" }}>
        <img
          src={imageSrc}
          alt={product.name}
          onError={() => setImgError(true)}
          className="product-image"
          loading="lazy"
        />

        {/* Gradient overlay for text readability */}
        <div className="absolute inset-x-0 bottom-0 h-16"
          style={{ background: "linear-gradient(to top, rgba(0,0,0,0.08), transparent)" }} />

        {/* ── Tag chips ── */}
        <div className="absolute top-2 left-2 flex flex-col gap-1">
          {product.is_sponsored && (
            <span
              className="px-2 py-0.5 text-[10px] font-700 font-display rounded-full"
              style={{ background: "#facc15", color: "#000" }}
            >
              ⭐ SPONSORED
            </span>
          )}
          {product.is_new && (
            <span className="px-2 py-0.5 text-[10px] font-700 font-display rounded-full"
              style={{ background: "var(--indigo)", color: "#fff" }}>
              NEW
            </span>
          )}
          {inventoryLow && (
            <span className="px-2 py-0.5 text-[10px] font-mono rounded-full"
              style={{ background: "var(--red-bg)", color: "var(--red)", border: "1px solid rgba(239,68,68,0.2)" }}>
              {product.inventory_level} left
            </span>
          )}
          {isSurge && (
            <span className="px-2 py-0.5 text-[10px] font-mono rounded-full"
              style={{ background: "var(--red-bg)", color: "var(--red)", border: "1px solid rgba(239,68,68,0.2)" }}>
              ↑ High Demand
            </span>
          )}
          {isDiscount && !product.is_new && (
            <span className="px-2 py-0.5 text-[10px] font-mono rounded-full"
              style={{ background: "var(--green-bg)", color: "var(--green)", border: "1px solid rgba(16,185,129,0.2)" }}>
              ↓ Price Drop
            </span>
          )}
        </div>

        {/* ── Size quick-select ── */}
        <AnimatePresence>
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            whileHover={{ opacity: 1, y: 0 }}
            className="absolute bottom-2 inset-x-2 flex gap-1 justify-center opacity-0 group-hover:opacity-100"
            onClick={e => e.stopPropagation()}
          >
            {product.sizes.slice(0, 5).map(s => (
              <button key={s} onClick={() => setSelectedSize(s)}
                className={clsx(
                  "px-2 py-0.5 text-[10px] font-mono rounded-md transition-all",
                  selectedSize === s
                    ? "text-white font-700"
                    : "text-slate-600 hover:bg-indigo-50"
                )}
                style={selectedSize === s
                  ? { background: "var(--indigo)" }
                  : { background: "rgba(255,255,255,0.85)" }
                }>
                {s}
              </button>
            ))}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* ── Card body ───────────────────────────────────────────────────── */}
      <div className="p-3.5 flex flex-col gap-2.5">
        {/* Brand + name */}
        <div>
          <p className="text-[10px] font-mono uppercase tracking-widest"
            style={{ color: "var(--text-muted)" }}>
            {product.brand}
          </p>
          <h3 className="font-display text-sm font-700 leading-tight mt-0.5 line-clamp-2"
            style={{ color: "var(--text-primary)" }}>
            {product.name}
          </h3>
        </div>

        {/* Rating */}
        <div className="flex items-center gap-1">
          <div className="flex">
            {[1,2,3,4,5].map(i => (
              <span key={i} className="text-[10px]"
                style={{ color: i <= Math.round(product.rating) ? "#F59E0B" : "#E2E8F0" }}>★</span>
            ))}
          </div>
          <span className="text-[10px] font-mono" style={{ color: "var(--text-muted)" }}>
            {product.rating.toFixed(1)} ({product.review_count.toLocaleString("en-IN")})
          </span>
        </div>

        {/* Drop timer */}
        <DropTimer inventoryLevel={product.inventory_level} />

        {/* Live price */}
        <div className="min-h-[2rem]">
          {pricingLoading || !pricing
            ? <PriceDisplaySkeleton size="sm" />
            : <PriceDisplay pricing={pricing} productId={product.id} size="sm" showBadge />
          }
        </div>

        {/* Add to cart */}
        <motion.button whileTap={{ scale: 0.97 }} onClick={handleAdd}
          className="w-full py-2.5 rounded-xl text-sm font-display font-700 transition-all duration-200"
          style={addedToCart
            ? { background: "var(--green-bg)", color: "var(--green)", border: "1px solid rgba(16,185,129,0.3)" }
            : { background: "var(--indigo)", color: "#fff" }
          }>
          {addedToCart
            ? `✓ Added · ${formatINR(priceInr)}`
            : "Add to Cart"
          }
        </motion.button>
      </div>
    </motion.div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────
export function ProductCardSkeleton({ index = 0 }: { index?: number }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      transition={{ delay: index * 0.04 }} className="product-card overflow-hidden">
      <div className="skeleton" style={{ aspectRatio: "1/1" }} />
      <div className="p-3.5 space-y-2.5">
        <div className="skeleton h-3 w-16 rounded" />
        <div className="skeleton h-4 w-full rounded" />
        <div className="skeleton h-3 w-20 rounded" />
        <div className="skeleton h-7 w-28 rounded" />
        <div className="skeleton h-9 w-full rounded-xl" />
      </div>
    </motion.div>
  );
}
