"use client";
import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { FALLBACK_PRODUCTS } from "@/lib/catalog";
import { formatINR } from "@/lib/currency";

interface Toast {
  id: string;
  message: string;
  sub?: string;
  type: "purchase" | "viewing" | "price" | "stock";
}

// Use FALLBACK_PRODUCTS (the correct export name) with a runtime guard
const PRODUCTS = FALLBACK_PRODUCTS ?? [];

const NAMES = [
  "Rahul K.", "Priya S.", "Arjun M.", "Neha T.", "Vikram P.",
  "Ananya R.", "Rohan D.", "Shreya B.", "Kiran J.", "Aditya N.",
  "Meera V.", "Siddharth L.", "Kavya H.", "Arnav G.", "Ishaan C.",
];

const CITIES = [
  "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Pune",
  "Chennai", "Kolkata", "Ahmedabad",
];

// Safe random element — returns undefined if array is empty
function randomEl<T>(arr: T[]): T | undefined {
  if (!arr || arr.length === 0) return undefined;
  return arr[Math.floor(Math.random() * arr.length)];
}

function generateToast(): Toast | null {
  const product = randomEl(PRODUCTS);
  const name    = randomEl(NAMES);
  const city    = randomEl(CITIES);

  // Guard: if catalog isn't ready yet, skip
  if (!product || !name || !city) return null;

  const viewerCount = 18 + Math.floor(Math.random() * 70);
  const roll = Math.random();

  if (roll < 0.35) {
    return {
      id: Math.random().toString(36).slice(2),
      type: "purchase",
      message: `👟 ${name} just bought ${product.name}`,
      sub: `${city} · ${formatINR(product.base_price)}`,
    };
  } else if (roll < 0.60) {
    return {
      id: Math.random().toString(36).slice(2),
      type: "viewing",
      message: `🔥 ${viewerCount} people viewing this drop`,
      sub: `${product.name} · demand surging`,
    };
  } else if (roll < 0.80) {
    return {
      id: Math.random().toString(36).slice(2),
      type: "price",
      message: `📈 Price updated · ${product.name}`,
      sub: `Real-time demand signal detected`,
    };
  } else {
    const left = 1 + Math.floor(Math.random() * 5);
    return {
      id: Math.random().toString(36).slice(2),
      type: "stock",
      message: `⚡ Only ${left} left — ${product.name}`,
      sub: `${city} warehouse · scarcity pricing active`,
    };
  }
}

const TYPE_STYLES: Record<Toast["type"], string> = {
  purchase: "border-emerald-500/20 bg-emerald-500/8",
  viewing:  "border-orange-500/20 bg-orange-500/8",
  price:    "border-amber-500/20 bg-amber-500/8",
  stock:    "border-red-500/20 bg-red-500/8",
};

export function LiveToasts() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback(() => {
    const toast = generateToast();
    if (!toast) return; // catalog not ready — skip silently

    setToasts((prev) => [toast, ...prev].slice(0, 4));
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== toast.id));
    }, 4000);
  }, []);

  useEffect(() => {
    // First toast after 2s, then random intervals 4–12s
    const initial = setTimeout(addToast, 2000);

    let recurringTimer: ReturnType<typeof setTimeout>;
    const schedule = () => {
      const delay = 4000 + Math.random() * 8000;
      recurringTimer = setTimeout(() => {
        addToast();
        schedule();
      }, delay);
    };
    schedule();

    return () => {
      clearTimeout(initial);
      clearTimeout(recurringTimer);
    };
  }, [addToast]);

  return (
    <div className="fixed bottom-4 left-4 z-50 flex flex-col gap-2 max-w-xs pointer-events-none">
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            layout
            initial={{ opacity: 0, x: -20, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: -20, scale: 0.95 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className={`glass rounded-xl px-3.5 py-2.5 border ${TYPE_STYLES[toast.type]} shadow-card`}
          >
            <p className="text-white text-xs font-500 leading-snug">{toast.message}</p>
            {toast.sub && (
              <p className="text-zinc-500 text-[10px] font-mono mt-0.5">{toast.sub}</p>
            )}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}