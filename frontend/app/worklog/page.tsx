"use client";

import { useEffect, useState, useCallback } from "react";

type WorkItem = {
  id: string;
  title: string;
  project: string;
  category: string;
  date: string;
  minutes: number;
  engine: string;
  outcome: string;
  tags: string[];
  source?: string;
  created_at: string;
  updated_at: string;
};

type Stats = {
  days: number;
  total_entries: number;
  total_minutes: number;
  by_project: Record<string, { count: number; minutes: number }>;
  by_category: Record<string, { count: number; minutes: number }>;
  by_engine: Record<string, number>;
  engine_by_category: Record<string, Record<string, number>>;
};

const ENGINE_OPTIONS = [
  "claude-code",
  "claude",
  "gpt",
  "gemini",
  "grok",
  "perplexity",
  "venice",
  "fugu",
  "fugu-ultra",
  "canva",
  "notebooklm",
  "codex",
  "none",
  "other",
];

function today(): string {
  const d = new Date();
  const z = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}

function fmtMinutes(m: number): string {
  if (!m) return "";
  if (m < 60) return `${m}分`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r ? `${h}時間${r}分` : `${h}時間`;
}

export default function WorkLogPage() {
  const [items, setItems] = useState<WorkItem[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [facets, setFacets] = useState<{ projects: string[]; categories: string[] }>({
    projects: [],
    categories: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // filters
  const [fProject, setFProject] = useState("");
  const [fCategory, setFCategory] = useState("");
  const [fEngine, setFEngine] = useState("");
  const [q, setQ] = useState("");

  // new entry form
  const [title, setTitle] = useState("");
  const [project, setProject] = useState("");
  const [category, setCategory] = useState("");
  const [date, setDate] = useState(today());
  const [minutes, setMinutes] = useState("");
  const [engine, setEngine] = useState("");
  const [outcome, setOutcome] = useState("");

  // AI engine suggestion (work_log の実績ベース)
  const [suggesting, setSuggesting] = useState(false);
  const [suggestion, setSuggestion] = useState<{
    engine: string;
    reason: string;
    history_used: boolean;
    close_call: boolean;
    history_thin: boolean;
  } | null>(null);

  // 入力モード: quick=ざっくり1枚 / detail=構造化フォーム
  const [mode, setMode] = useState<"quick" | "detail">("quick");
  const [quickText, setQuickText] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (fProject) params.set("project", fProject);
    if (fCategory) params.set("category", fCategory);
    if (fEngine) params.set("engine", fEngine);
    if (q) params.set("q", q);
    fetch(`/api/work-log?${params.toString()}`)
      .then((r) => r.json())
      .then((d) => setItems(d.items ?? []))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [fProject, fCategory, fEngine, q]);

  const loadMeta = useCallback(() => {
    fetch("/api/work-log/facets")
      .then((r) => r.json())
      .then((d) => setFacets({ projects: d.projects ?? [], categories: d.categories ?? [] }))
      .catch(() => {});
    fetch("/api/work-log/stats?days=90")
      .then((r) => r.json())
      .then((d) => setStats(d))
      .catch(() => {});
  }, []);

  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    loadMeta();
  }, [loadMeta]);

  const handleAdd = async () => {
    if (!title.trim()) return;
    try {
      await fetch("/api/work-log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          project,
          category,
          date,
          minutes: minutes ? parseInt(minutes, 10) : 0,
          engine,
          outcome,
        }),
      });
      setTitle("");
      setOutcome("");
      setMinutes("");
      load();
      loadMeta();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleQuickAdd = async () => {
    const text = quickText.trim();
    if (!text) return;
    const lines = text.split("\n");
    const firstLine = lines[0].slice(0, 120);
    const rest = lines.slice(1).join("\n").trim();
    try {
      await fetch("/api/work-log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: firstLine, outcome: rest, date }),
      });
      setQuickText("");
      load();
      loadMeta();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleSuggest = async () => {
    if (!title.trim()) return;
    setSuggesting(true);
    setSuggestion(null);
    try {
      const r = await fetch("/api/dispatch/suggest-engine", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: title, category: category || null }),
      });
      const d = await r.json();
      if (d.ok) {
        setSuggestion({
          engine: d.engine,
          reason: d.reason,
          history_used: d.history_used,
          close_call: d.close_call,
          history_thin: d.history_thin,
        });
        if (ENGINE_OPTIONS.includes(d.engine)) setEngine(d.engine);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSuggesting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("この実績を削除しますか？")) return;
    try {
      await fetch(`/api/work-log/${id}`, { method: "DELETE" });
      load();
      loadMeta();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const inputStyle = {
    background: "var(--color-background)",
    border: "1px solid var(--color-border)",
    color: "var(--color-text)",
  };

  const topEngines = stats
    ? Object.entries(stats.by_engine).sort((a, b) => b[1] - a[1])
    : [];

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Hero */}
      <div
        className="px-8 pt-10 pb-6"
        style={{
          background:
            "radial-gradient(ellipse at top right, rgba(34, 197, 94, 0.10), transparent 50%)",
        }}
      >
        <div className="max-w-5xl mx-auto">
          <h1
            className="text-4xl font-bold tracking-tight"
            style={{
              background: "linear-gradient(90deg, #fafafa 0%, #a1a1aa 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            実績ログ
          </h1>
          <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>
            やり遂げた作業を時系列に積む台帳。メモとは別。使った AI も記録して、後で「この作業はこれが向いている」の判断材料にする
          </p>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-5xl mx-auto space-y-6">
          {/* Stats */}
          {stats && stats.total_entries > 0 && (
            <div
              className="rounded-2xl p-4 grid grid-cols-2 md:grid-cols-4 gap-4"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            >
              <div>
                <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  直近{stats.days}日の件数
                </div>
                <div className="text-2xl font-bold">{stats.total_entries}</div>
              </div>
              <div>
                <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  記録した時間
                </div>
                <div className="text-2xl font-bold">{fmtMinutes(stats.total_minutes) || "—"}</div>
              </div>
              <div className="col-span-2">
                <div className="text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>
                  使った AI (件数)
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {topEngines.length === 0 && <span className="text-sm">—</span>}
                  {topEngines.map(([eng, n]) => (
                    <span
                      key={eng}
                      className="px-2 py-0.5 rounded-full text-[11px]"
                      style={{
                        background: "rgba(34, 197, 94, 0.12)",
                        border: "1px solid rgba(34, 197, 94, 0.4)",
                      }}
                    >
                      {eng} · {n}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Add form */}
          <div
            className="rounded-2xl p-4 space-y-3"
            style={{
              background: "rgba(34, 197, 94, 0.06)",
              border: "1px solid rgba(34, 197, 94, 0.35)",
            }}
          >
            {/* モード切替 */}
            <div className="flex gap-1 text-xs">
              <button
                onClick={() => setMode("quick")}
                className="px-3 py-1 rounded-full transition-all"
                style={{
                  background: mode === "quick" ? "var(--color-text)" : "transparent",
                  color: mode === "quick" ? "var(--color-background)" : "var(--color-text-muted)",
                  border: "1px solid var(--color-border)",
                }}
              >
                ✏️ ざっくり
              </button>
              <button
                onClick={() => setMode("detail")}
                className="px-3 py-1 rounded-full transition-all"
                style={{
                  background: mode === "detail" ? "var(--color-text)" : "transparent",
                  color: mode === "detail" ? "var(--color-background)" : "var(--color-text-muted)",
                  border: "1px solid var(--color-border)",
                }}
              >
                📋 詳しく
              </button>
            </div>

            {mode === "quick" && (
              <div className="space-y-2">
                <textarea
                  value={quickText}
                  onChange={(e) => setQuickText(e.target.value)}
                  placeholder="今日やったこと、ざっくり書く。改行OK。1行目が見出しになります（プロジェクトや使った AI は後から「詳しく」で足してもOK）"
                  rows={4}
                  className="w-full px-3 py-2 rounded-lg text-sm resize-none"
                  style={inputStyle}
                />
                <div className="flex items-center justify-between">
                  <input
                    type="date"
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                    className="px-3 py-1.5 rounded-lg text-sm"
                    style={inputStyle}
                  />
                  <button
                    onClick={handleQuickAdd}
                    disabled={!quickText.trim()}
                    className="px-5 py-1.5 rounded-full text-sm font-medium disabled:opacity-50 transition-all hover:scale-[1.02]"
                    style={{ background: "var(--color-text)", color: "var(--color-background)" }}
                  >
                    さっと記録
                  </button>
                </div>
              </div>
            )}

            {mode === "detail" && (
            <>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="やったこと (例: EGAKU の Supabase RLS 4テーブル修正)"
              className="w-full px-3 py-2 rounded-lg text-sm"
              style={inputStyle}
            />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <input
                value={project}
                onChange={(e) => setProject(e.target.value)}
                placeholder="プロジェクト"
                list="wl-projects"
                className="px-3 py-2 rounded-lg text-sm"
                style={inputStyle}
              />
              <input
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="カテゴリ"
                list="wl-categories"
                className="px-3 py-2 rounded-lg text-sm"
                style={inputStyle}
              />
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="px-3 py-2 rounded-lg text-sm"
                style={inputStyle}
              />
              <input
                value={minutes}
                onChange={(e) => setMinutes(e.target.value.replace(/[^0-9]/g, ""))}
                placeholder="分 (任意)"
                inputMode="numeric"
                className="px-3 py-2 rounded-lg text-sm"
                style={inputStyle}
              />
            </div>
            <datalist id="wl-projects">
              {facets.projects.map((p) => (
                <option key={p} value={p} />
              ))}
            </datalist>
            <datalist id="wl-categories">
              {facets.categories.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                使った AI:
              </label>
              <select
                value={engine}
                onChange={(e) => setEngine(e.target.value)}
                className="px-3 py-2 rounded-lg text-sm"
                style={inputStyle}
              >
                <option value="">(未選択)</option>
                {ENGINE_OPTIONS.map((eng) => (
                  <option key={eng} value={eng}>
                    {eng}
                  </option>
                ))}
              </select>
              <button
                onClick={handleSuggest}
                disabled={!title.trim() || suggesting}
                className="px-3 py-2 rounded-lg text-sm disabled:opacity-40 transition-all"
                style={{ background: "rgba(34,197,94,0.15)", border: "1px solid rgba(34,197,94,0.4)" }}
                title="やったこと(と任意でカテゴリ)から、過去の実績を根拠に最適な AI を提案"
              >
                {suggesting ? "..." : "🤖 AI提案"}
              </button>
            </div>
            {suggestion && (
              <div className="text-xs px-3 py-2 rounded-lg" style={{ background: "var(--color-background)", border: "1px solid var(--color-border)" }}>
                <span style={{ color: "#86efac" }}>おすすめ: {suggestion.engine}</span>
                {suggestion.reason && <span style={{ color: "var(--color-text-muted)" }}> — {suggestion.reason}</span>}
                {suggestion.history_thin && (
                  <span style={{ color: "var(--color-text-muted)" }}> ⚠実績が薄いので一般論ベース</span>
                )}
                {suggestion.close_call && (
                  <span style={{ color: "var(--color-text-muted)" }}> (僅差)</span>
                )}
              </div>
            )}
            <textarea
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
              placeholder="成果・メモ (任意)"
              rows={2}
              className="w-full px-3 py-2 rounded-lg text-sm resize-none"
              style={inputStyle}
            />
            <div className="flex justify-end">
              <button
                onClick={handleAdd}
                disabled={!title.trim()}
                className="px-5 py-1.5 rounded-full text-sm font-medium disabled:opacity-50 transition-all hover:scale-[1.02]"
                style={{ background: "var(--color-text)", color: "var(--color-background)" }}
              >
                台帳に記録
              </button>
            </div>
            </>
            )}
          </div>

          {/* Filters */}
          <div className="flex flex-wrap gap-2 items-center">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="検索..."
              className="px-3 py-1.5 rounded-lg text-sm flex-1 min-w-[160px]"
              style={inputStyle}
            />
            <select
              value={fProject}
              onChange={(e) => setFProject(e.target.value)}
              className="px-3 py-1.5 rounded-lg text-sm"
              style={inputStyle}
            >
              <option value="">全プロジェクト</option>
              {facets.projects.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <select
              value={fCategory}
              onChange={(e) => setFCategory(e.target.value)}
              className="px-3 py-1.5 rounded-lg text-sm"
              style={inputStyle}
            >
              <option value="">全カテゴリ</option>
              {facets.categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <select
              value={fEngine}
              onChange={(e) => setFEngine(e.target.value)}
              className="px-3 py-1.5 rounded-lg text-sm"
              style={inputStyle}
            >
              <option value="">全 AI</option>
              {ENGINE_OPTIONS.map((eng) => (
                <option key={eng} value={eng}>
                  {eng}
                </option>
              ))}
            </select>
          </div>

          {error && (
            <div
              className="rounded-2xl p-3 text-sm"
              style={{
                background: "rgba(239, 68, 68, 0.08)",
                border: "1px solid var(--color-red)",
                color: "var(--color-red)",
              }}
            >
              {error}
            </div>
          )}

          {/* List */}
          {loading ? (
            <div className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              読み込み中...
            </div>
          ) : items.length === 0 ? (
            <div
              className="rounded-2xl p-10 text-center"
              style={{ background: "var(--color-surface)", border: "1px dashed var(--color-border-light)" }}
            >
              <p className="text-3xl mb-2">📒</p>
              <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                まだ実績の記録はありません
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {items.map((w) => (
                <div
                  key={w.id}
                  className="rounded-xl p-4 transition-all hover:translate-y-[-1px]"
                  style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <p className="text-sm font-medium" style={{ color: "var(--color-text)" }}>
                        {w.title}
                      </p>
                      {w.outcome && (
                        <p
                          className="text-xs mt-1 whitespace-pre-wrap"
                          style={{ color: "var(--color-text-muted)" }}
                        >
                          {w.outcome}
                        </p>
                      )}
                      <div className="flex flex-wrap gap-1.5 mt-2 text-[11px]">
                        <span style={{ color: "var(--color-text-muted)" }}>{w.date}</span>
                        {w.project && (
                          <span
                            className="px-1.5 rounded"
                            style={{ background: "rgba(59,130,246,0.15)", color: "#93c5fd" }}
                          >
                            {w.project}
                          </span>
                        )}
                        {w.category && (
                          <span
                            className="px-1.5 rounded"
                            style={{ background: "rgba(168,85,247,0.15)", color: "#d8b4fe" }}
                          >
                            {w.category}
                          </span>
                        )}
                        {w.engine && (
                          <span
                            className="px-1.5 rounded"
                            style={{ background: "rgba(34,197,94,0.15)", color: "#86efac" }}
                          >
                            {w.engine}
                          </span>
                        )}
                        {w.minutes > 0 && (
                          <span style={{ color: "var(--color-text-muted)" }}>{fmtMinutes(w.minutes)}</span>
                        )}
                        {w.source === "completion" && (
                          <span style={{ color: "var(--color-text-muted)" }} title="完了ログから昇格">
                            ✓昇格
                          </span>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => handleDelete(w.id)}
                      className="px-1.5 py-0.5 rounded hover:bg-black/10 text-xs"
                      style={{ color: "var(--color-text-muted)" }}
                      title="削除"
                    >
                      ✕
                    </button>
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
