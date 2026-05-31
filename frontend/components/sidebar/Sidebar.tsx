"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { DomainSelector } from "./DomainSelector";
import type { Domain } from "@/lib/types";

interface Props {
  domain: Domain;
  onDomainChange: (d: Domain) => void;
  isOpen: boolean;
  onToggle: () => void;
}

const NAV_ITEMS = [
  { href: "/daily", label: "Daily", icon: "🌅" },
  { href: "/evening", label: "Evening", icon: "🌙" },
  { href: "/coach", label: "コーチ", icon: "🧭" },
  { href: "/projects", label: "プロジェクト", icon: "🗂" },
  { href: "/focus", label: "Focus", icon: "⏱" },
  { href: "/calendar", label: "カレンダー", icon: "🗓" },
  { href: "/tasks", label: "Tasks", icon: "✅" },
  { href: "/memos", label: "Memos", icon: "🪧" },
  { href: "/gmail-sync", label: "予定を追加", icon: "📅" },
  { href: "/documents", label: "Docs→Tasks", icon: "📄" },
  { href: "/training", label: "Training", icon: "💪" },
  { href: "/agent", label: "Agent", icon: "🤖" },
  { href: "/email-watch", label: "対応待ちメール", icon: "📧" },
  { href: "/deep-work", label: "Deep Work 提案", icon: "🪄" },
  { href: "/launcher", label: "AI ランチャー", icon: "🚀" },
  { href: "/personas", label: "多視点で考える", icon: "🎭" },
  { href: "/extract", label: "動画→構造化", icon: "🎬" },
  { href: "/dispatcher", label: "AI 外注 (指示書)", icon: "📨" },
  { href: "/ask", label: "過去に聞く", icon: "🔎" },
  { href: "/kpi", label: "KPI", icon: "📈" },
  { href: "/", label: "Chat", icon: "💬" },
  { href: "/private", label: "プライベート", icon: "🤫" },
  { href: "/analyze", label: "Style", icon: "✍️" },
  { href: "/logs", label: "Logs", icon: "📋" },
  { href: "/review", label: "Review (週)", icon: "📊" },
  { href: "/memory", label: "Memory", icon: "🧠" },
  { href: "/help", label: "使い方", icon: "📖" },
  { href: "/settings", label: "Settings", icon: "⚙️" },
];

export function Sidebar({ domain, onDomainChange, isOpen, onToggle }: Props) {
  const pathname = usePathname();

  return (
    <aside
      className="flex flex-col h-full transition-all duration-200 overflow-hidden"
      style={{
        width: isOpen ? "260px" : "0px",
        background: "var(--color-surface)",
        borderRight: "1px solid var(--color-border)",
      }}
    >
      {/* Header */}
      <div className="p-4 flex items-center justify-between" style={{ borderBottom: "1px solid var(--color-border)" }}>
        <div>
          <h2 className="font-bold text-lg">Koach OS</h2>
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>v2 — SRAP</p>
        </div>
        <button onClick={onToggle} className="p-1 rounded hover:bg-[var(--color-surface-hover)]">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
      </div>

      {/* Domain Selector */}
      <div className="p-3" style={{ borderBottom: "1px solid var(--color-border)" }}>
        <DomainSelector domain={domain} onChange={onDomainChange} />
      </div>

      {/* Navigation — overflow-y-auto + min-h-0 で flex 親内でスクロール可能に */}
      <nav className="flex-1 min-h-0 overflow-y-auto p-2 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors"
              style={{
                background: active ? "var(--color-accent)" : "transparent",
                color: active ? "white" : "var(--color-text-muted)",
              }}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-3 text-xs" style={{ color: "var(--color-text-muted)", borderTop: "1px solid var(--color-border)" }}>
        Opus 4.8 + GPT-5.5
      </div>
    </aside>
  );
}
