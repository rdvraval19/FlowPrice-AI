// lib/personas.ts — Two personas: Customer + Admin
// Seed events use organizer SKU IDs from product_catalog.parquet

export interface PersonaSignal {
  icon: string; label: string; value: string;
}

export interface SeedEvent {
  event_type: string;
  product?: { product_id: string; category: string; price_shown: number; base_price: number; inventory_level?: number; };
  search?: { query: string; result_count: number; filters_applied: string[]; };
}

export interface Persona {
  id: string; name: string; tagline: string; segment: string;
  color: string; glowHex: string; borderHex: string;
  accentClass: string; bgClass: string; icon: string; badge: string;
  signals: PersonaSignal[];
  seedEvents: SeedEvent[];
  redirectTo: string;
  intentScore: number;
  purchaseHistory: number;
}

export const PERSONAS: Persona[] = [
  {
    id: "customer",
    name: "Customer",
    tagline: "Browses, compares, hunts deals — and buys when the price is right.",
    segment: "returning",
    color: "emerald", glowHex: "#10b981", borderHex: "#059669",
    accentClass: "text-emerald-400", bgClass: "bg-emerald-500/10",
    icon: "🛍️", badge: "SHOPPER",
    intentScore: 74, purchaseHistory: 16,
    signals: [
      { icon: "📊", label: "Category affinity", value: "Electronics • Clothing"   },
      { icon: "💰", label: "Price sensitivity",  value: "Moderate — watches deals" },
      { icon: "🛒", label: "Cart behaviour",     value: "Adds, compares, converts" },
      { icon: "⚡", label: "Discount response",  value: "Converts at 15%+ off"    },
    ],
    seedEvents: [
      // Browsing / research (from Tech Enthusiast)
      { event_type: "page_view" },
      { event_type: "product_view",
        product: { product_id: "SKU004100", category: "Cameras", price_shown: 599.99, base_price: 599.99, inventory_level: 12 } },
      { event_type: "image_zoom",
        product: { product_id: "SKU004100", category: "Cameras", price_shown: 599.99, base_price: 599.99 } },
      { event_type: "product_view",
        product: { product_id: "SKU001000", category: "Electronics", price_shown: 89.99, base_price: 89.99, inventory_level: 23 } },
      { event_type: "cart_add",
        product: { product_id: "SKU001000", category: "Electronics", price_shown: 89.99, base_price: 89.99 } },
      // Deal hunting (from Deal Seeker)
      { event_type: "search",
        search: { query: "deals sale discount", result_count: 45, filters_applied: ["sort:price_asc"] } },
      { event_type: "product_view",
        product: { product_id: "SKU001500", category: "Clothing", price_shown: 54.99, base_price: 54.99, inventory_level: 67 } },
      { event_type: "product_view",
        product: { product_id: "SKU005500", category: "Beauty & Health", price_shown: 29.99, base_price: 29.99, inventory_level: 134 } },
      { event_type: "wishlist_add",
        product: { product_id: "SKU002100", category: "Cookware", price_shown: 129.99, base_price: 129.99 } },
      { event_type: "cart_add",
        product: { product_id: "SKU005500", category: "Beauty & Health", price_shown: 29.99, base_price: 29.99 } },
      { event_type: "checkout_start" },
    ],
    redirectTo: "/storefront",
  },
  {
    id: "admin",
    name: "Admin / Judge",
    tagline: "Full system visibility. All metrics unlocked.",
    segment: "high_value",
    color: "purple", glowHex: "#8b5cf6", borderHex: "#7c3aed",
    accentClass: "text-violet-400", bgClass: "bg-violet-500/10",
    icon: "📊", badge: "ADMIN ACCESS",
    intentScore: 100, purchaseHistory: 0,
    signals: [
      { icon: "⚡", label: "Stream access",   value: "All events · real-time"   },
      { icon: "🧪", label: "A/B experiments", value: "2 running · live metrics" },
      { icon: "🛡",  label: "Fairness audit",  value: "96/100 · no bias"         },
      { icon: "📉", label: "Revenue uplift",  value: "+₹1,45,020 vs baseline"   },
    ],
    seedEvents: [{ event_type: "page_view" }],
    redirectTo: "/dashboard",
  },
];

export const getPersona = (id: string) => PERSONAS.find(p => p.id === id);