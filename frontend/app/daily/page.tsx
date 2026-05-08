"use client";

import { useEffect, useState } from "react";

type Event = {
  title: string;
  start: string;
  end: string;
  all_day: boolean;
  location: string;
};

type Decision = {
  title: string;
  reasoning: string;
  timestamp: string;
};

type Failure = {
  what: string;
  lesson: string;
};

type DailyBrief = {
  generated_at: string;
  schedule: Event[];
  gcal_status: "ok" | "not_configured";
  decisions: Decision[];
  topics: string[];
  failures: Failure[];
  ai_brief: string;
};

const card = {
  background: "var(--color-surface)",
  border: "1px solid var(--color-border)",
};

function formatTime(iso: string): string {
  if (!iso) return "";
  if (iso.length <= 10) return "終日";
  const d = new Date(iso);
  return d.toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" });
}

function formatTimestamp(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("ja-JP", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function DailyPage() {
  const [data, setData] = useState<DailyBrief | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    setError(null);
    fetch("/api/daily-brief")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<DailyBrief>;
      })
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Daily Brief</h1>
            {data && (
              <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                {new Date(data.generated_at).toLocaleString("ja-JP", {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                  weekday: "long",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
            )}
          </div>
          <button
            onClick={load}
            disabled={loading}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            style={{ background: "var(--color-accent)", color: "white" }}
          >
            {loading ? "生成中..." : "更新"}
          </button>
        </div>

        {error && (
          <div className="p-4 rounded-xl" style={{ background: "var(--color-surface)", border: "1px solid var(--color-red)" }}>
            <p className="text-sm" style={{ color: "var(--color-red)" }}>
              読み込み失敗: {error}
            </p>
          </div>
        )}

        {loading && !data && (
          <div className="p-8 rounded-xl text-center" style={card}>
            <p style={{ color: "var(--color-text-muted)" }}>Brief を生成しています...</p>
          </div>
        )}

        {data && (
          <>
            {/* AI Brief — 最上段 */}
            <div className="p-5 rounded-xl" style={{ ...card, borderColor: "var(--color-accent)" }}>
              <h2 className="font-semibold mb-3 flex items-center gap-2">
                <span>Koach から</span>
                <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "var(--color-accent)", color: "white" }}>
                  L3
                </span>
              </h2>
              <div
                className="text-sm whitespace-pre-wrap leading-relaxed"
                style={{ color: "var(--color-text)" }}
              >
                {data.ai_brief}
              </div>
            </div>

            {/* Schedule */}
            <div className="p-5 rounded-xl" style={card}>
              <h2 className="font-semibold mb-3">今日の予定</h2>
              {data.gcal_status === "not_configured" ? (
                <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                  Google Calendar 未連携 — Settings から接続してください
                </p>
              ) : data.schedule.length === 0 ? (
                <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>予定なし</p>
              ) : (
                <ul className="space-y-2">
                  {data.schedule.map((ev, i) => (
                    <li key={i} className="flex gap-3 text-sm">
                      <span
                        className="font-mono text-xs pt-0.5 shrink-0"
                        style={{ color: "var(--color-text-muted)", minWidth: "3rem" }}
                      >
                        {formatTime(ev.start)}
                      </span>
                      <div className="flex-1">
                        <span>{ev.title}</span>
                        {ev.location && (
                          <span className="ml-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
                            @ {ev.location}
                          </span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Recent Decisions */}
            <div className="p-5 rounded-xl" style={card}>
              <h2 className="font-semibold mb-3">直近の決定</h2>
              {data.decisions.length === 0 ? (
                <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                  直近3日に登録された決定はありません
                </p>
              ) : (
                <ul className="space-y-3">
                  {data.decisions.map((d, i) => (
                    <li key={i} className="text-sm border-l-2 pl-3" style={{ borderColor: "var(--color-border-light)" }}>
                      <div className="font-medium">{d.title}</div>
                      {d.reasoning && (
                        <div className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                          {d.reasoning}
                        </div>
                      )}
                      <div className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                        {formatTimestamp(d.timestamp)}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Topics + Failures (2 cols) */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-5 rounded-xl" style={card}>
                <h2 className="font-semibold mb-3">直近の話題</h2>
                {data.topics.length === 0 ? (
                  <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>会話履歴なし</p>
                ) : (
                  <ul className="space-y-2 text-sm">
                    {data.topics.map((t, i) => (
                      <li key={i} style={{ color: "var(--color-text-muted)" }}>
                        — {t}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="p-5 rounded-xl" style={card}>
                <h2 className="font-semibold mb-3">最近の失敗から</h2>
                {data.failures.length === 0 ? (
                  <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>記録された失敗なし</p>
                ) : (
                  <ul className="space-y-3 text-sm">
                    {data.failures.map((f, i) => (
                      <li key={i}>
                        <div className="font-medium">{f.what}</div>
                        {f.lesson && (
                          <div className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                            学び: {f.lesson}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
