import type { Metadata, Viewport } from "next";
import PwaRegister from "@/components/PwaRegister";
import "@fontsource-variable/roboto-flex";
import "@fontsource/noto-sans-devanagari/400.css";
import "@fontsource/noto-sans-devanagari/600.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vani-Guard: voice payment demo",
  description: "A student research prototype. No real money moves.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Vani-Guard", statusBarStyle: "default" },
  icons: { icon: "/icons/icon-192.png", apple: "/icons/icon-192.png" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [{ media: "(prefers-color-scheme: light)", color: "#00696b" }, { media: "(prefers-color-scheme: dark)", color: "#0e1415" }],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full bg-surface font-sans text-on-surface">
        {children}
        <PwaRegister />
      </body>
    </html>
  );
}
