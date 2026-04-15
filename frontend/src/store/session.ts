"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { CartItem, Product } from "@/types";

function generateSessionId(): string {
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
  let id = "sess_";
  for (let i = 0; i < 24; i++) {
    id += chars[Math.floor(Math.random() * chars.length)];
  }
  return id;
}

interface SessionStore {
  sessionId: string;
  userId: string | null;
  userSegment: string;
  personaId: string | null;
  personaName: string | null;

  accessToken: string | null;
  userRole: "user" | "vendor" | null;

  cart: CartItem[];
  viewedProducts: string[];
  totalEvents: number;
  engagementScore: number;

  setPersona: (id: string, name: string, segment: string) => void;
  setUserSegment: (segment: string) => void;

  setAuth: (token: string, role: "user" | "vendor", userId: string) => void;
  clearAuth: () => void;

  addToCart: (product: Product, size: string, price: number) => void;
  removeFromCart: (productId: string, size: string) => void;
  clearCart: () => void;

  recordProductView: (productId: string) => void;
  incrementEvents: () => void;
  addEngagement: (delta: number) => void;

  cartTotal: () => number;
  cartCount: () => number;
}

export const useSessionStore = create<SessionStore>()(
  persist(
    (set, get) => ({
      sessionId: generateSessionId(),
      userId: null,
      userSegment: "returning",
      personaId: null,
      personaName: null,

      accessToken: null,
      userRole: null,

      cart: [],
      viewedProducts: [],
      totalEvents: 0,
      engagementScore: 0,

      setAuth: (token, role, userId) => {
        set({ accessToken: token, userRole: role, userId });
      },

      clearAuth: () => {
        set({
          accessToken: null,
          userRole: null,
          userId: null,
          personaId: null,
          personaName: null,
        });
      },

      setPersona: (id, name, segment) => {
        set({
          personaId: id,
          personaName: name,
          userSegment: segment,
          sessionId: generateSessionId(),
        });
      },

      setUserSegment: (segment) => set({ userSegment: segment }),

      addToCart: (product, size, price) =>
        set((state) => {
          const existing = state.cart.find(
            (i) => i.product.id === product.id && i.size === size
          );

          if (existing) {
            return {
              cart: state.cart.map((i) =>
                i.product.id === product.id && i.size === size
                  ? { ...i, quantity: i.quantity + 1 }
                  : i
              ),
            };
          }

          return {
            cart: [
              ...state.cart,
              { product, size, quantity: 1, price_at_add: price },
            ],
          };
        }),

      removeFromCart: (productId, size) =>
        set((state) => ({
          cart: state.cart.filter(
            (i) => !(i.product.id === productId && i.size === size)
          ),
        })),

      clearCart: () => set({ cart: [] }),

      recordProductView: (productId) =>
        set((state) => ({
          viewedProducts: state.viewedProducts.includes(productId)
            ? state.viewedProducts
            : [...state.viewedProducts.slice(-49), productId],
        })),

      incrementEvents: () =>
        set((state) => ({ totalEvents: state.totalEvents + 1 })),

      addEngagement: (delta) =>
        set((state) => ({
          engagementScore: Math.max(0, state.engagementScore + delta),
        })),

      cartTotal: () =>
        get().cart.reduce(
          (sum, i) => sum + i.price_at_add * i.quantity,
          0
        ),

      cartCount: () =>
        get().cart.reduce((sum, i) => sum + i.quantity, 0),
    }),
    {
      name: "velocity-store",
      partialize: (state) => ({
        cart: state.cart,
        userId: state.userId,
        accessToken: state.accessToken,
        userRole: state.userRole,
        personaId: state.personaId,
        personaName: state.personaName,
        userSegment: state.userSegment,
      }),
    }
  )
);