// types/index.ts — All shared TypeScript interfaces

export type PriceAdjustmentReason =
  | "high_demand" | "low_demand" | "limited_stock" | "flash_sale"
  | "loyalty_discount" | "new_visitor_offer" | "competitor_match"
  | "base_price" | "margin_floor_hit" | "cap_hit";

export interface PriceExplanation {
  primary_reason: PriceAdjustmentReason;
  secondary_reasons: PriceAdjustmentReason[];
  user_copy: string;
  discount_pct: number;
  demand_velocity: number;
  inventory_level: number | null;
  confidence: number;
  is_personalized: boolean;
  fairness_checked: boolean;
}

export interface PricingResponse {
  product_id: string;
  session_id: string;
  final_price: number;
  base_price: number;
  discount_pct: number;
  explanation: PriceExplanation;
  variant_id: string | null;
  computed_in_ms: number;
  cached: boolean;
}

export interface CatalogProduct {
  id: string;
  name: string;
  brand: string;
  category: string;
  subcategory: string;
  base_price: number;
  cost_price: number;
  current_price: number;
  min_price: number;
  max_price: number;
  inventory_level: number;
  restock_days: number;
  avg_rating: number;
  review_count: number;
  tags: string;
  trending: boolean;
  limited: boolean;
  is_sponsored: boolean;      // ← ADD THIS
  sponsor_badge?: string;     // ← ADD THIS
}

export interface Product {
  id: string;
  name: string;
  brand: string;
  category: string;
  subcategory?: string;
  base_price: number;
  cost_price: number;
  inventory_level: number;
  competitor_price?: number;
  image_url: string;
  colorway: string;
  sizes: string[];
  rating: number;
  review_count: number;
  is_new: boolean;
  tags: string[];
  trending?: boolean;
  limited?: boolean;
  restock_days?: number;
  is_sponsored?: boolean;     // ← ADD THIS
  sponsor_badge?: string;     // ← ADD THIS
}

export interface RecommendationItem {
  product_id: string;
  score: number;
  source: "session_based" | "collaborative" | "cold_start" | "trending";
  rank: number;
}

export interface CartItem {
  product: Product;
  size: string;
  quantity: number;
  price_at_add: number;
}

export interface ExperimentVariantMetrics {
  variant_id: string;
  impressions: number;
  conversions: number;
  conversion_rate: number;
  revenue: number;
  aov: number;
  rps: number;
}

export interface ExperimentResult {
  experiment_id: string;
  name: string;
  status: string;
  started_at: number;
  variants: Record<string, ExperimentVariantMetrics>;
  statistical_significance: {
    p_value: number | null;
    is_significant: boolean;
    confidence: number;
    z_score?: number;
    note?: string;
  };
  winner: string | null;
}

export interface LatencyMetrics {
  p50: number;
  p95: number;
  p99: number;
  count: number;
}

export interface StreamEvent {
  id: string;
  session_id: string;
  event_type: string;
  timestamp_ms: string;
  device_type: string;
  user_segment: string;
  product_id?: string;
  category?: string;
  price_shown?: number;
}

export interface CatalogPage {
  products: CatalogProduct[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

// ── Phase 4: Loyalty + Activity ───────────────────────────────────────────────

export type LoyaltyTier = "bronze" | "silver" | "gold" | "platinum";

export interface TierInfo {
  name: LoyaltyTier;
  min_points: number;
  benefit: string;
  multiplier: number;
}

export interface PointsBalance {
  user_id: string;
  total_points: number;
  tier: LoyaltyTier;
  tier_benefit: string;
  tier_multiplier: number;
  points_to_next_tier: number | null;  // null = already Platinum
  session_points: number;
  last_updated_at: string;
}

export interface ActivityItem {
  id: string;
  event_type: string;
  product_id: string | null;
  category: string | null;
  price_shown: number | null;
  points_awarded: number;
  created_at: string;
}

export interface ActivityFeed {
  user_id: string;
  total_points: number;
  tier: LoyaltyTier;
  activities: ActivityItem[];
  page: number;
  per_page: number;
  total_count: number;
  has_more: boolean;
}

export interface LeaderboardEntry {
  rank: number;
  user_id: string;
  total_points: number;
  tier: LoyaltyTier;
}

// Auth types (Phase 1)
export interface AuthUser {
  id: string;
  email: string;
  role: "user" | "vendor";
  is_active: boolean;
  created_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  role: "user" | "vendor";
  user_id: string;
}