"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Dumbbell,
  CheckSquare,
  ScanSearch,
  Settings,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "ホーム", icon: LayoutDashboard },
  { href: "/tasks", label: "タスク", icon: CheckSquare },
  { href: "/training", label: "トレーニング", icon: Dumbbell },
  { href: "/scan", label: "スキャン", icon: ScanSearch },
  { href: "/settings", label: "設定", icon: Settings },
];

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-[#0a0a12]/95 backdrop-blur-md">
      <div className="mx-auto flex max-w-lg items-center justify-around px-2 pb-[env(safe-area-inset-bottom,0px)]">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center gap-0.5 px-3 py-2.5 text-[10px] font-medium transition-colors ${
                isActive
                  ? "text-[var(--color-cat-training)]"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Icon className="h-5 w-5" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
