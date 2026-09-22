import type { Metadata } from "next";
import "./globals.css";
import { NavBar } from "@/components/NavBar";

export const metadata: Metadata = {
  title: "OrbiFlare -- Explainable Thermal Behaviour Intelligence",
  description: "AI-based detection and classification of industrial fires and persistent thermal sources using NASA FIRMS, OSM & satellite data.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-base-950 text-base-100 antialiased">
        <NavBar />
        <main className="mx-auto max-w-[1600px] px-4 py-5">{children}</main>
      </body>
    </html>
  );
}
