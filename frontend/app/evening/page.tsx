"use client";

import { useEffect, useState } from "react";
import BriefChat from "@/components/BriefChat";

type Completion = {
  kind: string;
  ref_id: string;
  title: string;
  category?: string;
  completed_at: string;
};

type CalEvent = { id: string; title: string; start: string; location?: string };
type BacklogLeft = { id: string; title: string; urgency: string };

type EveningBrief = {
  generated_at: string;
  completions: Completion[];
  missed_calendar: CalEvent[];
  backlog_left: BacklogLeft[];
  tomorrow: { title: string; start: string }[];
  ai_brief: string;
  engine_used: string;
  model_used: string;
};

export default function EveningPage() {
  const [data, setData] = useState<EveningBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [engine, setEngine] = useState("claude");

  const load = (e?: string) => {
    setLoading(true);
    setError(null);
    fetch(`/api/evening-brief?engine=${encodeURIComponent(e ?? engine)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((er: Error) => setError(er.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load("claude");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex-1 overflow-y-auto">
      <div
        className="px-8 pt-12 pb-10"
        style={{
          background:
            "radial-gradient(ellipse at top left, rgba(124, 58, 237, 0.18), transparent 60%), radial-gradient(ellipse at top right, rgba(244, 114, 182, 0.10), transparent 50%)",
        }}
      >
        <div className="max-w-4xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            Evening Reflection
          </p>
          <h1
            className="text-5xl font-bold tracking-tight leading-tight"
            style={{
              background: "linear-gradient(135deg, #fafafa 0%, #a78bfa 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            おつかれさま。
          </h1>
          <div className="mt-6 flex items-center gap-3 flex-wrap">
            <button
              onClick={() => load()}
              disabled={loading}
              className="px-5 py-2.5 rounded-full text-sm font-medium disabled:opacity-50"
              style={{ background: "#7c3aed", color: "white", boxShadow: "0 4px 14px rgba(124, 58, 237, 0.35)" }}
            >
              {loading ? "生成中..." : "振り返りを更新"}
            </button>
            {data && (
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                {new Date(data.generated_at).toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" })} / {data.engine_used}
              </span>
            )}
            <select
              value={engine}
              onChange={(e) => {
                setEngine(e.target.value);
                load(e.target.value);
              }}
              className="px-3 py-1.5 rounded text-xs"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
            >
              <option value="claude">Claude</option>
              <option value="gpt">GPT</option>
              <option value="gemini">Gemini</option>
              <option value="grok">Grok</option>
            </select>
          </div>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-4xl mx-auto space-y-6">
          {error && (
            <div className="p-4 rounded-2xl text-sm" style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid var(--color-red)", color: "var(--color-red)" }}>
              読み込み失敗: {error}
            </div>
          )}

          {data && (
            <>
              <div
                className="rounded-3xl p-7"
                style={{
                  background: "linear-gradient(135deg, rgba(124, 58, 237, 0.12) 0%, rgba(244, 114, 182, 0.06) 100%)",
                  border: "1px solid rgba(124, 58, 237, 0.25)",
                }}
              >
                <div className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "#a78bfa" }}>
                  Koach から
                </div>
                <div className="text-[15px] whitespace-pre-wrap leading-[1.85]">{data.ai_brief}</div>
              </div>

              {/* 対話レイヤー (Worklog Phase B-2) — 振り返りを往復にする */}
              <BriefChat mode="evening" engine={engine} />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Section title="今日完了したこと" count={data.completions.length} icon="✓">
                  {data.completions.length === 0 ? (
                    <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                      まだ何も記録されていません
                    </p>
                  ) : (
                    <ul className="space-y-2">
                      {data.completions.map((c, i) => (
                        <li key={i} className="text-sm flex gap-3 items-start">
                          <span
                            className="font-mono text-xs shrink-0 mt-0.5"
                            style={{ color: "var(--color-text-muted)" }}
                          >
                            {c.completed_at.slice(11, 16)}
                          </span>
                          <span>{c.title}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Section>

                <Section title="取りこぼした予定" count={data.missed_calendar.length} icon="⊘">
                  {data.missed_calendar.length === 0 ? (
                    <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                      なし
                    </p>
                  ) : (
                    <ul className="space-y-2">
                      {data.missed_calendar.map((ev) => (
                        <li key={ev.id} className="text-sm flex gap-3 items-start">
                          <span
                            className="font-mono text-xs shrink-0 mt-0.5"
                            style={{ color: "var(--color-text-muted)" }}
                          >
                            {ev.start.slice(11, 16) || "終日"}
                          </span>
                          <span>{ev.title}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Section>
              </div>

              <Section title="明日に繰越し候補" count={data.backlog_left.length} icon="↩">
                {data.backlog_left.length === 0 ? (
                  <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                    バックログなし
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {data.backlog_left.map((b) => (
                      <li key={b.id} className="text-sm flex gap-2 items-center">
                        <span
                          className="px-1.5 py-0.5 rounded text-[10px] font-mono"
                          style={{
                            background:
                              b.urgency === "high"
                                ? "rgba(239,68,68,0.15)"
                                : b.urgency === "medium"
                                ? "rgba(245,158,11,0.15)"
                                : "rgba(113,113,122,0.15)",
                            color: b.urgency === "high" ? "#ef4444" : b.urgency === "medium" ? "#f59e0b" : "#71717a",
                          }}
                        >
                          {b.urgency}
                        </span>
                        {b.title}
                      </li>
                    ))}
                  </ul>
                )}
              </Section>

              <Section title="明日の予定" count={data.tomorrow.length} icon="→">
                {data.tomorrow.length === 0 ? (
                  <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                    予定なし
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {data.tomorrow.map((ev, i) => (
                      <li key={i} className="text-sm flex gap-3 items-start">
                        <span
                          className="font-mono text-xs shrink-0 mt-0.5"
                          style={{ color: "var(--color-text-muted)" }}
                        >
                          {ev.start.length > 10 ? ev.start.slice(11, 16) : "終日"}
                        </span>
                        <span>{ev.title}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({ title, count, icon, children }: { title: string; count: number; icon: string; children: React.ReactNode }) {
  return (
    <section
      className="rounded-2xl p-6"
      style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
    >
      <header className="flex items-center justify-between mb-4">
        <h2 className="font-semibold flex items-center gap-2">
          <span className="text-lg">{icon}</span>
          <span>{title}</span>
        </h2>
        <span
          className="text-xs font-mono px-2 py-0.5 rounded-full"
          style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}
        >
          {count}
        </span>
      </header>
      {children}
    </section>
  );
}
