"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { useCatalog } from "@/hooks/useCatalog";
import { fetchBulkPrices } from "@/lib/api-client";
import { useSessionStore } from "@/store/session";
import { useEventTracker } from "@/hooks/useEventTracker";
import { ProductCard, ProductCardSkeleton } from "@/components/storefront/ProductCard";
import { CartDrawer } from "@/components/storefront/CartDrawer";
import { LiveToasts } from "@/components/storefront/LiveToasts";
import { RecommendationSlider } from "@/components/storefront/RecommendationSlider";
import { PricingResponse, Product } from "@/types";
import { formatINR, usdToInr } from "@/lib/currency";
import { clsx } from "clsx";
import { ShoppingCart } from "lucide-react";


const SEGMENT_CONFIG: Record<string, { label: string; icon: string; desc: string }> = {
  new_user:        { label: "New",       icon: "✦", desc: "Welcome offer" },
  returning:       { label: "Returning", icon: "⟳", desc: "Standard pricing" },
  loyal:           { label: "Loyal",     icon: "★", desc: "Member discounts" },
  high_value:      { label: "VIP",       icon: "◆", desc: "Premium buyer" },
  price_sensitive: { label: "Saver",     icon: "↓", desc: "Best deals" },
  at_risk:         { label: "Win-back",  icon: "⚡", desc: "Retention offers" },
};

export default function StorefrontPage() {
  const { sessionId, userId, userSegment, setUserSegment, cartCount, personaName } = useSessionStore();
  const { track, trackProductView } = useEventTracker();

  const [activeCategory,  setActiveCategory]  = useState<string|undefined>(undefined);
  const [currentPage,     setCurrentPage]     = useState(1);
  const [prices,          setPrices]          = useState<Record<string, PricingResponse>>({});
  const [pricingLoading,  setPricingLoading]  = useState(false);
  const [cartOpen,        setCartOpen]        = useState(false);
  const [searchQuery,     setSearchQuery]     = useState("");
  const [liveCount,       setLiveCount]       = useState(0);
  // For "Milk & Cookies" — track the last product the user viewed
  const [lastViewed, setLastViewed]           = useState<{id:string;cat:string}|null>(null);

  const { products, categories, total, pages, loading, isLive } = useCatalog({
    category: activeCategory, page: currentPage, perPage: 24,
  });

  useEffect(() => {
    setLiveCount(284 + Math.floor(Math.random() * 130));
    const t = setInterval(() => setLiveCount(c => Math.max(200, c + Math.floor(Math.random() * 7) - 3)), 3500);
    return () => clearInterval(t);
  }, []);

  const loadPrices = useCallback(async (prods: Product[]) => {
    if (!sessionId || !prods.length) return;
    setPricingLoading(true);
    try {
      const res = await fetchBulkPrices({
        sessionId, userSegment,
        products: prods.map(p => ({
          product_id: p.id, base_price: p.base_price, cost_price: p.cost_price,
          inventory_level: p.inventory_level,
          ...(p.competitor_price ? { competitor_price: p.competitor_price } : {}),
        })),
      });
      setPrices(prev => ({ ...prev, ...(res.prices || {}) }));
    } catch {}
    finally { setPricingLoading(false); }
  }, [sessionId, userSegment]);

  useEffect(() => { if (products.length) loadPrices(products); }, [products, userSegment]);
  useEffect(() => { track("page_view", { page_url: "/storefront" }); }, []);
  useEffect(() => {
    const t = setInterval(() => { if (products.length) loadPrices(products); }, 30000);
    return () => clearInterval(t);
  }, [products, loadPrices]);

  const filtered = searchQuery
    ? products.filter(p => p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                           p.brand.toLowerCase().includes(searchQuery.toLowerCase()) ||
                           p.category.toLowerCase().includes(searchQuery.toLowerCase()))
    : products;

  const handleProductClick = (product: Product) => {
    const price = prices[product.id]?.final_price ?? product.base_price;
    trackProductView(product.id, product.category, price, product.base_price);
    setLastViewed({ id: product.id, cat: product.category });
  };

  // Computed revenue impact
  const totalSavings = Object.values(prices).reduce((s, p) =>
    s + (p.base_price > p.final_price ? usdToInr(p.base_price - p.final_price) : 0), 0);
  const totalSurge = Object.values(prices).reduce((s, p) =>
    s + (p.final_price > p.base_price ? usdToInr(p.final_price - p.base_price) : 0), 0);

  return (
    <div className="storefront-light min-h-screen" style={{ background: "var(--bg-base)" }}>
      {/* ── Nav ─────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-30 glass-light" style={{ borderBottom: "1px solid var(--border-light)" }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center gap-3">
          {/* Logo */}
          <Link href="/" className="font-display text-xl font-800 tracking-tight"
            style={{ color: "var(--indigo)" }}>
            FlowPriceAI
          </Link>

          {personaName && (
            <span className="hidden md:flex items-center gap-1.5 text-xs font-mono"
              style={{ color: "var(--text-muted)" }}>
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--indigo)" }} />
              {personaName}
            </span>
          )}

          {/* Search */}
          <div className="flex-1 max-w-sm relative hidden sm:block">
            <input type="text" placeholder="Search products, brands…"
              value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              className="w-full rounded-xl px-3 py-1.5 text-sm outline-none transition-all font-body"
              style={{
                background: "var(--bg-card)", color: "var(--text-primary)",
                border: "1.5px solid var(--border-light)",
              }}
              onFocus={e => (e.target.style.borderColor = "var(--indigo)")}
              onBlur={e => (e.target.style.borderColor = "var(--border-light)")}
            />
          </div>

          <div className="flex items-center gap-2 ml-auto">
            {/* Live counter */}
            <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono"
              style={{ background: "var(--green-bg)", color: "var(--green)", border: "1px solid rgba(16,185,129,0.2)" }}>
              <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: "var(--green)" }} />
              {liveCount.toLocaleString("en-IN")} live
            </div>
            {/* Dashboard link */}
            <Link href="/dashboard"
              className="hidden sm:flex px-2.5 py-1 text-xs font-mono rounded-xl transition-colors"
              style={{ color: "var(--indigo)", border: "1px solid rgba(79,70,229,0.2)", background: "var(--indigo-light)" }}>
              Dashboard ↗
            </Link>
            {/* Cart */}
            <button
              onClick={() => setCartOpen(true)}
              className="relative flex items-center justify-center w-9 h-9 rounded-xl transition-colors"
              style={{ background: "var(--indigo)", color: "#fff" }}
            >
              <ShoppingCart className="w-5 h-5" />

              {cartCount() > 0 && (
                <motion.span
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  className="absolute -top-1 -right-1 w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-mono"
                  style={{ background: "var(--red)", color: "#fff" }}
                >
                  {cartCount()}
                </motion.span>
              )}
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        {/* ── Hero Banner ──────────────────────────────────────────────── */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl overflow-hidden mb-6 relative"
          style={{
            background: "linear-gradient(135deg, var(--indigo) 0%, #7C3AED 100%)",
            minHeight: 160,
          }}>
          {/* Grid pattern */}
          <div className="absolute inset-0 opacity-10"
            style={{ backgroundImage: "linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)", backgroundSize: "32px 32px" }} />
          <div className="relative px-8 py-7 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                <span className="text-white/70 text-xs font-mono uppercase tracking-widest">
                  Real-time ML pricing · {total.toLocaleString("en-IN")} products · INR
                </span>
              </div>
              <h1 className="font-display text-3xl sm:text-4xl font-800 text-white leading-tight">
                {isLive ? "Live Catalog" : "Demo Store"}
                <span className="text-white/70"> · Dynamic Prices</span>
              </h1>
              <p className="text-white/60 text-sm mt-1.5">
                Prices update in real-time. Hover any price badge to understand why.
              </p>
            </div>
            {/* Revenue impact pill */}
            {(totalSavings > 0 || totalSurge > 0) && (
              <div className="hidden md:flex flex-col gap-2">
                {totalSavings > 0 && (
                  <div className="px-3 py-1.5 rounded-xl bg-white/10 text-white text-xs font-mono">
                    ↓ Savings active: {formatINR(totalSavings)}
                  </div>
                )}
                {totalSurge > 0 && (
                  <div className="px-3 py-1.5 rounded-xl bg-white/10 text-white text-xs font-mono">
                    ↑ Demand surge: {formatINR(totalSurge)}
                  </div>
                )}
              </div>
            )}
          </div>
        </motion.div>

        {/* ── Controls ─────────────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row gap-3 mb-5">
          {/* Category pills */}
          <div className="flex gap-1.5 flex-wrap">
            <button onClick={() => { setActiveCategory(undefined); setCurrentPage(1); }}
              className="px-3 py-1.5 rounded-xl text-xs font-display font-600 transition-all"
              style={!activeCategory
                ? { background: "var(--indigo)", color: "#fff" }
                : { background: "var(--bg-card)", color: "var(--text-secondary)", border: "1px solid var(--border-light)" }
              }>
              All
            </button>
            {categories.slice(0, 7).map(cat => (
              <button key={cat} onClick={() => { setActiveCategory(cat); setCurrentPage(1); }}
                className="px-3 py-1.5 rounded-xl text-xs font-display font-600 transition-all truncate max-w-[110px]"
                style={activeCategory === cat
                  ? { background: "var(--indigo)", color: "#fff" }
                  : { background: "var(--bg-card)", color: "var(--text-secondary)", border: "1px solid var(--border-light)" }
                }>
                {cat}
              </button>
            ))}
          </div>

          {/* Segment switcher */}
          <div className="sm:ml-auto flex items-center gap-2 flex-wrap">
            <span className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>Persona:</span>
            {Object.entries(SEGMENT_CONFIG).slice(0, 5).map(([id, cfg]) => (
              <button key={id} onClick={() => setUserSegment(id)} title={cfg.desc}
                className="px-2 py-1 rounded-lg text-xs font-mono transition-all"
                style={userSegment === id
                  ? { background: "var(--indigo-light)", color: "var(--indigo)", border: "1px solid rgba(79,70,229,0.3)" }
                  : { background: "var(--bg-card)", color: "var(--text-muted)", border: "1px solid var(--border-light)" }
                }>
                {cfg.icon} {cfg.label}
              </button>
            ))}
          </div>
        </div>

        {/* ── Product grid ─────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
          <AnimatePresence mode="popLayout">
            {loading
              ? Array.from({ length: 12 }).map((_, i) => <ProductCardSkeleton key={i} index={i} />)
              : filtered.map((product, i) => (
                  <ProductCard key={product.id} product={product}
                    pricing={prices[product.id] ?? null}
                    pricingLoading={pricingLoading && !prices[product.id]}
                    index={i}
                    onProductClick={handleProductClick}
                  />
                ))
            }
          </AnimatePresence>
        </div>

        {!loading && filtered.length === 0 && (
          <div className="text-center py-20 font-display text-sm" style={{ color: "var(--text-muted)" }}>
            No products match "{searchQuery}"
          </div>
        )}

        {/* Pagination */}
        {isLive && pages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-8">
            <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1}
              className="px-4 py-2 rounded-xl text-sm font-mono transition-all disabled:opacity-30"
              style={{ background: "var(--bg-card)", color: "var(--text-secondary)", border: "1px solid var(--border-light)" }}>
              ← Prev
            </button>
            <span className="text-xs font-mono px-3" style={{ color: "var(--text-muted)" }}>
              {currentPage} / {pages} · {total.toLocaleString("en-IN")} products
            </span>
            <button onClick={() => setCurrentPage(p => Math.min(pages, p + 1))} disabled={currentPage === pages}
              className="px-4 py-2 rounded-xl text-sm font-mono transition-all disabled:opacity-30"
              style={{ background: "var(--bg-card)", color: "var(--text-secondary)", border: "1px solid var(--border-light)" }}>
              Next →
            </button>
          </div>
        )}

        {/* ── Recommendation Slider ─────────────────────────────────────── */}
        {!loading && filtered.length > 0 && (
          <div className="mt-12 pt-8" style={{ borderTop: "1px solid var(--border-light)" }}>
            <RecommendationSlider
              sessionId={sessionId}
              userId={userId ?? undefined}
              title="Recommended for You"
              lastViewedProductId={lastViewed?.id}
              lastViewedCategory={lastViewed?.cat}
            />
          </div>
        )}

        {/* ── Transparency footer ───────────────────────────────────────── */}
        <div className="mt-10 p-6 rounded-2xl" style={{ background: "var(--bg-card)", border: "1px solid var(--border-light)" }}>
          <h3 className="font-display text-sm font-700 mb-3" style={{ color: "var(--text-primary)" }}>
            How FlowPriceAI pricing works
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs" style={{ color: "var(--text-muted)" }}>
            {[
              { icon: "📈", label: "Demand signals",  desc: "Redis Stream velocity · 5-min rolling window", color: "var(--indigo)" },
              { icon: "🔄", label: "Competitor match", desc: "Organizer feed · Amazon IN, Flipkart, Croma", color: "var(--green)" },
              { icon: "⚡", label: "Scarcity pricing", desc: "Live inventory levels from catalog",           color: "var(--orange)" },
              { icon: "🛡", label: "Circuit Breaker",  desc: "Hard floor/ceiling — model can't go too far", color: "var(--purple)" },
            ].map(item => (
              <div key={item.label} className="flex gap-2">
                <span className="text-base leading-none mt-0.5">{item.icon}</span>
                <div>
                  <div className="font-700 mb-0.5 text-xs" style={{ color: item.color }}>{item.label}</div>
                  <div>{item.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <CartDrawer open={cartOpen} onClose={() => setCartOpen(false)} />
      <LiveToasts />
    </div>
  );
}
