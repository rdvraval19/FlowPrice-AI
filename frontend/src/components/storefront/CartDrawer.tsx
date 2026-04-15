"use client";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useSessionStore } from "@/store/session";
import { formatINR, usdToInr } from "@/lib/currency";
import { redeemCoupon, placeOrder } from "@/lib/vendor-api";


export function CartDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { cart, removeFromCart, cartTotal, cartCount, userId, clearCart } = useSessionStore();
  const totalUsd = cartTotal();
  const totalInr = usdToInr(totalUsd);
  
  const [couponCode, setCouponCode] = useState("");
  const [discount, setDiscount] = useState(0);
  const [finalTotal, setFinalTotal] = useState(totalInr);
  const [message, setMessage] = useState("");
  
  // 🟢 NEW: Loading state for checkout
  const [isCheckingOut, setIsCheckingOut] = useState(false);

  useEffect(() => {
    if (discount === 0) {
      setFinalTotal(totalInr);
    }
  }, [totalInr, discount]);

  const handleApplyCoupon = async () => {
    if (!couponCode.trim()) {
      setMessage("⚠️ Please enter a code");
      return;
    }

    try {
      const res = await redeemCoupon({
        code: couponCode,
        user_id: userId || "guest_user",
        cart_total: totalUsd,
      });

      if (res.valid) {
        setDiscount(res.discount_pct);
        setFinalTotal(usdToInr(res.discounted_total));
        setMessage("✅ Coupon applied!");
      } else {
        setMessage("❌ Invalid coupon");
        setDiscount(0);
        setFinalTotal(totalInr);
      }
    } catch (err) {
      setMessage("⚠️ Error applying coupon");
      setDiscount(0);
      setFinalTotal(totalInr);
    }
  };

  const handleCheckout = async () => {
    if (!cart.length) {
      setMessage("⚠️ Cart is empty");
      return;
    }

    setIsCheckingOut(true);
    setMessage("");

    try {
      const res = await placeOrder({
        user_id: userId || "guest_user",
        items: cart.map(item => ({
          product_id: item.product.id,
          quantity: item.quantity,
          price: item.price_at_add,
        })),
        // ✅ Send USD only
        total_amount: discount > 0
          ? totalUsd * (1 - discount / 100)
          : totalUsd,
        coupon_code: discount > 0 ? couponCode : null,
      });

      // ✅ Success message
      setMessage(`🎉 Order placed! ID: ${res.order_id}`);

      // ✅ Clear everything
      clearCart();
      setCouponCode("");
      setDiscount(0);

      // ✅ Close drawer after delay
      setTimeout(() => {
        onClose();
      }, 1000);

    } catch (err) {
      setMessage("❌ Checkout failed");
    } finally {
      setIsCheckingOut(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            style={{
              position: "fixed", inset: 0,
              background: "rgba(0,0,0,0.55)",
              backdropFilter: "blur(4px)",
              zIndex: 9998,
            }}
          />

          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            style={{
              position: "fixed",
              top: 0, right: 0, bottom: 0,
              width: "100%", maxWidth: 400,
              background: "#0d0d18",
              borderLeft: "1px solid #1e1e2a",
              zIndex: 9999,
              display: "flex",
              flexDirection: "column",
            }}
          >
            {/* Header */}
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "20px", borderBottom: "1px solid #1e1e2a",
            }}>
              <div>
                <h2 style={{ color: "#fff", fontWeight: 700, fontSize: 18, margin: 0 }}>
                  Your Cart
                </h2>
                <p style={{ color: "#71717a", fontSize: 11, fontFamily: "monospace", marginTop: 2 }}>
                  {cartCount()} items · All prices in INR
                </p>
              </div>
              <button
                onClick={onClose}
                style={{
                  width: 32, height: 32,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  borderRadius: 8, border: "none",
                  background: "transparent", color: "#71717a",
                  cursor: "pointer", fontSize: 16,
                }}
                onMouseEnter={e => (e.currentTarget.style.color = "#fff")}
                onMouseLeave={e => (e.currentTarget.style.color = "#71717a")}
              >
                ✕
              </button>
            </div>

            {/* Items */}
            <div style={{ flex: 1, overflowY: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
              <AnimatePresence>
                {cart.length === 0 ? (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    style={{
                      display: "flex", flexDirection: "column", alignItems: "center",
                      justifyContent: "center", height: "100%", textAlign: "center", padding: "64px 0",
                    }}
                  >
                    <span style={{ fontSize: 40, opacity: 0.15, color: "#fff" }}>◻</span>
                    <p style={{ color: "#71717a", fontSize: 14, marginTop: 12 }}>Cart is empty</p>
                    <p style={{ color: "#3f3f46", fontSize: 12, marginTop: 4 }}>Dynamic prices are waiting…</p>
                  </motion.div>
                ) : (
                  cart.map((item, i) => {
                    const priceInr     = usdToInr(item.price_at_add);
                    const totalItemInr = usdToInr(item.price_at_add * item.quantity);
                    return (
                      <motion.div
                        key={`${item.product.id}-${item.size}`}
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 20, height: 0 }}
                        transition={{ delay: i * 0.04 }}
                        style={{
                          display: "flex", gap: 12, padding: 12,
                          background: "#141420", borderRadius: 12,
                          border: "1px solid #1e1e2a",
                        }}
                      >
                        <div style={{
                          width: 64, height: 64, borderRadius: 8,
                          background: "#0a0a12", overflow: "hidden", flexShrink: 0,
                        }}>
                          <img
                            src={item.product.image_url}
                            alt={item.product.name}
                            style={{ width: "100%", height: "100%", objectFit: "cover" }}
                          />
                        </div>

                        <div style={{ flex: 1, minWidth: 0 }}>
                          <p style={{
                            color: "#fff", fontSize: 14, fontWeight: 600,
                            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                            margin: 0,
                          }}>
                            {item.product.name}
                          </p>
                          <p style={{ color: "#71717a", fontSize: 12, marginTop: 2 }}>
                            {item.product.brand} · Size {item.size} · Qty {item.quantity}
                          </p>
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 6 }}>
                            <div>
                              <span style={{ color: "#fbbf24", fontSize: 14, fontWeight: 700 }}>
                                {formatINR(totalItemInr)}
                              </span>
                              {item.quantity > 1 && (
                                <span style={{ color: "#52525b", fontSize: 10, fontFamily: "monospace", marginLeft: 6 }}>
                                  {formatINR(priceInr)} each
                                </span>
                              )}
                            </div>
                            <button
                              onClick={() => removeFromCart(item.product.id, item.size)}
                              style={{
                                background: "none", border: "none",
                                color: "#52525b", fontSize: 12, cursor: "pointer",
                              }}
                              onMouseEnter={e => (e.currentTarget.style.color = "#f87171")}
                              onMouseLeave={e => (e.currentTarget.style.color = "#52525b")}
                            >
                              Remove
                            </button>
                          </div>
                        </div>
                      </motion.div>
                    );
                  })
                )}
              </AnimatePresence>
            </div>

            {/* Footer */}
            {cart.length > 0 && (
              <div style={{ padding: 16, borderTop: "1px solid #1e1e2a", display: "flex", flexDirection: "column", gap: 12 }}>
                
                {/* Coupon UI */}
                <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 8 }}>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input
                      type="text"
                      placeholder="Enter coupon"
                      value={couponCode}
                      onChange={(e) => setCouponCode(e.target.value)}
                      style={{
                        flex: 1,
                        padding: "10px",
                        borderRadius: 8,
                        border: "1px solid #1e1e2a",
                        background: "#0a0a12",
                        color: "#fff",
                      }}
                    />
                    <button
                      onClick={handleApplyCoupon}
                      style={{
                        padding: "10px 14px",
                        background: "#6366f1",
                        color: "#fff",
                        borderRadius: 8,
                        border: "none",
                        cursor: "pointer",
                        fontWeight: "bold",
                      }}
                    >
                      Apply
                    </button>
                  </div>
                  
                  {message && (
                    <p style={{ fontSize: 12, color: message.includes("✅") ? "#4ade80" : "#f87171", margin: 0 }}>
                      {message}
                    </p>
                  )}
                  {discount > 0 && (
                    <p style={{ color: "#4ade80", fontSize: 12, margin: 0 }}>
                      {discount}% discount applied 🎉
                    </p>
                  )}
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
                  <span style={{ color: "#a1a1aa", fontSize: 14 }}>Subtotal</span>
                  <div style={{ textAlign: "right" }}>
                    {discount > 0 && (
                      <div style={{ color: "#71717a", fontSize: 12, textDecoration: "line-through", marginBottom: 2 }}>
                        {formatINR(totalInr)}
                      </div>
                    )}
                    <div style={{ color: "#fff", fontSize: 20, fontWeight: 700 }}>
                      {discount > 0 ? formatINR(finalTotal) : formatINR(totalInr)}
                    </div>
                  </div>
                </div>

                {/* 🟢 STEP 2 — Attach onClick and loading state */}
                <motion.button
                  whileTap={{ scale: 0.98 }}
                  onClick={handleCheckout}
                  disabled={isCheckingOut}
                  style={{
                    width: "100%", padding: "14px 0",
                    background: isCheckingOut ? "#d97706" : "#fbbf24", 
                    color: "#000",
                    fontWeight: 700, fontSize: 14,
                    border: "none", borderRadius: 12, 
                    cursor: isCheckingOut ? "not-allowed" : "pointer",
                    opacity: isCheckingOut ? 0.7 : 1,
                  }}
                  onMouseEnter={e => !isCheckingOut && (e.currentTarget.style.background = "#fcd34d")}
                  onMouseLeave={e => !isCheckingOut && (e.currentTarget.style.background = "#fbbf24")}
                >
                  {isCheckingOut ? "Processing..." : `Checkout · ${discount > 0 ? formatINR(finalTotal) : formatINR(totalInr)}`}
                </motion.button>
                <p style={{ color: "#3f3f46", fontSize: 10, textAlign: "center", fontFamily: "monospace", margin: 0 }}>
                  Prices reflect real-time demand at time of add
                </p>
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}