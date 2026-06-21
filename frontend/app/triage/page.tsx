"use client";

import { useEffect, useState, useCallback } from "react";

type EmailItem = { subject: string; from: string; urgency: string; deadline_date?: string | null; days_since: number };
type BacklogItem = { title: string; category: string; urgency: string; due_date?: string | null };
type TaskItem = { title: string; due_date?: string | null; status: string; overdue: boolean };

type Res = {
  emails: EmailItem[];
  backlog: BacklogItem[];
  tasks: TaskItem[];
  counts: { emails: number; backlog: number; overdue_tasks: number };
  ai_priorities?: string;
};

const URGENCY_COLOR: Record<string, string> = { high: "#f87171", medium: "#fbbf24", low: "#9ca3af" };

export default function TriagePage() {
  const [data, setData] = useState<Res | null>(null);
  const [loading, setLoading] = useState(true);
  const [aiLoading, setAiLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((ai = false) => {
    if (ai) setAiLoading(true);
    else setLoading(true);
    setError(null);
    fetch(`/api/triage${ai ? "?ai=true" : ""}`)
      .then((r) => r.json())
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => {
        setLoading(false);
        setAiLoading(false);
      });
  }, []);

  useEffect(() => {
    load(false);
  }, [load]);

  const Section = ({ title, count, children }: { title: string; count: number; children: React.ReactNode }) => (
    <div className="rounded-2xl p-4" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
      <h2 className="text-sm font-medium mb-2">
        {title} <span style={{ color: "var(--color-text-muted)" }}>({count})</span>
      </h2>
      <div className="space-y-1.5">{children}</div>
    </div>
  );

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="px-8 pt-10 pb-6" style={{ background: "radial-gradient(ellipse at top right, rgba(239, 68, 68, 0.10), transparent 50%)" }}>
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl font-bold tracking-tight" style={{ background: "linear-gradient(90deg, #fafafa 0%, #a1a1aa 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            未対応の棚卸し
          </h1>
          <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>
            対応待ちメール + バックログ + 期限切れタスクを1画面に。AI に今週の優先順位をつけさせる
          </p>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-4xl mx-auto space-y-4">
          <div className="flex items-center gap-3">
            <button onClick={() => load(true)} disabled={aiLoading || loading} className="px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50 transition-all hover:scale-[1.02]" style={{ background: "var(--color-text)", color: "var(--color-background)" }}>
              {aiLoading ? "優先順位を作成中..." : "AIで優先順位をつける"}
            </button>
            <button onClick={() => load(false)} disabled={loading} className="px-3 py-2 rounded-full text-sm disabled:opacity-50" style={{ border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}>
              再読込
            </button>
          </div>

          {error && <div className="rounded-2xl p-3 text-sm" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid var(--color-red)", color: "var(--color-red)" }}>{error}</div>}

          {data?.ai_priorities && (
            <div className="rounded-2xl p-5 text-sm whitespace-pre-wrap leading-relaxed" style={{ background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.35)", color: "var(--color-text)" }}>
              {data.ai_priorities}
            </div>
          )}

          {loading ? (
            <div className="text-sm" style={{ color: "var(--color-text-muted)" }}>読み込み中...</div>
          ) : data ? (
            <>
              <Section title="📧 対応待ちメール" count={data.counts.emails}>
                {data.emails.length === 0 ? <Empty /> : data.emails.map((e, i) => (
                  <div key={i} className="text-xs flex items-center gap-2">
                    <span style={{ color: URGENCY_COLOR[e.urgency] }}>●</span>
                    <span className="flex-1 truncate">{e.subject}</span>
                    <span style={{ color: "var(--color-text-muted)" }}>{e.days_since}日 {e.deadline_date ? `〆${e.deadline_date}` : ""}</span>
                  </div>
                ))}
              </Section>
              <Section title="🗂 バックログ" count={data.backlog.length}>
                {data.backlog.length === 0 ? <Empty /> : data.backlog.map((b, i) => (
                  <div key={i} className="text-xs flex items-center gap-2">
                    <span style={{ color: URGENCY_COLOR[b.urgency] }}>●</span>
                    <span className="flex-1 truncate">{b.title}</span>
                    <span style={{ color: "var(--color-text-muted)" }}>{b.category}{b.due_date ? ` 〆${b.due_date}` : ""}</span>
                  </div>
                ))}
              </Section>
              <Section title="✅ タスク (期限切れ優先)" count={data.tasks.length}>
                {data.tasks.length === 0 ? <Empty /> : data.tasks.map((t, i) => (
                  <div key={i} className="text-xs flex items-center gap-2">
                    <span style={{ color: t.overdue ? "#f87171" : "#9ca3af" }}>●</span>
                    <span className="flex-1 truncate">{t.title}</span>
                    <span style={{ color: t.overdue ? "#f87171" : "var(--color-text-muted)" }}>{t.due_date || ""}{t.overdue ? " 期限切れ" : ""}</span>
                  </div>
                ))}
              </Section>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Empty() {
  return <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>なし</div>;
}
