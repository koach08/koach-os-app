"use client";

import { useEffect, useState } from "react";

type Event = {
  id?: string;
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

type BacklogItem = {
  id: string;
  title: string;
  category: string;
  urgency: "high" | "medium" | "low";
  estimated_minutes: number;
  needs_ai: boolean;
};

type Completion = {
  kind: "calendar" | "backlog";
  ref_id: string;
  title: string;
  date: string;
  category?: string;
  completed_at: string;
};

type DailyBrief = {
  generated_at: string;
  schedule: Event[];
  schedule_tomorrow?: Event[];
  schedule_week?: (Event & { event_type?: string })[];
  gcal_status: "ok" | "not_configured";
  decisions: Decision[];
  topics: string[];
  failures: Failure[];
  backlog?: BacklogItem[];
  completions_today?: Completion[];
  ai_brief: string;
  engine_used: string;
  model_used: string;
};

const ENGINES: { value: string; label: string; emoji: string; hint: string }[] = [
  { value: "claude", label: "Claude", emoji: "🧠", hint: "思考・戦略" },
  { value: "gpt", label: "GPT", emoji: "🤖", hint: "実行・コード" },
  { value: "grok", label: "Grok", emoji: "🌀", hint: "推論・代替" },
  { value: "gemini", label: "Gemini", emoji: "✨", hint: "長文・解析" },
  { value: "venice", label: "Venice", emoji: "🎭", hint: "制約なし" },
  { value: "perplexity", label: "Perplexity", emoji: "🔍", hint: "Web検索" },
  { value: "groq", label: "Groq", emoji: "⚡", hint: "爆速" },
];

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

type BalanceWarning = { severity: string; category: string; message: string };
type Balance = { warnings: BalanceWarning[]; calendar_minutes_by_category: Record<string, number> };
type KpiMetric = { id: string; label: string; value: number; unit?: string; delta_7d?: number | null; category?: string };
type FamilyEvent = { id: string; title: string; start_iso: string };
type HealthHint = { hint: string; energy_band: string };

export default function DailyPage() {
  const [data, setData] = useState<DailyBrief | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [engine, setEngine] = useState<string>("claude");
  const [completedKeys, setCompletedKeys] = useState<Set<string>>(new Set());
  const [pendingKeys, setPendingKeys] = useState<Set<string>>(new Set());
  const [balance, setBalance] = useState<Balance | null>(null);
  const [kpiMetrics, setKpiMetrics] = useState<KpiMetric[]>([]);
  const [family, setFamily] = useState<FamilyEvent[]>([]);
  const [healthHint, setHealthHint] = useState<HealthHint | null>(null);

  const completionKey = (kind: "calendar" | "backlog", refId: string) =>
    `${kind}:${refId}`;

  const syncCompletionsFromData = (d: DailyBrief) => {
    const keys = new Set<string>();
    (d.completions_today ?? []).forEach((c) => keys.add(completionKey(c.kind, c.ref_id)));
    setCompletedKeys(keys);
  };

  const load = (engineOverride?: string) => {
    const e = engineOverride ?? engine;
    setLoading(true);
    setError(null);
    fetch(`/api/daily-brief?engine=${encodeURIComponent(e)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<DailyBrief>;
      })
      .then((d) => {
        setData(d);
        syncCompletionsFromData(d);
      })
      .catch((er: Error) => setError(er.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load("claude");
    fetch("/api/balance?days=7").then((r) => r.ok ? r.json() : null).then((d) => d && setBalance(d)).catch(() => {});
    fetch("/api/kpi").then((r) => r.ok ? r.json() : null).then((d) => d && setKpiMetrics((d.metrics ?? []).slice(0, 4))).catch(() => {});
    fetch("/api/calendar/family?days_ahead=2").then((r) => r.ok ? r.json() : null).then((d) => d && setFamily(d.events ?? [])).catch(() => {});
    fetch("/api/health-data/state-hint").then((r) => r.ok ? r.json() : null).then((d) => d && setHealthHint(d)).catch(() => {});
    const onCaptured = () => load();
    window.addEventListener("koach-capture-saved", onCaptured);
    return () => window.removeEventListener("koach-capture-saved", onCaptured);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleEngineChange = (e: string) => {
    setEngine(e);
    load(e);
  };

  const deferBacklog = async (id: string, days: number) => {
    try {
      const r = await fetch(`/api/productivity/backlog/${id}/defer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ days }),
      });
      if (r.ok) load();
    } catch {}
  };

  const shiftEvent = async (id: string, days: number) => {
    try {
      const r = await fetch(`/api/calendar/event/${id}/shift`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ days }),
      });
      if (r.ok) load();
    } catch {}
  };

  const toggleCompletion = async (
    kind: "calendar" | "backlog",
    refId: string,
    title: string,
    category = "",
  ) => {
    if (!refId) return;
    const key = completionKey(kind, refId);
    const isDone = completedKeys.has(key);
    setPendingKeys((s) => new Set(s).add(key));
    // optimistic toggle
    setCompletedKeys((s) => {
      const next = new Set(s);
      if (isDone) next.delete(key);
      else next.add(key);
      return next;
    });
    try {
      if (isDone) {
        const params = new URLSearchParams({ ref_id: refId, kind });
        const r = await fetch(`/api/completions?${params.toString()}`, { method: "DELETE" });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
      } else {
        const r = await fetch(`/api/completions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ kind, ref_id: refId, title, category }),
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
      }
    } catch {
      // revert on failure
      setCompletedKeys((s) => {
        const next = new Set(s);
        if (isDone) next.add(key);
        else next.delete(key);
        return next;
      });
    } finally {
      setPendingKeys((s) => {
        const next = new Set(s);
        next.delete(key);
        return next;
      });
    }
  };

  return (
    <div className="flex-1 overflow-y-auto relative pb-32">
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
          <div className="mt-6 flex items-center gap-3 flex-wrap">
            <button
              onClick={() => load()}
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
                })} / {data.engine_used}
              </span>
            )}
          </div>

          {/* KPI mini strip */}
          {kpiMetrics.length > 0 && (
            <div className="mt-6 flex flex-wrap gap-2">
              {kpiMetrics.map((m) => (
                <div
                  key={m.id}
                  className="px-3 py-1.5 rounded-lg text-xs"
                  style={{ background: "rgba(255,255,255,0.04)", border: "1px solid var(--color-border)" }}
                >
                  <span style={{ color: "var(--color-text-muted)" }}>{m.label}</span>
                  <span className="font-mono font-bold ml-2">{m.value.toLocaleString()}</span>
                  <span className="ml-0.5" style={{ color: "var(--color-text-muted)" }}>{m.unit}</span>
                  {m.delta_7d != null && (
                    <span className="ml-2 font-mono" style={{ color: m.delta_7d >= 0 ? "#10b981" : "#ef4444" }}>
                      {m.delta_7d >= 0 ? "▲" : "▼"} {Math.abs(m.delta_7d)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

          {healthHint?.hint && (
            <div
              className="mt-3 inline-block px-3 py-1.5 rounded-full text-xs"
              style={{
                background:
                  healthHint.energy_band === "low"
                    ? "rgba(239, 68, 68, 0.1)"
                    : healthHint.energy_band === "high"
                    ? "rgba(16, 185, 129, 0.1)"
                    : "rgba(255, 255, 255, 0.04)",
                color: healthHint.energy_band === "low" ? "#ef4444" : healthHint.energy_band === "high" ? "#10b981" : "var(--color-text-muted)",
                border: "1px solid var(--color-border)",
              }}
            >
              📊 {healthHint.hint}
            </div>
          )}

          {/* Engine selector pills */}
          <div className="mt-5 flex flex-wrap gap-2">
            {ENGINES.map((e) => {
              const active = engine === e.value;
              return (
                <button
                  key={e.value}
                  onClick={() => handleEngineChange(e.value)}
                  disabled={loading}
                  title={e.hint}
                  className="px-3.5 py-1.5 rounded-full text-xs transition-all disabled:opacity-50"
                  style={{
                    background: active ? "var(--color-text)" : "rgba(255,255,255,0.04)",
                    color: active ? "var(--color-background)" : "var(--color-text-muted)",
                    border: active
                      ? "1px solid var(--color-text)"
                      : "1px solid var(--color-border)",
                    fontWeight: active ? 600 : 400,
                  }}
                >
                  <span className="mr-1">{e.emoji}</span>
                  {e.label}
                </button>
              );
            })}
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

          {balance && balance.warnings.length > 0 && (
            <div className="space-y-2">
              {balance.warnings.map((w, i) => (
                <div
                  key={i}
                  className="p-3 rounded-xl text-sm flex items-start gap-3"
                  style={{
                    background: w.severity === "warn" ? "rgba(239, 68, 68, 0.08)" : "rgba(245, 158, 11, 0.08)",
                    border: `1px solid ${w.severity === "warn" ? "rgba(239, 68, 68, 0.25)" : "rgba(245, 158, 11, 0.25)"}`,
                    color: w.severity === "warn" ? "#ef4444" : "#f59e0b",
                  }}
                >
                  <span>{w.severity === "warn" ? "⚠" : "ℹ"}</span>
                  <span>{w.message}</span>
                </div>
              ))}
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

              {/* Coach バックログ — Daily Brief から直接チェック */}
              {(data.backlog ?? []).length > 0 && (
                <SectionCard
                  emoji="🧭"
                  title="Coach バックログ"
                  count={(data.backlog ?? []).length}
                  empty="バックログなし"
                  isEmpty={false}
                  badge={`${
                    (data.backlog ?? []).filter((b) =>
                      completedKeys.has(completionKey("backlog", b.id))
                    ).length
                  } / ${(data.backlog ?? []).length}`}
                >
                  <ul className="space-y-2.5">
                    {(data.backlog ?? []).map((b) => {
                      const key = completionKey("backlog", b.id);
                      const done = completedKeys.has(key);
                      const pending = pendingKeys.has(key);
                      const urgencyColor =
                        b.urgency === "high"
                          ? "#ef4444"
                          : b.urgency === "medium"
                          ? "#f59e0b"
                          : "#71717a";
                      return (
                        <li key={b.id} className="flex gap-3 items-start">
                          <button
                            onClick={() =>
                              toggleCompletion("backlog", b.id, b.title, b.category)
                            }
                            disabled={pending}
                            aria-label={done ? "完了取り消し" : "完了"}
                            className="mt-1 shrink-0 transition-all"
                            style={{
                              width: "1.1rem",
                              height: "1.1rem",
                              borderRadius: "0.35rem",
                              border: done
                                ? "1px solid var(--color-accent)"
                                : "1px solid var(--color-border)",
                              background: done ? "var(--color-accent)" : "transparent",
                              cursor: "pointer",
                              opacity: pending ? 0.5 : 1,
                              color: "white",
                              fontSize: "0.7rem",
                              lineHeight: 1,
                            }}
                          >
                            {done ? "✓" : ""}
                          </button>
                          <div
                            className="font-mono text-[10px] shrink-0 px-1.5 py-0.5 rounded"
                            style={{
                              background: `${urgencyColor}20`,
                              color: urgencyColor,
                              minWidth: "3rem",
                              textAlign: "center",
                              marginTop: "0.15rem",
                            }}
                          >
                            {b.urgency}
                          </div>
                          <div className="flex-1" style={{ opacity: done ? 0.45 : 1 }}>
                            <div
                              className="text-sm flex items-center gap-2"
                              style={{ textDecoration: done ? "line-through" : "none" }}
                            >
                              <span>{b.title}</span>
                              {!done && (
                                <span className="ml-auto flex gap-1">
                                  {[1, 3, 7].map((d) => (
                                    <button
                                      key={d}
                                      onClick={() => deferBacklog(b.id, d)}
                                      title={`${d} 日後ろにずらす`}
                                      className="text-[10px] px-1.5 py-0.5 rounded font-mono"
                                      style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}
                                    >
                                      +{d}d
                                    </button>
                                  ))}
                                </span>
                              )}
                            </div>
                            <div
                              className="text-[11px] mt-0.5"
                              style={{ color: "var(--color-text-muted)" }}
                            >
                              {b.category} ・ 推定 {b.estimated_minutes} 分
                            </div>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </SectionCard>
              )}

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
                  badge={
                    data.schedule.length > 0
                      ? `${
                          data.schedule.filter((ev) =>
                            ev.id ? completedKeys.has(completionKey("calendar", ev.id)) : false
                          ).length
                        } / ${data.schedule.length}`
                      : undefined
                  }
                >
                  <ul className="space-y-3">
                    {data.schedule.map((ev, i) => {
                      const key = ev.id ? completionKey("calendar", ev.id) : "";
                      const done = key ? completedKeys.has(key) : false;
                      const pending = key ? pendingKeys.has(key) : false;
                      return (
                        <li key={i} className="flex gap-3 items-start">
                          <button
                            onClick={() =>
                              ev.id && toggleCompletion("calendar", ev.id, ev.title)
                            }
                            disabled={!ev.id || pending}
                            aria-label={done ? "完了取り消し" : "完了"}
                            className="mt-1 shrink-0 transition-all"
                            style={{
                              width: "1.1rem",
                              height: "1.1rem",
                              borderRadius: "0.35rem",
                              border: done
                                ? "1px solid var(--color-accent)"
                                : "1px solid var(--color-border)",
                              background: done ? "var(--color-accent)" : "transparent",
                              cursor: ev.id ? "pointer" : "not-allowed",
                              opacity: pending ? 0.5 : 1,
                              color: "white",
                              fontSize: "0.7rem",
                              lineHeight: 1,
                            }}
                          >
                            {done ? "✓" : ""}
                          </button>
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
                          <div className="flex-1 pt-0.5" style={{ opacity: done ? 0.45 : 1 }}>
                            <div className="flex items-center gap-2">
                              <span
                                className="text-sm font-medium flex-1"
                                style={{ textDecoration: done ? "line-through" : "none" }}
                              >
                                {ev.title}
                              </span>
                              {!done && ev.id && (
                                <span className="flex gap-1">
                                  {[1, 7].map((d) => (
                                    <button
                                      key={d}
                                      onClick={() => ev.id && shiftEvent(ev.id, d)}
                                      title={`予定を ${d} 日後ろにずらす`}
                                      className="text-[10px] px-1.5 py-0.5 rounded font-mono"
                                      style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}
                                    >
                                      +{d}d
                                    </button>
                                  ))}
                                </span>
                              )}
                            </div>
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
                      );
                    })}
                  </ul>
                </SectionCard>

                <SectionCard
                  emoji="🌅"
                  title="明日の予定"
                  count={(data.schedule_tomorrow ?? []).length}
                  empty={data.gcal_status === "not_configured" ? "未連携" : "予定なし"}
                  isEmpty={(data.schedule_tomorrow ?? []).length === 0}
                >
                  <ul className="space-y-3">
                    {(data.schedule_tomorrow ?? []).map((ev, i) => (
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
                            <div className="text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>
                              📍 {ev.location}
                            </div>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </SectionCard>
              </div>

              {family.length > 0 && (
                <SectionCard
                  emoji="👨‍👩‍👧"
                  title="家族カレンダー"
                  count={family.length}
                  empty=""
                  isEmpty={false}
                >
                  <ul className="space-y-2">
                    {family.slice(0, 8).map((ev) => {
                      const d = new Date(ev.start_iso);
                      const label = d.toLocaleString("ja-JP", { month: "numeric", day: "numeric", weekday: "short" });
                      const time = ev.start_iso.length > 10 ? ev.start_iso.slice(11, 16) : "終日";
                      return (
                        <li key={ev.id} className="flex gap-3 items-center text-sm">
                          <span
                            className="font-mono text-[11px] shrink-0 px-2 py-0.5 rounded"
                            style={{ background: "rgba(244, 114, 182, 0.15)", color: "#f472b6", minWidth: "4.5rem", textAlign: "center" }}
                          >
                            {label}
                          </span>
                          <span className="font-mono text-xs" style={{ color: "var(--color-text-muted)", minWidth: "3rem" }}>
                            {time}
                          </span>
                          <span className="flex-1">{ev.title}</span>
                        </li>
                      );
                    })}
                  </ul>
                </SectionCard>
              )}

              {/* 今週 (7日) */}
              <SectionCard
                emoji="📆"
                title="今週の予定"
                count={(data.schedule_week ?? []).length}
                empty={data.gcal_status === "not_configured" ? "Google Calendar 未連携" : "予定なし"}
                isEmpty={(data.schedule_week ?? []).length === 0}
              >
                <ul className="space-y-2">
                  {(data.schedule_week ?? []).map((ev, i) => {
                    const d = new Date(ev.start);
                    const label = d.toLocaleString("ja-JP", {
                      month: "numeric",
                      day: "numeric",
                      weekday: "short",
                    });
                    const typeColors: Record<string, string> = {
                      meeting: "#3b82f6",
                      committee: "#a855f7",
                      deadline: "#ef4444",
                      default: "#71717a",
                    };
                    const color = typeColors[ev.event_type ?? "default"];
                    return (
                      <li key={i} className="flex gap-3 items-center">
                        <div
                          className="font-mono text-[11px] shrink-0 px-2 py-0.5 rounded"
                          style={{ background: `${color}20`, color, minWidth: "4.5rem", textAlign: "center" }}
                        >
                          {label}
                        </div>
                        <div className="font-mono text-xs" style={{ color: "var(--color-text-muted)", minWidth: "3rem" }}>
                          {formatTime(ev.start)}
                        </div>
                        <div className="flex-1 text-sm">{ev.title}</div>
                        {ev.location && (
                          <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                            📍 {ev.location}
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </SectionCard>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
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
  badge,
}: {
  emoji: string;
  title: string;
  count: number;
  empty: string;
  isEmpty: boolean;
  children: React.ReactNode;
  badge?: string;
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
            {badge ?? count}
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
