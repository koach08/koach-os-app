"use client";

import { useEffect, useState } from "react";

type Category =
  | "career" | "research" | "creative" | "family" | "health"
  | "learning" | "side_project" | "admin" | "rest" | "other";

const CATEGORIES: { id: Category; emoji: string; label: string; color: string }[] = [
  { id: "career", emoji: "💼", label: "キャリア", color: "#3b82f6" },
  { id: "research", emoji: "🔬", label: "研究", color: "#0891b2" },
  { id: "creative", emoji: "🎨", label: "クリエイティブ", color: "#a855f7" },
  { id: "family", emoji: "👨‍👩‍👧", label: "家族", color: "#f59e0b" },
  { id: "health", emoji: "💪", label: "健康・ダンス・アクロ", color: "#22c55e" },
  { id: "learning", emoji: "📚", label: "学習", color: "#06b6d4" },
  { id: "side_project", emoji: "🚀", label: "副プロジェクト", color: "#8b5cf6" },
  { id: "admin", emoji: "📋", label: "事務", color: "#64748b" },
  { id: "rest", emoji: "🌙", label: "休息", color: "#71717a" },
  { id: "other", emoji: "✨", label: "その他", color: "#94a3b8" },
];

type BacklogItem = {
  id: string;
  title: string;
  category: Category;
  estimated_minutes: number;
  urgency: "high" | "medium" | "low";
  notes: string;
  needs_ai: boolean;
  done: boolean;
};

type LifeBlock = {
  id: string;
  title: string;
  weekday: number;
  start_hm: string;
  end_hm: string;
  category: Category;
};

const WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"];

const ENGINES = [
  { id: "claude", label: "Claude", emoji: "🧠" },
  { id: "gpt", label: "GPT", emoji: "🤖" },
  { id: "gemini", label: "Gemini", emoji: "✨" },
  { id: "grok", label: "Grok", emoji: "🌀" },
];

export default function CoachPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "";

  const [backlog, setBacklog] = useState<BacklogItem[]>([]);
  const [lifeBlocks, setLifeBlocks] = useState<LifeBlock[]>([]);
  const [plan, setPlan] = useState<string | null>(null);
  const [planMeta, setPlanMeta] = useState<{ calendar_events_count: number; backlog_count: number; engine_used: string } | null>(null);
  type PlannedBlock = { title: string; start_iso: string; end_iso: string; category: Category; description: string };
  const [blocks, setBlocks] = useState<PlannedBlock[]>([]);
  const [selectedBlocks, setSelectedBlocks] = useState<Set<number>>(new Set());
  const [parsingBlocks, setParsingBlocks] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [commitResult, setCommitResult] = useState<{ ok: number; failed: number } | null>(null);
  const [horizon, setHorizon] = useState(7);
  const [engine, setEngine] = useState("claude");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Backlog form
  const [newItem, setNewItem] = useState<BacklogItem>({
    id: "", title: "", category: "career", estimated_minutes: 60, urgency: "medium", notes: "", needs_ai: false, done: false,
  });
  // Life block form
  const [newBlock, setNewBlock] = useState<LifeBlock>({
    id: "", title: "", weekday: 0, start_hm: "17:00", end_hm: "18:30", category: "family",
  });
  const [showLifeForm, setShowLifeForm] = useState(false);

  const loadAll = async () => {
    try {
      const [bRes, lRes] = await Promise.all([
        fetch(`${apiBase}/api/productivity/backlog`),
        fetch(`${apiBase}/api/productivity/life-blocks`),
      ]);
      setBacklog((await bRes.json()).items ?? []);
      setLifeBlocks((await lRes.json()).items ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => { loadAll(); }, []);

  const addBacklog = async () => {
    if (!newItem.title.trim()) return;
    const r = await fetch(`${apiBase}/api/productivity/backlog`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(newItem),
    });
    if (r.ok) {
      const created = await r.json();
      setBacklog((b) => [...b, created]);
      setNewItem({ ...newItem, title: "", notes: "" });
    }
  };

  const toggleDone = async (item: BacklogItem) => {
    const updated = { ...item, done: !item.done };
    const r = await fetch(`${apiBase}/api/productivity/backlog/${item.id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(updated),
    });
    if (r.ok) {
      setBacklog((b) => b.map((x) => (x.id === item.id ? updated : x)));
    }
  };

  const deleteBacklog = async (id: string) => {
    await fetch(`${apiBase}/api/productivity/backlog/${id}`, { method: "DELETE" });
    setBacklog((b) => b.filter((x) => x.id !== id));
  };

  const addLifeBlock = async () => {
    if (!newBlock.title.trim()) return;
    const r = await fetch(`${apiBase}/api/productivity/life-blocks`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(newBlock),
    });
    if (r.ok) {
      const created = await r.json();
      setLifeBlocks((l) => [...l, created]);
      setNewBlock({ ...newBlock, title: "" });
    }
  };

  const deleteLifeBlock = async (id: string) => {
    await fetch(`${apiBase}/api/productivity/life-blocks/${id}`, { method: "DELETE" });
    setLifeBlocks((l) => l.filter((x) => x.id !== id));
  };

  const generatePlan = async () => {
    setGenerating(true);
    setError(null);
    setPlan(null);
    setBlocks([]);
    setSelectedBlocks(new Set());
    setCommitResult(null);
    try {
      const r = await fetch(`${apiBase}/api/productivity/plan`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ horizon_days: horizon, engine }),
      });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      setPlan(d.plan);
      setPlanMeta({
        calendar_events_count: d.calendar_events_count,
        backlog_count: d.backlog_count,
        engine_used: d.engine_used,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setGenerating(false);
    }
  };

  const parseBlocks = async () => {
    if (!plan) return;
    setParsingBlocks(true);
    setError(null);
    try {
      const r = await fetch(`${apiBase}/api/productivity/parse-plan`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan }),
      });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      const bs: PlannedBlock[] = d.blocks ?? [];
      setBlocks(bs);
      // pre-select all
      setSelectedBlocks(new Set(bs.map((_, i) => i)));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setParsingBlocks(false);
    }
  };

  const commitBlocks = async () => {
    const chosen = blocks.filter((_, i) => selectedBlocks.has(i));
    if (chosen.length === 0) return;
    setCommitting(true);
    setError(null);
    try {
      const r = await fetch(`${apiBase}/api/productivity/commit-plan`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ blocks: chosen }),
      });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      const ok = (d.results ?? []).filter((r: { ok: boolean }) => r.ok).length;
      const failed = (d.results ?? []).length - ok;
      setCommitResult({ ok, failed });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCommitting(false);
    }
  };

  const toggleBlock = (i: number) => {
    setSelectedBlocks((s) => {
      const next = new Set(s);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  const catMeta = (id: Category) => CATEGORIES.find((c) => c.id === id) ?? CATEGORIES[CATEGORIES.length - 1];

  return (
    <div className="flex-1 overflow-y-auto">
      <div
        className="px-8 pt-12 pb-8"
        style={{
          background:
            "radial-gradient(ellipse at top left, rgba(34, 197, 94, 0.15), transparent 60%), radial-gradient(ellipse at top right, rgba(168, 85, 247, 0.10), transparent 50%)",
        }}
      >
        <div className="max-w-6xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            PRODUCTIVITY COACH
          </p>
          <h1
            className="text-4xl font-bold tracking-tight"
            style={{
              background: "linear-gradient(135deg, #fafafa 0%, #4ade80 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            時間の使い方を AI と整える
          </h1>
          <p className="mt-3 text-sm max-w-2xl" style={{ color: "var(--color-text-muted)" }}>
            Google Calendar の固定予定 + 毎週の生活ブロック + バックログから、AI が空き時間を集計し、バランスのとれた週次スケジュールを提案します。タスクごとに最適な AI ツールも教えてくれます。
          </p>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-6xl mx-auto space-y-6">
          {error && (
            <div className="rounded-2xl p-4 text-sm" style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid var(--color-red)", color: "var(--color-red)" }}>
              {error}
            </div>
          )}

          {/* Backlog */}
          <div className="rounded-2xl p-6" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
            <h2 className="text-lg font-semibold mb-3">🎒 バックログ (やりたい / やらないといけないこと)</h2>

            <div className="space-y-2 mb-4">
              {backlog.length === 0 && (
                <div className="text-sm" style={{ color: "var(--color-text-muted)" }}>まだ項目がありません。下のフォームから追加。</div>
              )}
              {backlog.map((b) => {
                const cm = catMeta(b.category);
                return (
                  <div
                    key={b.id}
                    className="flex items-center gap-3 p-2.5 rounded-lg"
                    style={{
                      background: "var(--color-background)",
                      border: "1px solid var(--color-border)",
                      borderLeft: `3px solid ${cm.color}`,
                      opacity: b.done ? 0.5 : 1,
                    }}
                  >
                    <input type="checkbox" checked={b.done} onChange={() => toggleDone(b)} />
                    <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: `${cm.color}25`, color: cm.color }}>
                      {cm.emoji} {cm.label}
                    </span>
                    <span className="text-xs font-mono" style={{ color: "var(--color-text-muted)" }}>
                      {b.urgency === "high" ? "🔴" : b.urgency === "medium" ? "🟡" : "🟢"} {b.estimated_minutes}分
                    </span>
                    <span className={`flex-1 text-sm ${b.done ? "line-through" : ""}`}>{b.title}</span>
                    {b.needs_ai && <span className="text-xs">🤖 AI推奨</span>}
                    <button onClick={() => deleteBacklog(b.id)} className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                      🗑
                    </button>
                  </div>
                );
              })}
            </div>

            <div className="grid gap-2" style={{ gridTemplateColumns: "1fr auto auto auto auto auto" }}>
              <input
                type="text" placeholder="タイトル (例: 科研費草案を書く)"
                value={newItem.title} onChange={(e) => setNewItem({ ...newItem, title: e.target.value })}
                className="px-3 py-2 rounded-lg text-sm"
                style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
              />
              <select value={newItem.category} onChange={(e) => setNewItem({ ...newItem, category: e.target.value as Category })}
                className="px-3 py-2 rounded-lg text-sm" style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}>
                {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.emoji} {c.label}</option>)}
              </select>
              <select value={newItem.urgency} onChange={(e) => setNewItem({ ...newItem, urgency: e.target.value as "high" | "medium" | "low" })}
                className="px-3 py-2 rounded-lg text-sm" style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}>
                <option value="high">🔴 急ぎ</option>
                <option value="medium">🟡 普通</option>
                <option value="low">🟢 ゆっくり</option>
              </select>
              <input type="number" min={5} step={5} value={newItem.estimated_minutes}
                onChange={(e) => setNewItem({ ...newItem, estimated_minutes: Number(e.target.value) || 60 })}
                className="px-3 py-2 rounded-lg text-sm w-20" placeholder="分"
                style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
              />
              <label className="flex items-center gap-1 text-sm px-2" style={{ color: "var(--color-text-muted)" }}>
                <input type="checkbox" checked={newItem.needs_ai} onChange={(e) => setNewItem({ ...newItem, needs_ai: e.target.checked })} />
                🤖
              </label>
              <button onClick={addBacklog} disabled={!newItem.title.trim()}
                className="px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                style={{ background: "var(--color-accent)", color: "white" }}>
                追加
              </button>
            </div>
          </div>

          {/* Life Blocks */}
          <div className="rounded-2xl p-6" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold">🏠 毎週の生活ブロック (お迎え、運動、家族時間 etc.)</h2>
              <button onClick={() => setShowLifeForm((s) => !s)} className="text-sm underline" style={{ color: "var(--color-text-muted)" }}>
                {showLifeForm ? "閉じる" : "+ 追加"}
              </button>
            </div>

            {lifeBlocks.length === 0 ? (
              <div className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                例: 月〜金 17:00-18:30 保育園お迎え、土 10:00-11:30 ブレイクダンス練習
              </div>
            ) : (
              <div className="grid md:grid-cols-2 gap-2 mb-3">
                {lifeBlocks.map((b) => {
                  const cm = catMeta(b.category);
                  return (
                    <div key={b.id} className="flex items-center gap-2 p-2 rounded-lg"
                      style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", borderLeft: `3px solid ${cm.color}` }}>
                      <span className="text-xs font-mono px-1.5 py-0.5 rounded" style={{ background: "var(--color-surface)" }}>
                        {WEEKDAYS[b.weekday]} {b.start_hm}-{b.end_hm}
                      </span>
                      <span className="flex-1 text-sm">{cm.emoji} {b.title}</span>
                      <button onClick={() => deleteLifeBlock(b.id)} className="text-xs" style={{ color: "var(--color-text-muted)" }}>🗑</button>
                    </div>
                  );
                })}
              </div>
            )}

            {showLifeForm && (
              <div className="flex gap-2 flex-wrap items-center">
                <input type="text" placeholder="例: 保育園お迎え" value={newBlock.title}
                  onChange={(e) => setNewBlock({ ...newBlock, title: e.target.value })}
                  className="flex-1 px-3 py-2 rounded-lg text-sm min-w-[200px]"
                  style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                />
                <select value={newBlock.weekday} onChange={(e) => setNewBlock({ ...newBlock, weekday: Number(e.target.value) })}
                  className="px-3 py-2 rounded-lg text-sm" style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}>
                  {WEEKDAYS.map((w, i) => <option key={w} value={i}>{w}曜</option>)}
                </select>
                <input type="time" value={newBlock.start_hm} onChange={(e) => setNewBlock({ ...newBlock, start_hm: e.target.value })}
                  className="px-3 py-2 rounded-lg text-sm" style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }} />
                <span style={{ color: "var(--color-text-muted)" }}>〜</span>
                <input type="time" value={newBlock.end_hm} onChange={(e) => setNewBlock({ ...newBlock, end_hm: e.target.value })}
                  className="px-3 py-2 rounded-lg text-sm" style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }} />
                <select value={newBlock.category} onChange={(e) => setNewBlock({ ...newBlock, category: e.target.value as Category })}
                  className="px-3 py-2 rounded-lg text-sm" style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}>
                  {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.emoji} {c.label}</option>)}
                </select>
                <button onClick={addLifeBlock} disabled={!newBlock.title.trim()}
                  className="px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                  style={{ background: "var(--color-accent)", color: "white" }}>
                  追加
                </button>
              </div>
            )}
          </div>

          {/* Generate plan */}
          <div className="rounded-2xl p-6" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
            <h2 className="text-lg font-semibold mb-3">🤖 AI にスケジュール案を出させる</h2>
            <div className="flex items-center gap-3 flex-wrap mb-4">
              <label className="text-sm" style={{ color: "var(--color-text-muted)" }}>期間</label>
              <select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}
                className="px-3 py-2 rounded-lg text-sm" style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}>
                <option value={3}>3日</option>
                <option value={7}>1週間</option>
                <option value={14}>2週間</option>
                <option value={30}>1ヶ月</option>
              </select>
              <label className="text-sm" style={{ color: "var(--color-text-muted)" }}>AI</label>
              <select value={engine} onChange={(e) => setEngine(e.target.value)}
                className="px-3 py-2 rounded-lg text-sm" style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}>
                {ENGINES.map((e) => <option key={e.id} value={e.id}>{e.emoji} {e.label}</option>)}
              </select>
              <button onClick={generatePlan} disabled={generating}
                className="ml-auto px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50 hover:scale-[1.02] transition-all"
                style={{ background: "var(--color-accent)", color: "white", boxShadow: "0 4px 14px rgba(59, 130, 246, 0.35)" }}>
                {generating ? "生成中…" : "🎯 スケジュール案を生成"}
              </button>
            </div>
            {planMeta && (
              <div className="text-xs mb-3" style={{ color: "var(--color-text-muted)" }}>
                Calendar {planMeta.calendar_events_count} 件 / バックログ {planMeta.backlog_count} 件 / {planMeta.engine_used}
              </div>
            )}
            {plan && (
              <>
                <pre className="text-sm whitespace-pre-wrap p-4 rounded-lg"
                  style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", lineHeight: 1.7 }}>
                  {plan}
                </pre>

                <div className="mt-4 flex items-center gap-3 flex-wrap">
                  <button
                    onClick={parseBlocks}
                    disabled={parsingBlocks}
                    className="px-4 py-2 rounded-full text-sm font-medium disabled:opacity-50"
                    style={{ background: "var(--color-surface-hover)", color: "var(--color-text)", border: "1px solid var(--color-border)" }}
                  >
                    {parsingBlocks ? "解析中…" : "📋 提案を Calendar 用ブロックに変換"}
                  </button>
                  {blocks.length > 0 && (
                    <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                      {blocks.length} ブロック抽出 / {selectedBlocks.size} 件を Calendar に書き込み予定
                    </span>
                  )}
                </div>

                {blocks.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {blocks.map((b, i) => {
                      const cm = catMeta(b.category);
                      const sel = selectedBlocks.has(i);
                      const start = new Date(b.start_iso);
                      const end = new Date(b.end_iso);
                      const dateLabel = start.toLocaleString("ja-JP", { month: "numeric", day: "numeric", weekday: "short" });
                      return (
                        <label
                          key={i}
                          className="flex items-center gap-3 p-2.5 rounded-lg cursor-pointer"
                          style={{
                            background: "var(--color-background)",
                            border: `1px solid ${sel ? cm.color : "var(--color-border)"}`,
                            borderLeft: `4px solid ${cm.color}`,
                            opacity: sel ? 1 : 0.55,
                          }}
                        >
                          <input type="checkbox" checked={sel} onChange={() => toggleBlock(i)} />
                          <span className="text-xs font-mono shrink-0" style={{ color: "var(--color-text-muted)" }}>
                            {dateLabel}
                          </span>
                          <span className="text-xs font-mono shrink-0" style={{ color: "var(--color-text-muted)", minWidth: "5.5rem" }}>
                            {start.toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" })}-
                            {end.toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" })}
                          </span>
                          <span className="text-xs px-2 py-0.5 rounded-full shrink-0" style={{ background: `${cm.color}25`, color: cm.color }}>
                            {cm.emoji} {cm.label}
                          </span>
                          <span className="flex-1 text-sm">{b.title}</span>
                        </label>
                      );
                    })}

                    <div className="flex items-center gap-3 pt-2">
                      <button
                        onClick={commitBlocks}
                        disabled={committing || selectedBlocks.size === 0}
                        className="px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50 hover:scale-[1.02] transition-all"
                        style={{ background: "var(--color-accent)", color: "white", boxShadow: "0 4px 14px rgba(59, 130, 246, 0.35)" }}
                      >
                        {committing ? "書き込み中…" : `✅ ${selectedBlocks.size} 件を Google Calendar に書き込む`}
                      </button>
                      {commitResult && (
                        <span className="text-sm" style={{ color: commitResult.failed === 0 ? "var(--color-green)" : "var(--color-red)" }}>
                          {commitResult.failed === 0
                            ? `✓ ${commitResult.ok} 件追加しました`
                            : `${commitResult.ok} 件成功 / ${commitResult.failed} 件失敗`}
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
