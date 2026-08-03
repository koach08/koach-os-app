"use client";

import { useState, useEffect } from "react";
import { fetchJSON } from "@/lib/api";

interface Stats {
  total_interactions: number;
  domain_distribution: Record<string, number>;
  level_distribution: Record<string, number>;
  engine_distribution: Record<string, number>;
  bias_frequency: Record<string, number>;
  counterpoint_rate_pct: number;
  period_days: number;
}

type WeeklyAi = {
  review: string;
  completion_count: number;
  decision_count: number;
  failure_count: number;
  focus_minutes_total: number;
  focus_by_category: Record<string, number>;
  engine_used: string;
  generated_at: string;
};

type PendingDecision = {
  id: string;
  title: string;
  timestamp: string;
  chosen?: string;
  domain?: string;
};

export default function ReviewPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [generating, setGenerating] = useState(false);
  const [weekly, setWeekly] = useState<WeeklyAi | null>(null);
  const [loadingAi, setLoadingAi] = useState(false);
  const [pending, setPending] = useState<PendingDecision[]>([]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);

  const loadPending = () => {
    fetch("/api/memory/decisions/pending-outcome?days=14")
      .then((r) => (r.ok ? r.json() : { entries: [] }))
      .then((d) => setPending(d.entries ?? []))
      .catch(() => {});
  };

  useEffect(() => {
    fetchJSON<Stats>("/api/review/stats?days=7").then(setStats).catch(() => {});
    loadPending();
  }, []);

  const recordOutcome = async (id: string, status: "closed" | "revisit") => {
    const outcome = (draft[id] || "").trim();
    if (!outcome || saving) return;
    setSaving(id);
    try {
      const r = await fetch(`/api/memory/decisions/${id}/outcome`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outcome, status }),
      });
      if (r.ok) {
        setPending((xs) => xs.filter((x) => x.id !== id));
        setDraft((d) => {
          const n = { ...d };
          delete n[id];
          return n;
        });
      }
    } finally {
      setSaving(null);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      await fetch("/api/review/generate", { method: "POST" });
      const s = await fetchJSON<Stats>("/api/review/stats?days=7");
      setStats(s);
    } finally {
      setGenerating(false);
    }
  };

  const generateWeekly = async () => {
    setLoadingAi(true);
    try {
      const r = await fetch("/api/weekly-review?engine=claude");
      if (r.ok) setWeekly(await r.json());
    } finally {
      setLoadingAi(false);
    }
  };

  const barWidth = (value: number, max: number) =>
    max > 0 ? `${Math.round((value / max) * 100)}%` : "0%";

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6 flex-wrap gap-2">
          <h1 className="text-2xl font-bold">Weekly Review</h1>
          <div className="flex gap-2">
            <button
              onClick={generateWeekly}
              disabled={loadingAi}
              className="px-4 py-2 rounded-lg text-sm font-medium"
              style={{ background: "#7c3aed", color: "white" }}
            >
              {loadingAi ? "生成中..." : "AI 週次レビュー"}
            </button>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
              style={{ background: "var(--color-accent)", color: "white" }}
            >
              {generating ? "Generating..." : "対話統計を更新"}
            </button>
          </div>
        </div>

        {weekly && (
          <div
            className="rounded-2xl p-6 mb-6"
            style={{
              background: "linear-gradient(135deg, rgba(124, 58, 237, 0.12) 0%, rgba(244, 114, 182, 0.06) 100%)",
              border: "1px solid rgba(124, 58, 237, 0.25)",
            }}
          >
            <div className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "#a78bfa" }}>
              今週の所見 ({weekly.engine_used})
            </div>
            <div className="text-[14px] whitespace-pre-wrap leading-[1.85]">{weekly.review}</div>
            <div className="mt-4 flex gap-4 text-xs flex-wrap" style={{ color: "var(--color-text-muted)" }}>
              <span>完了 {weekly.completion_count}</span>
              <span>決定 {weekly.decision_count}</span>
              <span>失敗 {weekly.failure_count}</span>
              <span>集中 {Math.floor(weekly.focus_minutes_total / 60)}h {weekly.focus_minutes_total % 60}m</span>
            </div>
            {Object.keys(weekly.focus_by_category).length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {Object.entries(weekly.focus_by_category)
                  .sort((a, b) => b[1] - a[1])
                  .map(([k, v]) => (
                    <span
                      key={k}
                      className="text-[11px] px-2 py-0.5 rounded-full"
                      style={{ background: "rgba(255,255,255,0.06)", color: "var(--color-text-muted)" }}
                    >
                      {k}: {v}分
                    </span>
                  ))}
              </div>
            )}
          </div>
        )}

        {/* 結果を記録すべき決定 — 「で、効いたのか?」を閉じて判断力に変える */}
        {pending.length > 0 && (
          <div
            className="rounded-2xl p-6 mb-6"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
          >
            <div className="flex items-center gap-2 mb-1">
              <span>🧭</span>
              <h3 className="font-semibold">結果を記録すべき決定</h3>
              <span
                className="text-[11px] px-2 py-0.5 rounded-full"
                style={{ background: "rgba(245,158,11,0.14)", color: "#f59e0b" }}
              >
                {pending.length}
              </span>
            </div>
            <p className="text-sm mb-4" style={{ color: "var(--color-text-muted)" }}>
              2週間以上前に決めたのに、効いたかを記録していないものです。一言残すと決定が判断力になります。
            </p>
            <div className="space-y-4">
              {pending.map((d) => (
                <div
                  key={d.id}
                  className="rounded-xl p-4"
                  style={{ background: "var(--color-background)", border: "1px solid var(--color-border)" }}
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <h4 className="font-medium text-[15px] leading-snug">{d.title}</h4>
                    <span className="text-[11px] shrink-0" style={{ color: "var(--color-text-muted)" }}>
                      {d.timestamp?.slice(0, 10)}
                    </span>
                  </div>
                  {d.chosen && (
                    <p className="text-xs mb-2" style={{ color: "var(--color-text-muted)" }}>
                      結論: {d.chosen}
                    </p>
                  )}
                  <textarea
                    value={draft[d.id] || ""}
                    onChange={(e) => setDraft((x) => ({ ...x, [d.id]: e.target.value }))}
                    placeholder="で、効いた? 何が起きた? (一言で可)"
                    rows={2}
                    className="w-full rounded-lg px-3 py-2 text-sm resize-none"
                    style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                  />
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={() => recordOutcome(d.id, "closed")}
                      disabled={!!saving || !(draft[d.id] || "").trim()}
                      className="rounded-full px-4 py-1.5 text-sm font-medium disabled:opacity-40"
                      style={{ background: "var(--color-accent)", color: "#fff" }}
                    >
                      {saving === d.id ? "記録中..." : "✓ 記録して閉じる"}
                    </button>
                    <button
                      onClick={() => recordOutcome(d.id, "revisit")}
                      disabled={!!saving || !(draft[d.id] || "").trim()}
                      className="rounded-full px-4 py-1.5 text-sm disabled:opacity-40"
                      style={{ border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}
                    >
                      もう一度考える
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Overview */}
            <div className="p-5 rounded-xl" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
              <h3 className="font-semibold mb-3">Overview (Last {stats.period_days} days)</h3>
              <p className="text-3xl font-bold" style={{ color: "var(--color-accent)" }}>
                {stats.total_interactions}
              </p>
              <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>Total Interactions</p>
              <p className="mt-2 text-sm">
                Counterpoint Rate: <strong>{stats.counterpoint_rate_pct}%</strong>
              </p>
            </div>

            {/* Domain Distribution */}
            <div className="p-5 rounded-xl" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
              <h3 className="font-semibold mb-3">Domains</h3>
              <div className="space-y-2">
                {Object.entries(stats.domain_distribution).map(([d, count]) => (
                  <div key={d} className="flex items-center gap-2">
                    <span className="text-sm w-20" style={{ color: "var(--color-text-muted)" }}>{d}</span>
                    <div className="flex-1 h-4 rounded-full overflow-hidden" style={{ background: "var(--color-background)" }}>
                      <div
                        className="h-full rounded-full"
                        style={{ width: barWidth(count, stats.total_interactions), background: "var(--color-accent)" }}
                      />
                    </div>
                    <span className="text-sm w-6 text-right">{count}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Level Distribution */}
            <div className="p-5 rounded-xl" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
              <h3 className="font-semibold mb-3">Intervention Levels</h3>
              <div className="space-y-2">
                {Object.entries(stats.level_distribution).map(([l, count]) => (
                  <div key={l} className="flex items-center gap-2">
                    <span className="text-sm w-8 font-mono">{l}</span>
                    <div className="flex-1 h-4 rounded-full overflow-hidden" style={{ background: "var(--color-background)" }}>
                      <div
                        className="h-full rounded-full"
                        style={{ width: barWidth(count, stats.total_interactions), background: "var(--color-accent)" }}
                      />
                    </div>
                    <span className="text-sm w-6 text-right">{count}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Biases */}
            <div className="p-5 rounded-xl" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
              <h3 className="font-semibold mb-3">Detected Biases</h3>
              {Object.keys(stats.bias_frequency).length > 0 ? (
                <div className="space-y-2">
                  {Object.entries(stats.bias_frequency).map(([b, count]) => (
                    <div key={b} className="flex items-center justify-between">
                      <span className="text-sm">{b}</span>
                      <span className="text-sm px-2 py-0.5 rounded-full" style={{ background: "#7c3aed20", color: "#a78bfa" }}>
                        {count}x
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>No biases detected</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
