"use client";
// hooks/useCatalog.ts — Fetches the organizer's 5,000+ SKU catalog from Redis
// Falls back to the hardcoded 6 products when backend is offline.

import { useState, useEffect, useCallback } from "react";
import { Product, CatalogProduct, CatalogPage } from "@/types";
import { fetchCatalog, fetchCategories } from "@/lib/api-client";
import { catalogToProduct, FALLBACK_PRODUCTS } from "@/lib/catalog";

interface UseCatalogOptions {
  category?: string;
  page?: number;
  perPage?: number;
}

interface UseCatalogResult {
  products: Product[];
  categories: string[];
  total: number;
  pages: number;
  loading: boolean;
  error: string | null;
  isLive: boolean;       // true = organizer data, false = fallback
  refetch: () => void;
}

export function useCatalog(opts: UseCatalogOptions = {}): UseCatalogResult {
  const [products, setProducts]     = useState<Product[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [total, setTotal]           = useState(0);
  const [pages, setPages]           = useState(1);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);
  const [isLive, setIsLive]         = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // 1. Fetch paginated catalog from backend (organizer data in Redis)
      const data: CatalogPage = await fetchCatalog({
        category: opts.category,
        page:     opts.page || 1,
        perPage:  opts.perPage || 24,
      });

      if (data.products && data.products.length > 0) {
        // 🟢 FIX 1: Map AND sort sponsored products to the top
        const mappedProducts = data.products.map(catalogToProduct);
        
        mappedProducts.sort((a, b) => {
          if (a.is_sponsored && !b.is_sponsored) return -1;
          if (!a.is_sponsored && b.is_sponsored) return 1;
          return 0;
        });

        setProducts(mappedProducts);
        setTotal(data.total);
        setPages(data.pages);
        setIsLive(true);
      } else {
        // Backend returned empty — either not seeded or no category match
        setProducts(FALLBACK_PRODUCTS);
        setTotal(FALLBACK_PRODUCTS.length);
        setPages(1);
        setIsLive(false);
        setError("Catalog not seeded yet — run seed_from_organizer_data.py. Showing demo products.");
      }

      // 2. Fetch categories (for the filter pills)
      try {
        const catData = await fetchCategories();
        setCategories(catData.categories || []);
      } catch {
        setCategories(Array.from(new Set(FALLBACK_PRODUCTS.map(p => p.category))));
      }

    } catch {
      // Backend offline — use fallback
      // 🟢 BONUS FIX: Sort fallbacks too, in case you add a fake sponsored item for testing
      const sortedFallbacks = [...FALLBACK_PRODUCTS].sort((a, b) => {
        if (a.is_sponsored && !b.is_sponsored) return -1;
        if (!a.is_sponsored && b.is_sponsored) return 1;
        return 0;
      });
      
      setProducts(sortedFallbacks);
      setTotal(FALLBACK_PRODUCTS.length);
      setPages(1);
      setCategories(Array.from(new Set(FALLBACK_PRODUCTS.map(p => p.category))));
      setIsLive(false);
    } finally {
      setLoading(false);
    }
  }, [opts.category, opts.page, opts.perPage]);

  useEffect(() => { load(); }, [load]);

  return { products, categories, total, pages, loading, error, isLive, refetch: load };
}