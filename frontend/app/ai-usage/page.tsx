"use client";

import { useEffect, useState } from "react";

type Res = {
  days: number;
  worklog_by_engine: Record<string, number>;
  worklog_engine_by_category: Record<string, Record<string, number>>;
  routine_runs_by_engine: Record<string, number>;
};

function Bars({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  if (entries.length === 0) return <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>データなし</div>;
  return (
    <div className="space-y-1.5">
      {entries.map(([k, n]) => (
        <div key={k} className="flex items-center gap-2 text-xs">
          <span className="w-24 shrink-0 truncate" style={{ color: "var(--color-text-muted)" }}>{k}</span>
          <div className="flex-1 h-4 rounded" style={{ background: "var(--color-background)" }}>
            <div className="h-4 rounded" style={{ width: `${(n / max) * 100}%`, background: "rgba(34,197,94,0.5)", minWidth: "2px" }} />
          </div>
          <span className="w-8 text-right">{n}</span>
        </div>
      ))}
    </div>
  );
}

export default function AiUsagePage() {
  const [data, setData] = useState<Res | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/ai-usage?days=90")
      .then((r) => r.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  const card = { background: "var(--color-surface)", border: "1px solid var(--color-border)" };

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="px-8 pt-10 pb-6" style={{ background: "radial-gradient(ellipse at top right, rgba(34, 197, 94, 0.10), transparent 50%)" }}>
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl font-bold tracking-tight" style={{ background: "linear-gradient(90deg, #fafafa 0%, #a1a1aa 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            AI 利用ダッシュボード
          </h1>
          <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>
            実績ログ(work_log)の engine タグと routine 実行から「どの AI を・どの作業に・どれだけ」を集計(直近90日)
          </p>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-4xl mx-auto space-y-4">
          {loading ? (
            <div className="text-sm" style={{ color: "var(--color-text-muted)" }}>読み込み中...</div>
          ) : !data ? null : (
            <>
              <div className="rounded-2xl p-4" style={card}>
                <h2 className="text-sm font-medium mb-3">実績ログ: 使った AI</h2>
                <Bars data={data.worklog_by_engine} />
              </div>

              <div className="rounded-2xl p-4" style={card}>
                <h2 className="text-sm font-medium mb-3">作業カテゴリ別の AI 使用</h2>
                {Object.keys(data.worklog_engine_by_category).length === 0 ? (
                  <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                    まだデータがありません。実績ログで「使った AI」を記録すると、ここに偏り(慣れで同じ AI に投げている等)が出ます
                  </div>
                ) : (
                  <div className="space-y-3">
                    {Object.entries(data.worklog_engine_by_category).map(([cat, m]) => (
                      <div key={cat}>
                        <div className="text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>{cat}</div>
                        <div className="flex flex-wrap gap-1.5">
                          {Object.entries(m).sort((a, b) => b[1] - a[1]).map(([e, n]) => (
                            <span key={e} className="px-2 py-0.5 rounded-full text-[11px]" style={{ background: "rgba(34,197,94,0.12)", border: "1px solid rgba(34,197,94,0.4)" }}>
                              {e} · {n}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-2xl p-4" style={card}>
                <h2 className="text-sm font-medium mb-3">ルーティン実行で使った AI</h2>
                <Bars data={data.routine_runs_by_engine} />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
