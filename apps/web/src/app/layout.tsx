import type { Metadata } from "next";
import { Bricolage_Grotesque, JetBrains_Mono, Public_Sans } from "next/font/google";
import "./globals.css";

const display = Bricolage_Grotesque({ variable: "--font-display-face", subsets: ["latin"], display: "swap" });
const body = Public_Sans({ variable: "--font-body", subsets: ["latin"], display: "swap" });
const code = JetBrains_Mono({ variable: "--font-code", subsets: ["latin"], weight: ["400", "500"], display: "swap" });

export const metadata: Metadata = {
  title: "PayPilot AI: safe payments you can explain",
  description:
    "Tell PayPilot who to pay. AI reads the request, policy checks it, you approve, PayPal processes it, and every step is recorded.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${code.variable} antialiased`}>
      <body className="min-h-dvh bg-cloud text-ink">{children}</body>
    </html>
  );
}
