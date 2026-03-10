"use client";

import { useState } from "react";
import { Sidebar } from "@/components/sidebar/Sidebar";
import type { Domain } from "@/lib/types";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [domain, setDomain] = useState<Domain>("personal");
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        domain={domain}
        onDomainChange={setDomain}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />
      <main className="flex-1 flex flex-col overflow-hidden">{children}</main>
    </div>
  );
}
