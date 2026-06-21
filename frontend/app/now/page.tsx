"use client";

import { useEffect, useState, useCallback } from "react";

type Res = {
  generated_at: string;
  recommendation: string;
  engine_used: string;
  context_counts: Record<string, number>;
};

export default function NowPage() {
  const [data, setData] = useState<Res | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetch("/api/next-action")
      .then((r) => r.json())
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="px-8 pt-10 pb-6" style={{ background: "radial-gradient(ellipse at top right, rgba(245, 158, 11, 0.12), transparent 50%)" }}>
        <div className="max-w-3xl mx-auto">
          <h1 className="text-4xl font-bold tracking-tight" style={{ background: "linear-gradient(90deg, #fafafa 0%, #a1a1aa 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            今、何をやる?
          </h1>
          <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>
            残り予定・対応待ち・期限・直近の動きから、今この瞬間の一手を即断で。迎合しません
          </p>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-3xl mx-auto space-y-4">
          <div className="flex items-center gap-3">
            <button
              onClick={load}
              disabled={loading}
              className="px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50 transition-all hover:scale-[1.02]"
              style={{ background: "var(--color-text)", color: "var(--color-background)" }}
            >
              {loading ? "考え中..." : "今やる一手を出す"}
            </button>
            {data && (
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                予定{data.context_counts.remaining_calendar} / メール{data.context_counts.pending_emails} / backlog{data.context_counts.open_backlog} / タスク{data.context_counts.tasks} · {data.engine_used}
              </span>
            )}
          </div>

          {error && (
            <div className="rounded-2xl p-3 text-sm" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid var(--color-red)", color: "var(--color-red)" }}>
              {error}
            </div>
          )}

          {data && (
            <div
              className="rounded-2xl p-5 text-sm whitespace-pre-wrap leading-relaxed"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
            >
              {data.recommendation}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
