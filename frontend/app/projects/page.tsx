"use client";

import { useEffect, useState } from "react";

type Project = {
  id: string;
  name: string;
  category: string;
  status: string;
  priority: number;
  github_url?: string;
  live_url?: string;
  local_path?: string;
  memory_ref?: string;
  one_liner?: string;
  next_action?: string;
  last_touched?: string;
  notes?: string;
  last_commit_sha?: string;
  last_commit_message?: string;
  last_commit_date?: string;
  uncommitted_changes?: number;
  sync_at?: string;
  sync_source?: string;
};

type Candidate = {
  id: string;
  source: string;
  name: string;
  local_path?: string;
  github_url?: string;
  last_commit_date?: string;
  last_commit_message?: string;
  last_email_subject?: string;
  last_email_from?: string;
  last_email_date?: string;
  stack_hint?: string;
  discovered_at?: string;
};

type ListResp = {
  updated_at: string | null;
  projects: Project[];
  by_status: Record<string, Project[]>;
  by_category: Record<string, Project[]>;
  count: number;
};

const CAT_META: Record<string, { emoji: string; label: string; color: string }> = {
  saas: { emoji: "💎", label: "SaaS", color: "#10b981" },
  research: { emoji: "🎓", label: "研究", color: "#f59e0b" },
  platform: { emoji: "🧰", label: "プラットフォーム", color: "#3b82f6" },
  infra: { emoji: "🛠", label: "Infra", color: "#a855f7" },
  creative: { emoji: "🎨", label: "クリエイティブ", color: "#ec4899" },
};

const STATUS_META: Record<string, { emoji: string; label: string }> = {
  active: { emoji: "🟢", label: "アクティブ" },
  maintenance: { emoji: "🔧", label: "メンテ" },
  paused: { emoji: "⏸", label: "一時停止" },
  archived: { emoji: "📦", label: "アーカイブ" },
  planning: { emoji: "📝", label: "計画中" },
};

const STATUS_ORDER = ["active", "maintenance", "paused", "planning", "archived"];

function daysSince(dateStr?: string): number | null {
  if (!dateStr) return null;
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return null;
  return Math.floor((Date.now() - d.getTime()) / (1000 * 60 * 60 * 24));
}

function emptyProject(): Project {
  return {
    id: "",
    name: "",
    category: "saas",
    status: "active",
    priority: 3,
    github_url: "",
    live_url: "",
    local_path: "",
    memory_ref: "",
    one_liner: "",
    next_action: "",
    last_touched: "",
    notes: "",
  };
}

export default function ProjectsPage() {
  const [data, setData] = useState<ListResp | null>(null);
  const [editing, setEditing] = useState<Project | null>(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRecommend, setShowRecommend] = useState(false);
  const [mood, setMood] = useState("");
  const [hours, setHours] = useState(2);
  const [context, setContext] = useState("");
  const [engine, setEngine] = useState("claude");
  const [recLoading, setRecLoading] = useState(false);
  const [recommendation, setRecommendation] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [showCandidates, setShowCandidates] = useState(true);
  const [candLoading, setCandLoading] = useState(false);
  const [adviseFor, setAdviseFor] = useState<Project | null>(null);
  const [adviseFocus, setAdviseFocus] = useState("");
  const [adviseLoading, setAdviseLoading] = useState(false);
  const [adviseText, setAdviseText] = useState<string | null>(null);
  const [adviseMeta, setAdviseMeta] = useState<{ docs_count: number; commits_used: number } | null>(null);

  const load = () => {
    fetch("/api/projects")
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError((e as Error).message));
  };

  const loadCandidates = () => {
    fetch("/api/projects/candidates")
      .then((r) => r.json())
      .then((j) => setCandidates(j.candidates || []))
      .catch(() => {});
  };

  useEffect(() => {
    load();
    loadCandidates();
  }, []);

  const approveCandidate = async (cand: Candidate) => {
    const res = await fetch(`/api/projects/candidates/${encodeURIComponent(cand.id)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category: "saas", status: "active", priority: 3 }),
    });
    if (res.ok) {
      loadCandidates();
      load();
    } else {
      alert(`承認失敗: ${await res.text()}`);
    }
  };

  const rejectCandidate = async (cand: Candidate) => {
    if (!confirm(`「${cand.name}」を却下しますか? (二度と提案されません)`)) return;
    await fetch(`/api/projects/candidates/${encodeURIComponent(cand.id)}/reject`, { method: "POST" });
    loadCandidates();
  };

  const requestAdvice = async (project: Project, focus: string) => {
    setAdviseLoading(true);
    setAdviseText(null);
    setAdviseMeta(null);
    try {
      const res = await fetch(`/api/projects/${encodeURIComponent(project.id)}/advise`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ focus, engine: "claude" }),
      });
      const j = await res.json();
      if (!res.ok) throw new Error(j.detail || res.statusText);
      setAdviseText(j.advice);
      setAdviseMeta({ docs_count: j.docs_count, commits_used: j.commits_used });
    } catch (e) {
      setAdviseText(`エラー: ${(e as Error).message}`);
    } finally {
      setAdviseLoading(false);
    }
  };

  const scanGmail = async () => {
    setCandLoading(true);
    try {
      const res = await fetch("/api/projects/discover/gmail?days=30&slot=1", { method: "POST" });
      const j = await res.json();
      if (res.ok) {
        alert(`Gmail から ${j.added} 件の新候補 (合計 ${j.total_candidates} / scan: ${j.scanned_emails} 通)`);
        loadCandidates();
      } else {
        alert(`失敗: ${JSON.stringify(j)}`);
      }
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setCandLoading(false);
    }
  };

  const save = async (p: Project) => {
    setError(null);
    try {
      const isNew = adding;
      const method = isNew ? "POST" : "PATCH";
      const url = isNew ? "/api/projects" : `/api/projects/${encodeURIComponent(p.id)}`;
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(p),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(`${res.status} ${t}`);
      }
      setEditing(null);
      setAdding(false);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const remove = async (id: string) => {
    if (!confirm(`「${id}」を削除しますか?`)) return;
    await fetch(`/api/projects/${encodeURIComponent(id)}`, { method: "DELETE" });
    load();
  };

  const touch = async (id: string) => {
    await fetch(`/api/projects/touched/${encodeURIComponent(id)}`, { method: "POST" });
    load();
  };

  const seed = async () => {
    if (!confirm("プロジェクト初期 seed を merge 投入しますか? (既存 id は保持)")) return;
    const res = await fetch("/api/projects/seed", { method: "POST" });
    const j = await res.json();
    alert(`追加: ${j.added} 件 / 合計: ${j.total}`);
    load();
  };

  const recommend = async () => {
    setRecLoading(true);
    setRecommendation(null);
    try {
      const res = await fetch("/api/projects/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mood, available_hours: hours, context, engine }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const j = await res.json();
      setRecommendation(j.recommendation);
    } catch (e) {
      setRecommendation(`エラー: ${(e as Error).message}`);
    } finally {
      setRecLoading(false);
    }
  };

  const allProjects = data?.projects || [];
  const filtered =
    statusFilter === "all"
      ? allProjects
      : allProjects.filter((p) => p.status === statusFilter);

  // ソート: priority 降順 → last_touched 古い順 (未記録は最後)
  const sorted = [...filtered].sort((a, b) => {
    if (b.priority !== a.priority) return b.priority - a.priority;
    const da = daysSince(a.last_touched) ?? -1;
    const db = daysSince(b.last_touched) ?? -1;
    if (da === -1 && db === -1) return 0;
    if (da === -1) return 1;
    if (db === -1) return -1;
    return db - da;
  });

  return (
    <div className="flex-1 overflow-y-auto">
      <div
        className="px-8 pt-12 pb-8"
        style={{ background: "radial-gradient(ellipse at top, rgba(168, 85, 247, 0.10), transparent 60%)" }}
      >
        <div className="max-w-6xl mx-auto">
          <p
            className="text-xs uppercase tracking-widest mb-2"
            style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}
          >
            Projects · Alfred
          </p>
          <h1 className="text-4xl font-bold tracking-tight">並行プロジェクト全把握</h1>
          <p className="text-sm mt-3" style={{ color: "var(--color-text-muted)" }}>
            {data?.count ?? 0} プロジェクト ·{" "}
            {data?.updated_at && `更新 ${new Date(data.updated_at).toLocaleDateString("ja-JP")}`}
          </p>
          <div className="flex flex-wrap gap-2 mt-5">
            <button
              onClick={() => setShowRecommend(!showRecommend)}
              className="px-4 py-2 rounded-lg text-sm font-medium"
              style={{ background: "var(--color-accent)", color: "white" }}
            >
              🎯 今日どれに触る?
            </button>
            <button
              onClick={() => {
                setEditing(emptyProject());
                setAdding(true);
              }}
              className="px-4 py-2 rounded-lg text-sm"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            >
              + 新規プロジェクト
            </button>
            <button
              onClick={seed}
              className="px-4 py-2 rounded-lg text-sm"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            >
              🌱 初期 seed
            </button>
            <button
              onClick={scanGmail}
              disabled={candLoading}
              className="px-4 py-2 rounded-lg text-sm disabled:opacity-50"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
              title="Gmail 直近30日から GitHub / Vercel / Railway 通知を scan して候補化"
            >
              📧 Gmail から発見
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-8 pb-20">
        {error && (
          <div
            className="p-3 rounded-lg mb-4 text-sm"
            style={{ background: "rgba(239, 68, 68, 0.1)", color: "#ef4444" }}
          >
            {error}
          </div>
        )}

        {showRecommend && (
          <div
            className="rounded-2xl p-5 mb-6"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
          >
            <h2 className="font-bold mb-3">🎯 今日触るプロジェクト推奨</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
              <input
                value={mood}
                onChange={(e) => setMood(e.target.value)}
                placeholder="気分 (例: 疲れてる / 集中できる)"
                className="px-3 py-2 rounded-lg text-sm"
                style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
              />
              <input
                type="number"
                step="0.5"
                value={hours}
                onChange={(e) => setHours(Number(e.target.value))}
                placeholder="使える時間 (h)"
                className="px-3 py-2 rounded-lg text-sm"
                style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
              />
              <select
                value={engine}
                onChange={(e) => setEngine(e.target.value)}
                className="px-3 py-2 rounded-lg text-sm"
                style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
              >
                <option value="claude">Claude</option>
                <option value="gpt">GPT</option>
                <option value="gemini">Gemini</option>
                <option value="grok">Grok</option>
              </select>
            </div>
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="追加コンテキスト (例: 午後2時間だけ、家族の予定で夜は無理)"
              rows={2}
              className="w-full px-3 py-2 rounded-lg text-sm mb-3"
              style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
            />
            <button
              onClick={recommend}
              disabled={recLoading}
              className="px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
              style={{ background: "var(--color-accent)", color: "white" }}
            >
              {recLoading ? "AI 考え中..." : "推奨を取得"}
            </button>
            {recommendation && (
              <div
                className="mt-4 p-4 rounded-lg text-sm whitespace-pre-wrap"
                style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
              >
                {recommendation}
              </div>
            )}
          </div>
        )}

        {/* 候補 (discovery) */}
        {candidates.length > 0 && (
          <div
            className="rounded-2xl p-5 mb-6"
            style={{ background: "var(--color-surface)", border: "1px solid rgba(168, 85, 247, 0.3)" }}
          >
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-bold flex items-center gap-2">
                📥 新しい候補 ({candidates.length})
                <span className="text-xs font-normal" style={{ color: "var(--color-text-muted)" }}>
                  — 承認するとプロジェクトに追加、却下で二度と提案されません
                </span>
              </h2>
              <button
                onClick={() => setShowCandidates(!showCandidates)}
                className="text-xs px-2 py-1 rounded"
                style={{ background: "var(--color-bg)" }}
              >
                {showCandidates ? "閉じる" : "開く"}
              </button>
            </div>
            {showCandidates && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {candidates.map((c) => (
                  <div
                    key={c.id}
                    className="p-3 rounded-lg"
                    style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] px-1.5 py-0.5 rounded font-mono" style={{ background: "var(--color-surface)", color: "var(--color-text-muted)" }}>
                        {c.source}
                      </span>
                      <span className="font-medium text-sm truncate">{c.name}</span>
                    </div>
                    {c.local_path && (
                      <div className="text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>
                        📁 {c.local_path}
                      </div>
                    )}
                    {c.github_url && (
                      <div className="text-xs mb-1 truncate" style={{ color: "var(--color-text-muted)" }}>
                        🔗 <a href={c.github_url} target="_blank" rel="noopener" className="hover:underline">{c.github_url}</a>
                      </div>
                    )}
                    {c.last_commit_message && (
                      <div className="text-xs mb-1 truncate" style={{ color: "var(--color-text-muted)" }}>
                        💬 {c.last_commit_message}
                      </div>
                    )}
                    {c.last_email_subject && (
                      <div className="text-xs mb-1 truncate" style={{ color: "var(--color-text-muted)" }}>
                        ✉ {c.last_email_subject}
                      </div>
                    )}
                    {c.stack_hint && c.stack_hint !== "unknown" && (
                      <div className="text-xs mb-2" style={{ color: "var(--color-text-muted)" }}>
                        🧱 {c.stack_hint}
                      </div>
                    )}
                    <div className="flex gap-2 mt-2">
                      <button
                        onClick={() => approveCandidate(c)}
                        className="text-xs px-3 py-1 rounded font-medium"
                        style={{ background: "var(--color-accent)", color: "white" }}
                      >
                        ✓ 承認 → プロジェクト追加
                      </button>
                      <button
                        onClick={() => rejectCandidate(c)}
                        className="text-xs px-3 py-1 rounded"
                        style={{ background: "var(--color-surface)", color: "#ef4444" }}
                      >
                        却下
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ステータスフィルタ */}
        <div className="flex flex-wrap gap-2 mb-5">
          <button
            onClick={() => setStatusFilter("all")}
            className="px-3 py-1.5 rounded-lg text-xs"
            style={{
              background: statusFilter === "all" ? "var(--color-accent)" : "var(--color-surface)",
              color: statusFilter === "all" ? "white" : "var(--color-text)",
              border: "1px solid var(--color-border)",
            }}
          >
            全て ({allProjects.length})
          </button>
          {STATUS_ORDER.map((s) => {
            const cnt = (data?.by_status?.[s] || []).length;
            if (cnt === 0) return null;
            const meta = STATUS_META[s];
            return (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className="px-3 py-1.5 rounded-lg text-xs"
                style={{
                  background: statusFilter === s ? "var(--color-accent)" : "var(--color-surface)",
                  color: statusFilter === s ? "white" : "var(--color-text)",
                  border: "1px solid var(--color-border)",
                }}
              >
                {meta.emoji} {meta.label} ({cnt})
              </button>
            );
          })}
        </div>

        {/* プロジェクトカード */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {sorted.map((p) => {
            const cat = CAT_META[p.category] || CAT_META.saas;
            const status = STATUS_META[p.status] || STATUS_META.active;
            const days = daysSince(p.last_touched);
            const cold = days !== null && days > 30;
            return (
              <div
                key={p.id}
                className="rounded-2xl p-5"
                style={{
                  background: "var(--color-surface)",
                  border: `1px solid ${cold ? "rgba(239, 68, 68, 0.4)" : "var(--color-border)"}`,
                }}
              >
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="text-lg">{cat.emoji}</span>
                      <h3 className="font-bold truncate">{p.name}</h3>
                      <span
                        className="text-[10px] px-1.5 py-0.5 rounded"
                        style={{ background: cat.color + "22", color: cat.color }}
                      >
                        {cat.label}
                      </span>
                      <span className="text-xs" title={status.label}>
                        {status.emoji}
                      </span>
                      <span
                        className="text-[10px] px-1.5 py-0.5 rounded"
                        style={{ background: "var(--color-bg)", color: "var(--color-text-muted)" }}
                      >
                        P{p.priority}
                      </span>
                    </div>
                    {p.one_liner && (
                      <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                        {p.one_liner}
                      </p>
                    )}
                  </div>
                </div>

                {p.next_action && (
                  <div
                    className="text-xs p-2 rounded-lg mb-2"
                    style={{ background: "var(--color-bg)" }}
                  >
                    <span style={{ color: "var(--color-text-muted)" }}>次: </span>
                    {p.next_action}
                  </div>
                )}

                {p.last_commit_message && (
                  <div
                    className="text-xs p-2 rounded-lg mb-2 flex items-start gap-2"
                    style={{ background: "var(--color-bg)" }}
                  >
                    <span style={{ color: "var(--color-text-muted)" }}>💬</span>
                    <div className="flex-1 min-w-0">
                      <div className="truncate">{p.last_commit_message}</div>
                      <div className="text-[10px] mt-0.5 flex items-center gap-2" style={{ color: "var(--color-text-muted)" }}>
                        {p.last_commit_sha && <span className="font-mono">{p.last_commit_sha.slice(0, 7)}</span>}
                        {p.last_commit_date && <span>{p.last_commit_date.slice(0, 10)}</span>}
                        {(p.uncommitted_changes ?? 0) > 0 && (
                          <span style={{ color: "#f59e0b" }}>● 未コミット {p.uncommitted_changes}</span>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                <div className="flex items-center gap-3 text-xs mb-3" style={{ color: "var(--color-text-muted)" }}>
                  {p.last_touched ? (
                    <span style={{ color: cold ? "#ef4444" : undefined }}>
                      🕒 {p.last_touched} ({days}日前{cold && " 冷え"})
                    </span>
                  ) : (
                    <span>🕒 未記録</span>
                  )}
                </div>

                <div className="flex flex-wrap gap-2 text-xs">
                  {p.github_url && (
                    <a
                      href={p.github_url}
                      target="_blank"
                      rel="noopener"
                      className="px-2 py-1 rounded hover:underline"
                      style={{ background: "var(--color-bg)" }}
                    >
                      GitHub ↗
                    </a>
                  )}
                  {p.live_url && (
                    <a
                      href={p.live_url}
                      target="_blank"
                      rel="noopener"
                      className="px-2 py-1 rounded hover:underline"
                      style={{ background: "var(--color-bg)" }}
                    >
                      Live ↗
                    </a>
                  )}
                  <button
                    onClick={() => touch(p.id)}
                    className="px-2 py-1 rounded hover:opacity-80"
                    style={{ background: "var(--color-bg)" }}
                    title="今日触ったとマーク"
                  >
                    ✋ 触った
                  </button>
                  <button
                    onClick={() => {
                      setAdviseFor(p);
                      setAdviseFocus("");
                      setAdviseText(null);
                      setAdviseMeta(null);
                    }}
                    className="px-2 py-1 rounded hover:opacity-80"
                    style={{ background: "var(--color-bg)" }}
                    title="資料 (memory + README + git log) を AI に読ませて具体アクションを提案"
                  >
                    💡 アドバイス
                  </button>
                  <button
                    onClick={() => {
                      setEditing(p);
                      setAdding(false);
                    }}
                    className="px-2 py-1 rounded hover:opacity-80"
                    style={{ background: "var(--color-bg)" }}
                  >
                    編集
                  </button>
                  <button
                    onClick={() => remove(p.id)}
                    className="px-2 py-1 rounded hover:opacity-80 ml-auto"
                    style={{ background: "var(--color-bg)", color: "#ef4444" }}
                  >
                    削除
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {sorted.length === 0 && (
          <div
            className="text-center py-16 rounded-2xl"
            style={{ background: "var(--color-surface)", border: "1px dashed var(--color-border)" }}
          >
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              プロジェクトが登録されていません。「🌱 初期 seed」を押すと既知プロジェクトが入ります。
            </p>
          </div>
        )}
      </div>

      {/* 編集モーダル */}
      {editing && (
        <div
          className="fixed inset-0 flex items-center justify-center p-4 z-50"
          style={{ background: "rgba(0,0,0,0.6)" }}
          onClick={() => {
            setEditing(null);
            setAdding(false);
          }}
        >
          <div
            className="rounded-2xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-bold mb-4">
              {adding ? "新規プロジェクト" : `編集: ${editing.name}`}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {adding && (
                <Field label="ID (slug)" required>
                  <input
                    value={editing.id}
                    onChange={(e) => setEditing({ ...editing, id: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg text-sm"
                    style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                  />
                </Field>
              )}
              <Field label="名称" required>
                <input
                  value={editing.name}
                  onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                />
              </Field>
              <Field label="カテゴリ">
                <select
                  value={editing.category}
                  onChange={(e) => setEditing({ ...editing, category: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                >
                  {Object.entries(CAT_META).map(([k, m]) => (
                    <option key={k} value={k}>
                      {m.emoji} {m.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="ステータス">
                <select
                  value={editing.status}
                  onChange={(e) => setEditing({ ...editing, status: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                >
                  {STATUS_ORDER.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_META[s].emoji} {STATUS_META[s].label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="優先度 (1-5)">
                <input
                  type="number"
                  min={1}
                  max={5}
                  value={editing.priority}
                  onChange={(e) => setEditing({ ...editing, priority: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                />
              </Field>
              <Field label="最終接触日 (YYYY-MM-DD)">
                <input
                  value={editing.last_touched || ""}
                  onChange={(e) => setEditing({ ...editing, last_touched: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                />
              </Field>
              <Field label="GitHub URL">
                <input
                  value={editing.github_url || ""}
                  onChange={(e) => setEditing({ ...editing, github_url: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                />
              </Field>
              <Field label="Live URL">
                <input
                  value={editing.live_url || ""}
                  onChange={(e) => setEditing({ ...editing, live_url: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                />
              </Field>
              <Field label="ローカルパス">
                <input
                  value={editing.local_path || ""}
                  onChange={(e) => setEditing({ ...editing, local_path: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                />
              </Field>
              <Field label="Memory 参照 (例: egaku_ai.md)">
                <input
                  value={editing.memory_ref || ""}
                  onChange={(e) => setEditing({ ...editing, memory_ref: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                />
              </Field>
              <div className="md:col-span-2">
                <Field label="一行説明">
                  <input
                    value={editing.one_liner || ""}
                    onChange={(e) => setEditing({ ...editing, one_liner: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg text-sm"
                    style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                  />
                </Field>
              </div>
              <div className="md:col-span-2">
                <Field label="次のアクション">
                  <textarea
                    value={editing.next_action || ""}
                    onChange={(e) => setEditing({ ...editing, next_action: e.target.value })}
                    rows={2}
                    className="w-full px-3 py-2 rounded-lg text-sm"
                    style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                  />
                </Field>
              </div>
              <div className="md:col-span-2">
                <Field label="メモ">
                  <textarea
                    value={editing.notes || ""}
                    onChange={(e) => setEditing({ ...editing, notes: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 rounded-lg text-sm"
                    style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                  />
                </Field>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button
                onClick={() => {
                  setEditing(null);
                  setAdding(false);
                }}
                className="px-4 py-2 rounded-lg text-sm"
                style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
              >
                キャンセル
              </button>
              <button
                onClick={() => save(editing)}
                disabled={!editing.id || !editing.name}
                className="px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                style={{ background: "var(--color-accent)", color: "white" }}
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}

      {/* アドバイス モーダル */}
      {adviseFor && (
        <div
          className="fixed inset-0 flex items-center justify-center p-4 z-50"
          style={{ background: "rgba(0,0,0,0.6)" }}
          onClick={() => setAdviseFor(null)}
        >
          <div
            className="rounded-2xl p-6 max-w-3xl w-full max-h-[90vh] overflow-y-auto"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="text-lg font-bold">💡 {adviseFor.name} へのアドバイス</h2>
                <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                  memory + README + 直近コミット 10 件を Claude Opus 4.8 に読ませて具体アクション 3 つ
                </p>
              </div>
              <button
                onClick={() => setAdviseFor(null)}
                className="text-xs px-2 py-1 rounded"
                style={{ background: "var(--color-bg)" }}
              >
                閉じる
              </button>
            </div>

            <div className="mb-4">
              <label className="block text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>
                今の文脈 (任意 — 例: 「今日 2 時間しかない」「リリース前」「方向に迷ってる」)
              </label>
              <textarea
                value={adviseFocus}
                onChange={(e) => setAdviseFocus(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 rounded-lg text-sm"
                style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
                placeholder="(なくても OK)"
              />
              <button
                onClick={() => requestAdvice(adviseFor, adviseFocus)}
                disabled={adviseLoading}
                className="mt-2 px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                style={{ background: "var(--color-accent)", color: "white" }}
              >
                {adviseLoading ? "Claude 考え中..." : "アドバイスを取得"}
              </button>
            </div>

            {adviseMeta && (
              <div className="text-xs mb-3" style={{ color: "var(--color-text-muted)" }}>
                資料 {adviseMeta.docs_count} 件 / 直近コミット {adviseMeta.commits_used} 件 を参照
              </div>
            )}

            {adviseText && (
              <div
                className="p-4 rounded-lg text-sm whitespace-pre-wrap"
                style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)", lineHeight: 1.7 }}
              >
                {adviseText}
              </div>
            )}

            {!adviseText && !adviseLoading && (
              <div className="text-xs mt-4 p-3 rounded-lg" style={{ background: "var(--color-bg)", color: "var(--color-text-muted)" }}>
                ヒント: 資料が空の場合は、ローカルで <code>python3 ~/.koach-os/scripts/sync_projects.py --with-docs</code> を 1 回叩くと、memory ファイル + README + 直近 10 コミットが backend に同期されます。
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>
        {label}
        {required && <span style={{ color: "#ef4444" }}> *</span>}
      </label>
      {children}
    </div>
  );
}
