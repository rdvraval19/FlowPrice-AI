import type { Metadata } from "next";
import { Syne, DM_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const syne = Syne({ subsets: ["latin"], variable: "--font-display", weight: ["400","500","600","700","800"] });
const dmSans = DM_Sans({ subsets: ["latin"], variable: "--font-body", weight: ["300","400","500"] });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", weight: ["400","500"] });

export const metadata: Metadata = {
  title: "FlowPriceAI — Real-Time Dynamic Pricing Engine",
  description: "Real-time behavioral signal processing · GRU4Rec recommendations · Sub-200ms p99 latency",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${syne.variable} ${dmSans.variable} ${jetbrainsMono.variable}`}>
      {/* No body background — each page sets its own via storefront-light or dashboard-dark */}
      <body style={{ margin: 0, fontFamily: "var(--font-body)" }} className="antialiased">
        {children}
      </body>
    </html>
  );
}

//frontend\src\app\layout.tsx

//Mine Layout