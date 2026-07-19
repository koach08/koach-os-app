"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/sidebar/Sidebar";
import { QuickCaptureBar } from "@/components/QuickCaptureBar";
import type { Domain } from "@/lib/types";

// 自前の入力 UI を持つページでは QuickCaptureBar を非表示にする
const NO_CAPTURE_PATHS = new Set([
  "/",
  "/private",
  "/personas",
  "/dispatcher",
  "/ask",
  "/extract",
  "/coach",
  "/gmail-sync",
  "/help",
  "/settings",
  "/share",
  "/agent",
  "/email-watch",
  "/deep-work",
]);

export function AppShell({ children }: { children: React.ReactNode }) {
  const [domain, setDomain] = useState<Domain>("personal");
  // 既定は畳む (モバイル安全)。デスクトップはマウント後に開く
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();
  const showCapture = !NO_CAPTURE_PATHS.has(pathname || "");

  // デスクトップ (>=768px) は初期表示でサイドバーを開く。モバイルは畳んだまま
  useEffect(() => {
    if (typeof window !== "undefined" && window.innerWidth >= 768) {
      setSidebarOpen(true);
    }
  }, []);

  // モバイルでページ遷移したら、開いていたオーバーレイを閉じる
  useEffect(() => {
    if (typeof window !== "undefined" && window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  }, [pathname]);

  const broadcastCaptured = () => {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("koach-capture-saved"));
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* サイドバーを開くハンバーガー — 閉じている間だけ表示 (畳むと開けなくなる問題も解消) */}
      {!sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(true)}
          aria-label="メニューを開く"
          className="fixed top-3 left-3 z-50 rounded-lg p-2 shadow-sm"
          style={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            color: "var(--color-text)",
          }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 6h18M3 12h18M3 18h18" />
          </svg>
        </button>
      )}

      {/* モバイル: 背景タップでサイドバーを閉じる (デスクトップでは非表示) */}
      {sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          aria-hidden
          className="md:hidden fixed inset-0 z-40"
          style={{ background: "rgba(0,0,0,0.45)" }}
        />
      )}

      {/* サイドバー: モバイルはオーバーレイ(fixed)、デスクトップは流し込み(relative)で本文を押す */}
      <div className="fixed md:relative inset-y-0 left-0 z-50 md:z-auto">
        <Sidebar
          domain={domain}
          onDomainChange={setDomain}
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
        />
      </div>

      <main className="flex-1 flex flex-col overflow-hidden relative">
        {children}
        {showCapture && <QuickCaptureBar onSaved={broadcastCaptured} />}
      </main>
    </div>
  );
}
