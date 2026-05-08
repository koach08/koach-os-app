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

function formatGreeting(): string {
  const h = new Date().getHours();
  if (h < 5) return "深夜";
  if (h < 11) return "おはよう";
  if (h < 17) return "こんにちは";
  return "こんばんは";
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
    <div className="flex-1 overflow-y-auto">
      {/* Hero header — full bleed gradient */}
      <div
        className="px-8 pt-12 pb-10 relative overflow-hidden"
        style={{
          background:
            "radial-gradient(ellipse at top left, rgba(59, 130, 246, 0.18), transparent 60%), radial-gradient(ellipse at top right, rgba(234, 179, 8, 0.10), transparent 50%)",
        }}
      >
        <div className="max-w-5xl mx-auto">
          <p
            className="text-xs uppercase tracking-widest mb-2"
            style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}
          >
            {data
              ? new Date(data.generated_at).toLocaleDateString("ja-JP", {
                  weekday: "long",
                  month: "long",
                  day: "numeric",
                })
              : "Loading"}
          </p>
          <h1
            className="text-5xl font-bold tracking-tight leading-tight"
            style={{
              background:
                "linear-gradient(135deg, #fafafa 0%, #a1a1aa 60%, #71717a 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            {formatGreeting()}。
          </h1>
          <div className="mt-6 flex items-center gap-3">
            <button
              onClick={load}
              disabled={loading}
              className="px-5 py-2.5 rounded-full text-sm font-medium transition-all disabled:opacity-50 hover:scale-[1.02]"
              style={{
                background: "var(--color-accent)",
                color: "white",
                boxShadow: "0 4px 14px rgba(59, 130, 246, 0.35)",
              }}
            >
              {loading ? "生成中..." : "Brief を更新"}
            </button>
            {data && (
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                {new Date(data.generated_at).toLocaleTimeString("ja-JP", {
                  hour: "2-digit",
                  minute: "2-digit",
                })} 更新
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-5xl mx-auto space-y-6">
          {error && (
            <div
              className="p-4 rounded-2xl text-sm"
              style={{
                background: "rgba(239, 68, 68, 0.08)",
                border: "1px solid var(--color-red)",
                color: "var(--color-red)",
              }}
            >
              読み込み失敗: {error}
            </div>
          )}

          {loading && !data && (
            <div className="space-y-4 animate-pulse">
              <div className="h-32 rounded-2xl" style={{ background: "var(--color-surface)" }} />
              <div className="h-24 rounded-2xl" style={{ background: "var(--color-surface)" }} />
              <div className="h-24 rounded-2xl" style={{ background: "var(--color-surface)" }} />
            </div>
          )}

          {data && (
            <>
              {/* AI Brief — premium card */}
              <div
                className="rounded-3xl p-7 relative overflow-hidden"
                style={{
                  background:
                    "linear-gradient(135deg, rgba(59, 130, 246, 0.12) 0%, rgba(168, 85, 247, 0.06) 100%)",
                  border: "1px solid rgba(59, 130, 246, 0.25)",
                }}
              >
                <div
                  className="absolute top-0 right-0 w-64 h-64 rounded-full opacity-20 blur-3xl"
                  style={{ background: "var(--color-accent)" }}
                />
                <div className="relative">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <span
                        className="w-2 h-2 rounded-full animate-pulse"
                        style={{ background: "var(--color-accent)" }}
                      />
                      <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--color-accent)" }}>
                        Koach から
                      </span>
                    </div>
                    <span
                      className="text-[10px] font-mono px-2 py-0.5 rounded-full"
                      style={{ background: "rgba(245, 158, 11, 0.12)", color: "#f59e0b" }}
                    >
                      L3 介入
                    </span>
                  </div>
                  <div
                    className="text-[15px] whitespace-pre-wrap leading-[1.85]"
                    style={{ color: "var(--color-text)" }}
                  >
                    {data.ai_brief}
                  </div>
                </div>
              </div>

              {/* 2-col layout for schedule + decisions */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <SectionCard
                  emoji="🗓"
                  title="今日の予定"
                  count={data.schedule.length}
                  empty={
                    data.gcal_status === "not_configured"
                      ? "Google Calendar 未連携"
                      : "予定なし"
                  }
                  isEmpty={data.schedule.length === 0}
                >
                  <ul className="space-y-3">
                    {data.schedule.map((ev, i) => (
                      <li key={i} className="flex gap-3">
                        <div
                          className="font-mono text-xs pt-1 shrink-0 px-2.5 py-1 rounded-md"
                          style={{
                            background: "var(--color-surface-hover)",
                            color: "var(--color-text-muted)",
                            minWidth: "3.5rem",
                            textAlign: "center",
                          }}
                        >
                          {formatTime(ev.start)}
                        </div>
                        <div className="flex-1 pt-0.5">
                          <div className="text-sm font-medium">{ev.title}</div>
                          {ev.location && (
                            <div
                              className="text-xs mt-0.5"
                              style={{ color: "var(--color-text-muted)" }}
                            >
                              📍 {ev.location}
                            </div>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </SectionCard>

                <SectionCard
                  emoji="🧭"
                  title="直近の決定"
                  count={data.decisions.length}
                  empty="直近3日に決定なし"
                  isEmpty={data.decisions.length === 0}
                >
                  <ul className="space-y-3">
                    {data.decisions.map((d, i) => (
                      <li
                        key={i}
                        className="border-l-2 pl-3 py-1"
                        style={{ borderColor: "var(--color-accent)" }}
                      >
                        <div className="text-sm font-medium">{d.title}</div>
                        {d.reasoning && (
                          <div
                            className="text-xs mt-1 line-clamp-2"
                            style={{ color: "var(--color-text-muted)" }}
                          >
                            {d.reasoning}
                          </div>
                        )}
                        <div
                          className="text-[10px] mt-1.5 font-mono"
                          style={{ color: "var(--color-text-muted)" }}
                        >
                          {formatTimestamp(d.timestamp)}
                        </div>
                      </li>
                    ))}
                  </ul>
                </SectionCard>
              </div>

              {/* Topics + Failures */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <SectionCard
                  emoji="💭"
                  title="直近の話題"
                  count={data.topics.length}
                  empty="会話履歴なし"
                  isEmpty={data.topics.length === 0}
                >
                  <ul className="space-y-2.5">
                    {data.topics.map((t, i) => (
                      <li
                        key={i}
                        className="text-sm flex gap-2"
                        style={{ color: "var(--color-text-muted)" }}
                      >
                        <span className="shrink-0 mt-1.5">
                          <span
                            className="block w-1 h-1 rounded-full"
                            style={{ background: "var(--color-text-muted)" }}
                          />
                        </span>
                        <span className="leading-relaxed">{t}</span>
                      </li>
                    ))}
                  </ul>
                </SectionCard>

                <SectionCard
                  emoji="🪨"
                  title="最近の失敗から"
                  count={data.failures.length}
                  empty="記録された失敗なし"
                  isEmpty={data.failures.length === 0}
                >
                  <ul className="space-y-3.5">
                    {data.failures.map((f, i) => (
                      <li key={i}>
                        <div className="text-sm font-medium">{f.what}</div>
                        {f.lesson && (
                          <div
                            className="text-xs mt-1.5 italic"
                            style={{ color: "var(--color-text-muted)" }}
                          >
                            → {f.lesson}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                </SectionCard>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function SectionCard({
  emoji,
  title,
  count,
  empty,
  isEmpty,
  children,
}: {
  emoji: string;
  title: string;
  count: number;
  empty: string;
  isEmpty: boolean;
  children: React.ReactNode;
}) {
  return (
    <section
      className="rounded-2xl p-6 transition-all hover:border-[var(--color-border-light)]"
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
      }}
    >
      <header className="flex items-center justify-between mb-4">
        <h2 className="font-semibold flex items-center gap-2">
          <span className="text-lg">{emoji}</span>
          <span>{title}</span>
        </h2>
        {!isEmpty && (
          <span
            className="text-xs font-mono px-2 py-0.5 rounded-full"
            style={{
              background: "var(--color-surface-hover)",
              color: "var(--color-text-muted)",
            }}
          >
            {count}
          </span>
        )}
      </header>
      {isEmpty ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          {empty}
        </p>
      ) : (
        children
      )}
    </section>
  );
}
