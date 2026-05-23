"use client";

import { useState } from "react";

type DispatchResult = {
  goal: string;
  brief: string;
  engine_used: string;
  generated_at: string;
};

const PRESETS = [
  "論文 introduction の骨子を作る",
  "EGAKU AI の LP コピーを志柿スタイルで書く",
  "WordPress 記事をリッチHTMLで書き起こす",
  "ブレイクダンス再開のための4週間トレーニング計画",
  "Pixiv 投稿用キャラ設定とプロンプト案",
  "科研費基盤C 再申請の研究計画 1.2 万字",
];

export default function DispatcherPage() {
  const [goal, setGoal] = useState("");
  const [constraints, setConstraints] = useState("");
  const [inputs, setInputs] = useState("");
  const [engine, setEngine] = useState("claude");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DispatchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const run = async () => {
    if (!goal.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await fetch("/api/dispatcher", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal, constraints, inputs_available: inputs, engine }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setResult(await r.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const copy = () => {
    if (!result) return;
    navigator.clipboard.writeText(result.brief);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="px-8 pt-12 pb-8" style={{ background: "radial-gradient(ellipse at top, rgba(245, 158, 11, 0.12), transparent 60%)" }}>
        <div className="max-w-4xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            AI Dispatcher
          </p>
          <h1 className="text-4xl font-bold tracking-tight">どの AI に頼むか</h1>
          <p className="mt-3 text-sm" style={{ color: "var(--color-text-muted)" }}>
            目的を渡すと推奨 AI サービスと貼り付け用プロンプトを返します。
          </p>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-4xl mx-auto space-y-6">
          <div
            className="rounded-2xl p-6 space-y-4"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
          >
            <div>
              <label className="block text-xs mb-1.5 uppercase tracking-wider" style={{ color: "var(--color-text-muted)" }}>
                目的
              </label>
              <textarea
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                rows={3}
                placeholder="例: 科研費基盤C 再申請の研究目的セクション 800字"
                className="w-full px-4 py-2.5 rounded-lg text-sm"
                style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
              />
              <div className="mt-2 flex flex-wrap gap-1.5">
                {PRESETS.map((p) => (
                  <button
                    key={p}
                    onClick={() => setGoal(p)}
                    className="text-[11px] px-2.5 py-1 rounded-full"
                    style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs mb-1.5 uppercase tracking-wider" style={{ color: "var(--color-text-muted)" }}>
                  制約
                </label>
                <input
                  value={constraints}
                  onChange={(e) => setConstraints(e.target.value)}
                  placeholder="無料で / 日本語 / 学術文体"
                  className="w-full px-4 py-2 rounded-lg text-sm"
                  style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                />
              </div>
              <div>
                <label className="block text-xs mb-1.5 uppercase tracking-wider" style={{ color: "var(--color-text-muted)" }}>
                  持っている素材
                </label>
                <input
                  value={inputs}
                  onChange={(e) => setInputs(e.target.value)}
                  placeholder="前回不採択の申請書 PDF など"
                  className="w-full px-4 py-2 rounded-lg text-sm"
                  style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                />
              </div>
            </div>
            <div className="flex items-center gap-3">
              <select
                value={engine}
                onChange={(e) => setEngine(e.target.value)}
                className="px-3 py-2 rounded text-sm"
                style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
              >
                <option value="claude">Claude (推論)</option>
                <option value="gpt">GPT</option>
                <option value="gemini">Gemini</option>
              </select>
              <button
                onClick={run}
                disabled={loading || !goal.trim()}
                className="px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50"
                style={{ background: "#f59e0b", color: "white" }}
              >
                {loading ? "生成中..." : "外注指示書を作る"}
              </button>
            </div>
          </div>

          {error && (
            <div className="p-4 rounded-2xl text-sm" style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid var(--color-red)", color: "var(--color-red)" }}>
              {error}
            </div>
          )}

          {result && (
            <div
              className="rounded-2xl p-6"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "#f59e0b" }}>
                  指示書 ({result.engine_used})
                </span>
                <button
                  onClick={copy}
                  className="text-xs px-3 py-1 rounded-full"
                  style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}
                >
                  {copied ? "✓ コピー完了" : "全文コピー"}
                </button>
              </div>
              <pre className="text-sm whitespace-pre-wrap leading-[1.75]" style={{ color: "var(--color-text)" }}>
                {result.brief}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
