"use client";

import { useEffect, useState } from "react";

type Citation = {
  index: number;
  kind: string;
  title: string;
  timestamp: string;
  excerpt: string;
  relevance: number;
};

type Result = {
  query: string;
  answer: string;
  citations: Citation[];
  indexed_count: number;
  engine_used: string;
};

const KIND_META: Record<string, { emoji: string; color: string }> = {
  memo: { emoji: "🪧", color: "#3b82f6" },
  decision: { emoji: "🧭", color: "#a855f7" },
  failure: { emoji: "🪨", color: "#ef4444" },
  private: { emoji: "🤫", color: "#71717a" },
  backlog: { emoji: "📋", color: "#10b981" },
};

const PRESET_QUESTIONS = [
  "EGAKU AI を始めた理由は何だったか",
  "過去にメンタルが落ちたパターン",
  "保育園の送り迎えに関する決定の経緯",
  "ブレイクダンスを再開しようと決めた瞬間",
  "失敗から得た一番大きな学び",
];

export default function AskPage() {
  const [query, setQuery] = useState("");
  const [engine, setEngine] = useState("claude");
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [indexed, setIndexed] = useState<number | null>(null);
  const [reindexing, setReindexing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/rag/stats")
      .then((r) => r.json())
      .then((d) => setIndexed(d.indexed_count));
  }, []);

  const run = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await fetch("/api/rag/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, engine, top_k: 6 }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setResult(await r.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const reindex = async () => {
    setReindexing(true);
    try {
      const r = await fetch("/api/rag/reindex", { method: "POST" });
      if (r.ok) {
        const d = await r.json();
        setIndexed(d.indexed ?? 0);
      }
    } finally {
      setReindexing(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="px-8 pt-12 pb-8" style={{ background: "radial-gradient(ellipse at top, rgba(59, 130, 246, 0.12), transparent 60%)" }}>
        <div className="max-w-4xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            Personal Knowledge Base
          </p>
          <h1 className="text-4xl font-bold tracking-tight">過去の自分に聞く</h1>
          <p className="mt-3 text-sm" style={{ color: "var(--color-text-muted)" }}>
            memo / decision / failure / private chat / backlog から引用付きで回答します。
          </p>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-4xl mx-auto space-y-6">
          <div
            className="rounded-2xl p-5 flex items-center justify-between"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
          >
            <div>
              <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                インデックス済み
              </div>
              <div className="text-xl font-mono font-bold">
                {indexed === null ? "..." : `${indexed} 件`}
              </div>
            </div>
            <button
              onClick={reindex}
              disabled={reindexing}
              className="px-4 py-2 rounded-full text-sm disabled:opacity-50"
              style={{ background: "var(--color-surface-hover)", color: "var(--color-text)" }}
            >
              {reindexing ? "構築中..." : "再構築"}
            </button>
          </div>

          <div
            className="rounded-2xl p-6 space-y-3"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
          >
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={3}
              placeholder="質問を入力（例: 「半年前に EGAKU の料金設定をどう決めたか」）"
              className="w-full px-4 py-2.5 rounded-lg text-sm"
              style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
            />
            <div className="flex flex-wrap gap-1.5">
              {PRESET_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => setQuery(q)}
                  className="text-[11px] px-2.5 py-1 rounded-full"
                  style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}
                >
                  {q}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-3">
              <select
                value={engine}
                onChange={(e) => setEngine(e.target.value)}
                className="px-3 py-2 rounded text-sm"
                style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
              >
                <option value="claude">Claude</option>
                <option value="gpt">GPT</option>
                <option value="gemini">Gemini</option>
              </select>
              <button
                onClick={run}
                disabled={loading || !query.trim()}
                className="px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50"
                style={{ background: "var(--color-accent)", color: "white" }}
              >
                {loading ? "検索中..." : "聞く"}
              </button>
            </div>
          </div>

          {error && (
            <div className="p-4 rounded-2xl text-sm" style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid var(--color-red)", color: "var(--color-red)" }}>
              {error}
            </div>
          )}

          {result && (
            <>
              <div
                className="rounded-2xl p-6"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
              >
                <div className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--color-accent)" }}>
                  回答
                </div>
                <div className="text-[15px] whitespace-pre-wrap leading-[1.85]">{result.answer}</div>
              </div>

              <div className="space-y-2">
                <div className="text-xs uppercase tracking-wider" style={{ color: "var(--color-text-muted)" }}>
                  引用元 ({result.citations.length})
                </div>
                {result.citations.map((c) => {
                  const meta = KIND_META[c.kind] ?? { emoji: "•", color: "#71717a" };
                  return (
                    <div
                      key={c.index}
                      className="rounded-xl p-4"
                      style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span
                          className="text-xs font-mono px-2 py-0.5 rounded-full"
                          style={{ background: `${meta.color}20`, color: meta.color }}
                        >
                          [{c.index}] {meta.emoji} {c.kind}
                        </span>
                        <span className="text-[10px] font-mono" style={{ color: "var(--color-text-muted)" }}>
                          {c.timestamp.slice(0, 10)} ・ rel {(c.relevance * 100).toFixed(0)}%
                        </span>
                      </div>
                      {c.title && <div className="text-sm font-medium mb-1">{c.title}</div>}
                      <div className="text-xs leading-relaxed" style={{ color: "var(--color-text-muted)" }}>
                        {c.excerpt}
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
