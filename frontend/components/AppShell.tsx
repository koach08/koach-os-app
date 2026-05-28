"use client";

import { useState } from "react";
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
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const pathname = usePathname();
  const showCapture = !NO_CAPTURE_PATHS.has(pathname || "");

  const broadcastCaptured = () => {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("koach-capture-saved"));
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        domain={domain}
        onDomainChange={setDomain}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />
      <main className="flex-1 flex flex-col overflow-hidden relative">
        {children}
        {showCapture && <QuickCaptureBar onSaved={broadcastCaptured} />}
      </main>
    </div>
  );
}
