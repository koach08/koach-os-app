"use client";

import { useState } from "react";

type Result = {
  ok: boolean;
  router: { engine: string; model: string; reason: string };
  result: string;
  latency_ms: number;
};

const ENGINE_EMOJI: Record<string, string> = {
  claude: "🧠",
  gpt: "🤖",
  gemini: "✨",
  grok: "🛰",
  venice: "🤫",
  perplexity: "🔎",
  groq: "⚡",
};

const PRESETS = [
  "今日の X で AI 関連のトレンドを 5 つまとめて",
  "EGAKU AI の有料転換が伸びない原因を 3 仮説、検証順に",
  "院生に博士進学を勧める時の論点",
  "今夜 1 時間でできる koach-os の改善案 1 つ",
  "Stripe の subscription cancel の正攻法 (TS, claudeにきく)",
];

export default function DispatchAutoPage() {
  const [goal, setGoal] = useState("");
  const [context, setContext] = useState("");
  const [forceEngine, setForceEngine] = useState<string>("");
  const [maxTokens, setMaxTokens] = useState<number>(2000);
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<Result["router"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const run = async () => {
    if (!goal.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await fetch("/api/dispatch/auto", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          goal,
          context: context || null,
          max_tokens: maxTokens,
          force_engine: forceEngine || null,
        }),
      });
      if (!r.ok) throw new Error(await r.text());
      setResult(await r.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const doPreview = async () => {
    if (!goal.trim()) return;
    setPreviewing(true);
    setPreview(null);
    try {
      const r = await fetch("/api/dispatch/auto/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal, context: context || null }),
      });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      setPreview(d.router);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPreviewing(false);
    }
  };

  const copy = () => {
    if (!result) return;
    navigator.clipboard.writeText(result.result);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div
        className="px-8 pt-12 pb-8"
        style={{ background: "radial-gradient(ellipse at top, rgba(139, 92, 246, 0.12), transparent 60%)" }}
      >
        <div className="max-w-4xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            Auto Dispatch
          </p>
          <h1 className="text-4xl font-bold tracking-tight">🎯 AI 自動ディスパッチ</h1>
          <p className="mt-3 text-sm" style={{ color: "var(--color-text-muted)" }}>
            目的を投げると、ルーター LLM が claude / gpt / gemini / grok / venice / perplexity / groq から最適 1 つを選び、そのまま実行して結果を返します。
          </p>

          <div className="mt-6">
            <label className="text-xs block mb-1" style={{ color: "var(--color-text-muted)" }}>
              目的 (1 文で)
            </label>
            <textarea
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="例: 院生に博士進学を勧める時の論点"
              className="w-full rounded-lg p-3 text-sm"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", minHeight: 80 }}
            />
          </div>

          <div className="mt-3 flex flex-wrap gap-1.5">
            {PRESETS.map((p) => (
              <button
                key={p}
                onClick={() => setGoal(p)}
                className="text-[11px] px-2 py-1 rounded-full"
                style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}
              >
                {p.length > 30 ? p.slice(0, 30) + "..." : p}
              </button>
            ))}
          </div>

          <div className="mt-4">
            <label className="text-xs block mb-1" style={{ color: "var(--color-text-muted)" }}>
              追加 context (任意 — 参考資料 / 前提 / 出力フォーマット)
            </label>
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder=""
              className="w-full rounded-lg p-3 text-sm"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", minHeight: 60 }}
            />
          </div>

          <div className="mt-4 flex items-center gap-2 flex-wrap">
            <label className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              強制エンジン:
            </label>
            <button
              onClick={() => setForceEngine("")}
              className="text-xs px-2.5 py-1 rounded-full"
              style={{
                background: forceEngine === "" ? "#8b5cf6" : "var(--color-surface-hover)",
                color: forceEngine === "" ? "white" : "var(--color-text-muted)",
              }}
            >
              🎯 自動
            </button>
            {Object.entries(ENGINE_EMOJI).map(([en, emoji]) => (
              <button
                key={en}
                onClick={() => setForceEngine(en)}
                className="text-xs px-2.5 py-1 rounded-full"
                style={{
                  background: forceEngine === en ? "#8b5cf6" : "var(--color-surface-hover)",
                  color: forceEngine === en ? "white" : "var(--color-text-muted)",
                }}
              >
                {emoji} {en}
              </button>
            ))}
            <label className="ml-3 text-xs" style={{ color: "var(--color-text-muted)" }}>
              max tokens:
              <input
                type="number"
                value={maxTokens}
                onChange={(e) => setMaxTokens(Math.max(200, Math.min(8000, parseInt(e.target.value) || 2000)))}
                className="ml-2 w-20 px-2 py-1 rounded text-xs"
                style={{ background: "var(--color-surface-hover)", border: "1px solid var(--color-border)" }}
              />
            </label>
          </div>

          <div className="mt-5 flex items-center gap-2">
            <button
              onClick={doPreview}
              disabled={previewing || !goal.trim()}
              className="text-xs px-4 py-1.5 rounded-full disabled:opacity-50"
              style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}
            >
              {previewing ? "判定中..." : "🔍 エンジンだけ判定"}
            </button>
            <button
              onClick={run}
              disabled={loading || !goal.trim()}
              className="text-xs px-5 py-1.5 rounded-full disabled:opacity-50 ml-auto"
              style={{ background: "#8b5cf6", color: "white" }}
            >
              {loading ? "実行中..." : "🚀 実行"}
            </button>
          </div>

          {preview && !result && (
            <div className="mt-4 rounded-2xl p-4" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
              <p className="text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>
                ルーター判定 (preview)
              </p>
              <p className="text-sm font-semibold">
                {ENGINE_EMOJI[preview.engine] ?? ""} {preview.engine} ({preview.model})
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                理由: {preview.reason}
              </p>
            </div>
          )}

          {error && (
            <div className="mt-4 p-3 rounded-xl text-sm" style={{ background: "rgba(239, 68, 68, 0.08)", color: "var(--color-red)" }}>
              {error}
            </div>
          )}

          {result && (
            <div className="mt-5 rounded-2xl p-4" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
              <div className="flex items-center justify-between mb-2">
                <div>
                  <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                    実行エンジン
                  </p>
                  <p className="text-sm font-semibold">
                    {ENGINE_EMOJI[result.router.engine] ?? ""} {result.router.engine} ({result.router.model})
                  </p>
                  <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                    {result.router.reason} · {(result.latency_ms / 1000).toFixed(1)}s
                  </p>
                </div>
                <button
                  onClick={copy}
                  className="text-xs px-3 py-1 rounded-full"
                  style={{ background: copied ? "#10b981" : "var(--color-surface-hover)", color: copied ? "white" : "var(--color-text-muted)" }}
                >
                  {copied ? "✓ コピー済み" : "コピー"}
                </button>
              </div>
              <pre
                className="text-sm whitespace-pre-wrap p-3 rounded-lg mt-2"
                style={{ background: "var(--color-surface-hover)", border: "1px solid var(--color-border)", fontFamily: "inherit", lineHeight: 1.7 }}
              >
                {result.result}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
