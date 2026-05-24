"use client";

import { useRef, useState } from "react";

type ExtractResult = {
  summary: string;
  decisions: { title: string; reasoning: string }[];
  tasks: { title: string; urgency: string; category: string }[];
  memos: { title: string; body: string }[];
  events: { title: string; start_iso: string; end_iso: string; location: string }[];
  key_quotes: { timestamp: string; text: string }[];
  _meta?: Record<string, unknown>;
};

type Selection = { decisions: Set<number>; tasks: Set<number>; memos: Set<number>; events: Set<number> };

export default function ExtractPage() {
  const [mode, setMode] = useState<"file" | "youtube">("file");
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [result, setResult] = useState<ExtractResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection>({
    decisions: new Set(),
    tasks: new Set(),
    memos: new Set(),
    events: new Set(),
  });
  const [committing, setCommitting] = useState(false);
  const [committed, setCommitted] = useState<{ ok: number; fail: number } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setResult(null);
    setError(null);
    setSelection({ decisions: new Set(), tasks: new Set(), memos: new Set(), events: new Set() });
    setCommitted(null);
  };

  const selectAll = (r: ExtractResult) => {
    setSelection({
      decisions: new Set(r.decisions.map((_, i) => i)),
      tasks: new Set(r.tasks.map((_, i) => i)),
      memos: new Set(r.memos.map((_, i) => i)),
      events: new Set(r.events.map((_, i) => i)),
    });
  };

  const runFile = async () => {
    const f = fileRef.current?.files?.[0];
    if (!f) {
      setError("ファイルを選んでください");
      return;
    }
    reset();
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const r = await fetch("/api/media/extract", { method: "POST", body: fd });
      if (!r.ok) throw new Error(await r.text());
      const d = (await r.json()) as ExtractResult;
      setResult(d);
      selectAll(d);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const runYoutube = async () => {
    if (!youtubeUrl.trim()) {
      setError("URL を入れてください");
      return;
    }
    reset();
    setLoading(true);
    try {
      const r = await fetch("/api/media/extract-youtube", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: youtubeUrl.trim() }),
      });
      if (!r.ok) throw new Error(await r.text());
      const d = (await r.json()) as ExtractResult;
      setResult(d);
      selectAll(d);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const toggle = (kind: keyof Selection, idx: number) => {
    setSelection((prev) => {
      const next = { ...prev };
      const s = new Set(prev[kind]);
      if (s.has(idx)) s.delete(idx);
      else s.add(idx);
      next[kind] = s;
      return next;
    });
  };

  const commit = async () => {
    if (!result) return;
    const items: { kind: string; data: unknown }[] = [];
    selection.decisions.forEach((i) => items.push({ kind: "decision", data: result.decisions[i] }));
    selection.tasks.forEach((i) => items.push({ kind: "task", data: result.tasks[i] }));
    selection.memos.forEach((i) => items.push({ kind: "memo", data: result.memos[i] }));
    selection.events.forEach((i) => items.push({ kind: "event", data: result.events[i] }));
    if (items.length === 0) return;
    setCommitting(true);
    try {
      const r = await fetch("/api/media/commit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items }),
      });
      const d = await r.json();
      const ok = (d.results ?? []).filter((x: { ok: boolean }) => x.ok).length;
      const fail = (d.results ?? []).length - ok;
      setCommitted({ ok, fail });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCommitting(false);
    }
  };

  const selCount =
    selection.decisions.size + selection.tasks.size + selection.memos.size + selection.events.size;

  return (
    <div className="flex-1 overflow-y-auto">
      <div
        className="px-8 pt-12 pb-8"
        style={{
          background:
            "radial-gradient(ellipse at top left, rgba(124, 58, 237, 0.12), transparent 60%), radial-gradient(ellipse at top right, rgba(59, 130, 246, 0.08), transparent 50%)",
        }}
      >
        <div className="max-w-4xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            Media → Structured (Gemini)
          </p>
          <h1 className="text-4xl font-bold tracking-tight">講義・会議録画から抽出</h1>
          <p className="mt-3 text-sm" style={{ color: "var(--color-text-muted)" }}>
            動画 / 長尺音声 / YouTube URL を Gemini 2.0 に投げて、決定・タスク・メモ・Calendar イベントに自動振り分け。
          </p>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-4xl mx-auto space-y-6">
          <div
            className="rounded-2xl p-5 space-y-3"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
          >
            <div className="flex gap-2">
              <button
                onClick={() => {
                  setMode("file");
                  reset();
                }}
                className="px-4 py-1.5 rounded-full text-xs"
                style={{
                  background: mode === "file" ? "var(--color-text)" : "transparent",
                  color: mode === "file" ? "var(--color-background)" : "var(--color-text-muted)",
                  border: "1px solid var(--color-border)",
                }}
              >
                📁 ファイル
              </button>
              <button
                onClick={() => {
                  setMode("youtube");
                  reset();
                }}
                className="px-4 py-1.5 rounded-full text-xs"
                style={{
                  background: mode === "youtube" ? "var(--color-text)" : "transparent",
                  color: mode === "youtube" ? "var(--color-background)" : "var(--color-text-muted)",
                  border: "1px solid var(--color-border)",
                }}
              >
                ▶️ YouTube URL
              </button>
            </div>
            {mode === "file" ? (
              <>
                <input
                  ref={fileRef}
                  type="file"
                  accept="video/*,audio/*"
                  className="w-full text-sm"
                  style={{ color: "var(--color-text-muted)" }}
                />
                <button
                  onClick={runFile}
                  disabled={loading}
                  className="px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50"
                  style={{ background: "#7c3aed", color: "white" }}
                >
                  {loading ? "抽出中..." : "抽出する (mp4/mp3/m4a/wav 等)"}
                </button>
                <p className="text-[11px]" style={{ color: "var(--color-text-muted)" }}>
                  動画は ACTIVE 待ちで 10〜60 秒。100MB を超えると Railway 経由でタイムアウトの可能性あり (その場合は YouTube アップ → URL 経由推奨)
                </p>
              </>
            ) : (
              <>
                <input
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=..."
                  className="w-full px-3 py-2 rounded text-sm"
                  style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                />
                <button
                  onClick={runYoutube}
                  disabled={loading || !youtubeUrl.trim()}
                  className="px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50"
                  style={{ background: "#7c3aed", color: "white" }}
                >
                  {loading ? "抽出中..." : "抽出する"}
                </button>
              </>
            )}
          </div>

          {error && (
            <div className="p-3 rounded-xl text-sm" style={{ background: "rgba(239, 68, 68, 0.08)", color: "var(--color-red)" }}>
              {error}
            </div>
          )}

          {committed && (
            <div className="p-3 rounded-xl text-sm" style={{ background: "rgba(16, 185, 129, 0.08)", color: "#10b981" }}>
              ✓ {committed.ok} 件投入 / 失敗 {committed.fail} 件
            </div>
          )}

          {result && (
            <>
              <div
                className="rounded-2xl p-5"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
              >
                <div className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--color-text-muted)" }}>
                  要約
                </div>
                <p className="text-sm leading-relaxed">{result.summary}</p>
              </div>

              <Group
                emoji="🧭"
                label="決定"
                color="#a855f7"
                items={result.decisions.map((d, i) => ({
                  i,
                  title: d.title,
                  sub: d.reasoning,
                }))}
                selected={selection.decisions}
                toggle={(i) => toggle("decisions", i)}
              />
              <Group
                emoji="📋"
                label="タスク"
                color="#10b981"
                items={result.tasks.map((t, i) => ({
                  i,
                  title: t.title,
                  sub: `[${t.urgency}] ${t.category}`,
                }))}
                selected={selection.tasks}
                toggle={(i) => toggle("tasks", i)}
              />
              <Group
                emoji="🪧"
                label="メモ"
                color="#3b82f6"
                items={result.memos.map((m, i) => ({
                  i,
                  title: m.title,
                  sub: m.body,
                }))}
                selected={selection.memos}
                toggle={(i) => toggle("memos", i)}
              />
              <Group
                emoji="📅"
                label="Calendar イベント"
                color="#f59e0b"
                items={result.events.map((e, i) => ({
                  i,
                  title: e.title,
                  sub: `${e.start_iso}${e.location ? " @ " + e.location : ""}`,
                }))}
                selected={selection.events}
                toggle={(i) => toggle("events", i)}
              />

              {result.key_quotes.length > 0 && (
                <div
                  className="rounded-2xl p-5"
                  style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
                >
                  <div className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--color-text-muted)" }}>
                    引用 (timestamp 付き)
                  </div>
                  <ul className="space-y-2 text-sm">
                    {result.key_quotes.map((q, i) => (
                      <li key={i} className="flex gap-3 items-start">
                        <span className="font-mono text-xs shrink-0 pt-0.5" style={{ color: "var(--color-text-muted)" }}>
                          {q.timestamp}
                        </span>
                        <span>{q.text}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="sticky bottom-4 flex justify-end">
                <button
                  onClick={commit}
                  disabled={committing || selCount === 0}
                  className="px-6 py-3 rounded-full text-sm font-medium shadow-lg disabled:opacity-50"
                  style={{ background: "var(--color-accent)", color: "white" }}
                >
                  {committing ? "投入中..." : `選択した ${selCount} 件を保存`}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Group({
  emoji,
  label,
  color,
  items,
  selected,
  toggle,
}: {
  emoji: string;
  label: string;
  color: string;
  items: { i: number; title: string; sub: string }[];
  selected: Set<number>;
  toggle: (i: number) => void;
}) {
  if (items.length === 0) return null;
  return (
    <section
      className="rounded-2xl p-5"
      style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
    >
      <header className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-sm flex items-center gap-2">
          <span>{emoji}</span>
          <span>{label}</span>
        </h2>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full" style={{ background: `${color}20`, color }}>
          {selected.size} / {items.length}
        </span>
      </header>
      <ul className="space-y-2">
        {items.map((it) => {
          const on = selected.has(it.i);
          return (
            <li
              key={it.i}
              onClick={() => toggle(it.i)}
              className="flex gap-3 items-start p-2 rounded-lg cursor-pointer hover:bg-[var(--color-surface-hover)]"
            >
              <span
                className="mt-1 shrink-0"
                style={{
                  width: "1rem",
                  height: "1rem",
                  borderRadius: "0.3rem",
                  border: on ? `1px solid ${color}` : "1px solid var(--color-border)",
                  background: on ? color : "transparent",
                  color: "white",
                  fontSize: "0.65rem",
                  lineHeight: 1,
                  textAlign: "center",
                  paddingTop: "0.1rem",
                }}
              >
                {on ? "✓" : ""}
              </span>
              <div className="flex-1">
                <div className="text-sm font-medium">{it.title}</div>
                {it.sub && (
                  <div className="text-[11px] mt-0.5" style={{ color: "var(--color-text-muted)" }}>
                    {it.sub}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
