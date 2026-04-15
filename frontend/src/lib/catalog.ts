// lib/catalog.ts
// Dual-mode catalog:
//   1. LIVE mode  — fetches from /api/v1/catalog/ (organizer's 5,000+ SKU dataset)
//   2. FALLBACK   — hardcoded 6 products when backend is offline
//
// ALL prices stored in USD. Display layer calls usdToInr() for INR output.

import { Product, CatalogProduct } from "@/types";


// ── Category → Unsplash image mapping ────────────────────────────────────────
// Maps organizer categories to relevant product photography
const CATEGORY_IMAGES: Record<string, string[]> = {
  "Electronics":       [
    "https://images.unsplash.com/photo-1498049794561-7780e7231661?w=600&q=80",
    "https://images.unsplash.com/photo-1588508065123-287b28e013da?w=600&q=80",
    "https://images.unsplash.com/photo-1593305841991-05c297ba4575?w=600&q=80",
  ],
  "Clothing":          [
    "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?w=600&q=80",
    "https://images.unsplash.com/photo-1516762689617-e1cffcef479d?w=600&q=80",
  ],
  "Home & Kitchen":    [
    "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=600&q=80",
    "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=600&q=80",
  ],
  "Books & Media":     [
    "https://images.unsplash.com/photo-1495446815901-a7297e633e8d?w=600&q=80",
    "https://images.unsplash.com/photo-1519681393784-d120267933ba?w=600&q=80",
  ],
  "Beauty & Health":   [
    "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=600&q=80",
    "https://images.unsplash.com/photo-1608248543803-ba4f8c70ae0b?w=600&q=80",
  ],
  "Sports":            [
    "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=80",
    "https://images.unsplash.com/photo-1600185365926-3a2ce3cdb9eb?w=600&q=80",
  ],
  "Gaming":            [
    "https://images.unsplash.com/photo-1593118247619-e2d6f056869e?w=600&q=80",
    "https://images.unsplash.com/photo-1612287230202-1ff1d85d1bdf?w=600&q=80",
  ],
  "Cameras":           [
    "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=600&q=80",
    "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=600&q=80",
  ],
  "Accessories":       [
    "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80",
    "https://images.unsplash.com/photo-1585386959984-a4155224a1ad?w=600&q=80",
  ],
  "Baby":              [
    "https://images.unsplash.com/photo-1515488042361-ee00e0ddd4e4?w=600&q=80",
  ],
  "Cookware":          [
    "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=600&q=80",
  ],
  "Art Supplies":      [
    "https://images.unsplash.com/photo-1513364776144-60967b0f800f?w=600&q=80",
  ],
  "Decor":             [
    "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=600&q=80",
  ],
  "Cleaning Supplies": [
    "https://images.unsplash.com/photo-1563453392212-326f5e854473?w=600&q=80",
  ],
  "Footwear":          [
    "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=80",
    "https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=600&q=80",
  ],
  "default":           [
    "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80",
    "https://images.unsplash.com/photo-1491553895911-0055eca6402d?w=600&q=80",
  ],
};

function getImageForCategory(category: string, skuId: string): string {
  const images = CATEGORY_IMAGES[category] ?? CATEGORY_IMAGES["default"];
  // Deterministic selection per SKU (not random on every render)
  const hashCode = skuId.split("").reduce((a, c) => a + c.charCodeAt(0), 0);
  return images[hashCode % images.length];
}

// Standard sizes by category
const SIZES_BY_CATEGORY: Record<string, string[]> = {
  "Clothing":  ["XS", "S", "M", "L", "XL", "XXL"],
  "Footwear":  ["6", "7", "8", "9", "10", "11", "12"],
  "default":   ["One Size"],
};

/** Map organizer CatalogProduct → UI Product */
export function catalogToProduct(p: CatalogProduct): Product {
  return {
  id:              p.id,
  name:            p.name,
  brand:           p.brand,
  category:        p.category,
  subcategory:     p.subcategory,
  base_price:      p.base_price,
  cost_price:      p.cost_price,
  inventory_level: p.inventory_level,

  // 🟢 ADD THIS LINE (CRITICAL FIX)
  is_sponsored:    p.is_sponsored ?? false,
  sponsor_badge:   p.sponsor_badge,

  image_url:       getImageForCategory(p.category, p.id),
  colorway:        p.subcategory || p.category,
  sizes:           SIZES_BY_CATEGORY[p.category] ?? SIZES_BY_CATEGORY["default"],
  rating:          p.avg_rating,
  review_count:    p.review_count,
  is_new:          false,
  tags:            p.tags ? p.tags.split(",").map(t => t.trim()).filter(Boolean) : [],
  trending:        p.trending,
  limited:         p.limited,
  restock_days:    p.restock_days,
};
}

// ── Demand context for price explainability (per category) ───────────────────
// Indian market demand signals for the transparency tooltip
export const DEMAND_CONTEXT_BY_CATEGORY: Record<string, string> = {
  "Electronics":       "📱 Demand up 38% — Diwali gifting season surge",
  "Clothing":          "👕 End-of-season sale — demand velocity declining",
  "Home & Kitchen":    "🏠 Wedding season boost — home setup demand rising",
  "Books & Media":     "📚 Back-to-school period — demand spike detected",
  "Beauty & Health":   "✨ Festival season — beauty purchases up 54%",
  "Sports":            "🏃 IPL season — sports gear demand surging",
  "Gaming":            "🎮 Holiday release window — inventory critical",
  "Cameras":           "📷 Travel season demand — matched Croma pricing",
  "Accessories":       "⌚ Gift season velocity — 47 views in last 5 min",
  "Cookware":          "🍳 Matched Amazon India competitive price",
  "Footwear":          "👟 High demand ahead of Navratri season",
  "default":           "📈 Real-time demand signals detected",
};

export function getDemandContext(category: string): string {
  return DEMAND_CONTEXT_BY_CATEGORY[category] ?? DEMAND_CONTEXT_BY_CATEGORY["default"];
}

// ── Fallback catalog (when backend is offline) ────────────────────────────────
// Kept as 6 representative products across key organizer categories
export const FALLBACK_PRODUCTS: Product[] = [
  {
    id: "SKU001000", name: "ProSound Wireless Headphones", brand: "AuraStyle",
    category: "Electronics", base_price: 89.99, cost_price: 35.00, inventory_level: 23,
    competitor_price: 94.99,
    image_url: CATEGORY_IMAGES["Electronics"][0],
    colorway: "Midnight Black", sizes: ["One Size"],
    rating: 4.7, review_count: 3241, is_new: true, tags: ["trending", "bestseller"],
    trending: true, limited: false,
  },
  {
    id: "SKU001500", name: "Urban Fit Running Jacket", brand: "PeakForm",
    category: "Clothing", base_price: 54.99, cost_price: 22.00, inventory_level: 67,
    image_url: CATEGORY_IMAGES["Clothing"][0],
    colorway: "Forest Green / Reflect", sizes: ["XS","S","M","L","XL","XXL"],
    rating: 4.5, review_count: 1892, is_new: false, tags: ["bestseller"],
    trending: false, limited: false,
  },
  {
    id: "SKU002100", name: "Smart Chef Cookware Set", brand: "TrueBlend",
    category: "Cookware", base_price: 129.99, cost_price: 52.00, inventory_level: 8,
    competitor_price: 135.00,
    image_url: CATEGORY_IMAGES["Cookware"][0],
    colorway: "Brushed Steel", sizes: ["One Size"],
    rating: 4.8, review_count: 987, is_new: false, tags: ["limited", "premium"],
    trending: false, limited: true,
  },
  {
    id: "SKU003200", name: "Pro Gaming Headset RGB", brand: "CoreLine",
    category: "Gaming", base_price: 74.99, cost_price: 30.00, inventory_level: 4,
    image_url: CATEGORY_IMAGES["Gaming"][0],
    colorway: "Shadow Black / RGB", sizes: ["One Size"],
    rating: 4.6, review_count: 2109, is_new: true, tags: ["trending", "limited"],
    trending: true, limited: true,
  },
  {
    id: "SKU004100", name: "Mirrorless Camera Kit 24MP", brand: "BrightPath",
    category: "Cameras", base_price: 599.99, cost_price: 240.00, inventory_level: 12,
    competitor_price: 619.99,
    image_url: CATEGORY_IMAGES["Cameras"][0],
    colorway: "Graphite Silver", sizes: ["One Size"],
    rating: 4.9, review_count: 654, is_new: true, tags: ["new", "premium"],
    trending: true, limited: false,
  },
  {
    id: "SKU005500", name: "Vitamin C Serum 30ml", brand: "EcoWave",
    category: "Beauty & Health", base_price: 29.99, cost_price: 12.00, inventory_level: 134,
    image_url: CATEGORY_IMAGES["Beauty & Health"][0],
    colorway: "Clear / Gold Cap", sizes: ["One Size"],
    rating: 4.4, review_count: 5820, is_new: false, tags: ["bestseller"],
    trending: false, limited: false,
  },
];

export function getProduct(id: string): Product | undefined {
  return FALLBACK_PRODUCTS.find((p) => p.id === id);
}
