// frontend/src/lib/vendor-api.ts

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ⚠️ Uses vendor_token — separate from storefront velocity_token
function vendorHeaders(): Record<string, string> {
  const token = typeof window !== "undefined" ? localStorage.getItem("vendor_token") : null;
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export interface DiscountResponse {
  product_id: string; original_price: number; discounted_price: number;
  discount_pct: number; applied_at: string; applied_by: string;
}

export interface CouponResponse {
  code: string; discount_pct: number; target: string; target_id: string | null;
  max_uses: number; uses_remaining: number; expires_at: string; created_by: string;
}

export interface CouponRedeemResponse {
  valid: boolean; discount_pct: number; discounted_total: number; message: string;
}

export interface SponsorResponse {
  product_id: string; is_sponsored: boolean; badge_label: string;
  sponsored_until: string; sponsored_by: string;
}

export interface NotifyResponse {
  sent: boolean; recipient: string; coupon_code: string; message: string;
}

// 🟢 NEW: Added OrderResponse typing
export interface OrderResponse {
  success: boolean;
  order_id: string;
  total: number;
  items: any[];
}

export async function applyDiscount(
  payload: { product_id: string; discount_pct: number; reason: string },
  original_price: number
): Promise<DiscountResponse> {
  const res = await fetch(`${BASE}/api/v1/vendor/discount?original_price=${original_price}`, { 
    method: "POST", 
    headers: vendorHeaders(), 
    body: JSON.stringify(payload) 
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Failed to apply discount");
  return data;
}

export async function removeDiscount(product_id: string) {
  const res = await fetch(`${BASE}/api/v1/vendor/discount/${product_id}`, { 
    method: "DELETE", 
    headers: vendorHeaders() 
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Failed to remove discount");
  return data;
}

export async function createCoupon(payload: {
  code: string; discount_pct: number; target: string;
  target_id: string | null; max_uses: number; ttl_minutes: number;
}): Promise<CouponResponse> {
  const res = await fetch(`${BASE}/api/v1/vendor/coupon`, { 
    method: "POST", 
    headers: vendorHeaders(), 
    body: JSON.stringify(payload) 
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Failed to create coupon");
  return data;
}

export async function redeemCoupon(payload: {
  code: string; user_id: string; cart_total: number;
}): Promise<CouponRedeemResponse> {
  const res = await fetch(`${BASE}/api/v1/vendor/coupon/redeem`, { 
    method: "POST", 
    headers: vendorHeaders(), // ✅ FIXED: Now uses consistent headers
    body: JSON.stringify(payload) 
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Redemption failed");
  return data;
}

export async function sponsorProduct(payload: {
  product_id: string; duration_hours: number; badge_label: string;
}): Promise<SponsorResponse> {
  const res = await fetch(`${BASE}/api/v1/vendor/sponsor`, { 
    method: "POST", 
    headers: vendorHeaders(), 
    body: JSON.stringify(payload) 
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Failed to sponsor product");
  return data;
}

export async function revokeSponsor(product_id: string) {
  const res = await fetch(`${BASE}/api/v1/vendor/sponsor/${product_id}`, { 
    method: "DELETE", 
    headers: vendorHeaders() 
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Failed to revoke sponsorship");
  return data;
}

export async function notifyUser(payload: {
  user_email: string; coupon_code: string;
}): Promise<NotifyResponse> {
  const res = await fetch(`${BASE}/api/v1/vendor/notify`, { 
    method: "POST", 
    headers: vendorHeaders(), 
    body: JSON.stringify(payload) 
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Failed to send notification");
  return data;
}

// ✅ Place Order API
export async function placeOrder(payload: {
  user_id: string;
  items: {
    product_id: string;
    quantity: number;
    price: number;
  }[];
  total_amount: number;
  coupon_code?: string | null;
}): Promise<OrderResponse> { // ✅ FIXED: Added return type
  const res = await fetch(`${BASE}/api/v1/vendor/checkout`, {
    method: "POST",
    headers: vendorHeaders(), // ✅ FIXED: Now uses consistent headers
    body: JSON.stringify(payload),
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Checkout failed");

  return data;
}