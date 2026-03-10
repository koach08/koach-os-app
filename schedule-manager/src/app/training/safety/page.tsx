"use client";

import { useState } from "react";
import Link from "next/link";
import { INJURY_PREVENTION, KAJABI_INFO } from "@/lib/training-data";
import { ChevronLeft, ChevronDown, ChevronUp } from "lucide-react";

export default function SafetyPage() {
  const [showKajabi, setShowKajabi] = useState(false);
  const [expandedItems, setExpandedItems] = useState<Record<number, boolean>>(
    {}
  );

  const toggleItem = (idx: number) => {
    setExpandedItems((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  return (
    <div className="min-h-screen px-4 py-6">
      <div className="mx-auto max-w-lg">
        <Link
          href="/training"
          className="mb-4 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-4 w-4" />
          トレーニングに戻る
        </Link>

        <h1 className="mb-1 text-xl font-black text-[var(--color-cat-deadline)]">
          {INJURY_PREVENTION.title}
        </h1>
        <p className="mb-6 text-xs text-muted-foreground">
          40代からのアクロバット。安全第一で進める。
        </p>

        {/* Injury prevention items */}
        <div className="space-y-2">
          {INJURY_PREVENTION.items.map((item, i) => (
            <div
              key={i}
              className="overflow-hidden rounded-xl border border-[#2a1a22] bg-[#14111a]"
            >
              <button
                onClick={() => toggleItem(i)}
                className="flex w-full items-center gap-2 px-3 py-3 text-left"
              >
                <span className="text-lg">{item.icon}</span>
                <span className="flex-1 text-xs font-bold text-[#ee8888]">
                  {item.title}
                </span>
                {expandedItems[i] ? (
                  <ChevronUp className="h-4 w-4 text-[#ee8888]" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-[#ee8888]" />
                )}
              </button>
              {expandedItems[i] && (
                <div className="px-3 pb-3 text-[11px] leading-relaxed text-[#aa8888]">
                  {item.desc}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Kajabi Info */}
        <div className="mt-6">
          <button
            onClick={() => setShowKajabi(!showKajabi)}
            className="flex w-full items-center justify-between rounded-xl border border-[#2a2a3e] bg-[#12121f] px-4 py-3 text-left"
          >
            <span className="text-[13px] font-bold text-[#88aaff]">
              {KAJABI_INFO.title}
            </span>
            {showKajabi ? (
              <ChevronUp className="h-4 w-4 text-[#88aaff]" />
            ) : (
              <ChevronDown className="h-4 w-4 text-[#88aaff]" />
            )}
          </button>

          {showKajabi && (
            <div className="rounded-b-xl border border-t-0 border-[#2a2a3e] bg-[#0e0e1a] p-4">
              {KAJABI_INFO.methods.map((m, i) => (
                <div key={i} className="mb-4 last:mb-0">
                  <h4 className="mb-2 text-[13px] font-bold text-[#aabbff]">
                    {m.name}
                  </h4>
                  {m.steps.map((s, si) => (
                    <div
                      key={si}
                      className="mb-1 flex gap-2 text-xs text-[#8899aa]"
                    >
                      <span className="flex-shrink-0 text-[#556677]">
                        {si + 1}.
                      </span>
                      <span>{s}</span>
                    </div>
                  ))}
                  <div className="mt-2 rounded-md bg-[#1a1815] px-2.5 py-1.5 text-[11px] text-[#887766]">
                    {m.note}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
