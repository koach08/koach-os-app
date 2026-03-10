import type { Metadata, Viewport } from "next";
import { Noto_Sans_JP, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { BottomNav } from "@/components/layout/bottom-nav";
import { Providers } from "@/components/providers";
import { Toaster } from "@/components/ui/sonner";

const notoSansJP = Noto_Sans_JP({
  variable: "--font-noto-sans",
  subsets: ["latin"],
  weight: ["400", "500", "700", "900"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

export const metadata: Metadata = {
  title: "Schedule Manager",
  description: "仕事・研究・トレーニング・家族時間を管理",
};

export const viewport: Viewport = {
  themeColor: "#08080d",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body
        className={`${notoSansJP.variable} ${jetbrainsMono.variable} font-sans antialiased`}
      >
        <Providers>
          <main className="min-h-screen pb-safe">{children}</main>
          <BottomNav />
          <Toaster theme="dark" />
        </Providers>
      </body>
    </html>
  );
}
