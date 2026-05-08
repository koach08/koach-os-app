"use client";

import { useEffect, useState } from "react";
import { fetchJSON } from "@/lib/api";

interface Settings {
  models: Record<string, string>;
  available_models: Record<string, [string, string][]>;
  has_keys: Record<string, boolean>;
  has_anthropic_key: boolean;
  has_openai_key: boolean;
}

const ENGINE_META: Record<string, { label: string; emoji: string; role: string }> = {
  claude: { label: "Claude", emoji: "🧠", role: "思考・戦略・振り返り" },
  gpt: { label: "GPT", emoji: "🤖", role: "実行・コード・要約" },
  grok: { label: "Grok", emoji: "🌀", role: "推論・代替" },
  gemini: { label: "Gemini", emoji: "✨", role: "長文・PDF・Gmail解析" },
  venice: { label: "Venice", emoji: "🎭", role: "制約なし対話" },
  perplexity: { label: "Perplexity", emoji: "🔍", role: "Web検索付き応答" },
  groq: { label: "Groq", emoji: "⚡", role: "爆速単発クエリ" },
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);

  useEffect(() => {
    fetchJSON<Settings>("/api/settings").then(setSettings).catch(() => {});
  }, []);

  const handleExport = () => {
    window.open("/api/settings/export", "_blank");
  };

  const handleOpenClaudeCode = async () => {
    try {
      await fetch("/api/settings/open-claude-code", { method: "POST" });
    } catch {
      alert("Claude Codeの起動に失敗しました。ターミナルで claude コマンドを実行してください。");
    }
  };

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Hero */}
      <div
        className="px-8 pt-10 pb-6"
        style={{
          background:
            "linear-gradient(180deg, rgba(168, 85, 247, 0.06) 0%, transparent 100%)",
        }}
      >
        <div className="max-w-4xl mx-auto">
          <h1
            className="text-4xl font-bold tracking-tight"
            style={{
              background: "linear-gradient(90deg, #fafafa 0%, #a1a1aa 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Settings
          </h1>
          <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>
            7 エンジン / API キー / データエクスポート
          </p>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-4xl mx-auto space-y-6">
          {!settings && (
            <div className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              読み込み中...
            </div>
          )}

          {settings && (
            <>
              {/* Engines grid */}
              <section>
                <h2 className="font-semibold mb-3 flex items-center gap-2">
                  <span>🧬</span>
                  <span>AI Engines</span>
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {Object.entries(settings.has_keys).map(([engine, hasKey]) => {
                    const meta = ENGINE_META[engine];
                    const currentModel = settings.models[engine];
                    return (
                      <div
                        key={engine}
                        className="rounded-2xl p-4 transition-all"
                        style={{
                          background: "var(--color-surface)",
                          border: hasKey
                            ? "1px solid var(--color-border)"
                            : "1px dashed var(--color-border-light)",
                          opacity: hasKey ? 1 : 0.55,
                        }}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xl">{meta?.emoji ?? "🔌"}</span>
                            <div>
                              <div className="font-semibold text-sm">{meta?.label ?? engine}</div>
                              <div
                                className="text-xs"
                                style={{ color: "var(--color-text-muted)" }}
                              >
                                {meta?.role ?? "—"}
                              </div>
                            </div>
                          </div>
                          <span
                            className="text-[10px] px-2 py-0.5 rounded-full font-medium"
                            style={{
                              background: hasKey ? "rgba(34, 197, 94, 0.12)" : "rgba(239, 68, 68, 0.12)",
                              color: hasKey ? "#22c55e" : "#ef4444",
                            }}
                          >
                            {hasKey ? "Connected" : "No Key"}
                          </span>
                        </div>
                        {currentModel && (
                          <div
                            className="mt-2 pt-2 text-xs font-mono"
                            style={{
                              color: "var(--color-text-muted)",
                              borderTop: "1px solid var(--color-border)",
                            }}
                          >
                            default: {currentModel}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>

              {/* Available models */}
              <section className="rounded-2xl p-6" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
                <h2 className="font-semibold mb-4 flex items-center gap-2">
                  <span>📚</span>
                  <span>Available Models</span>
                </h2>
                <div className="space-y-5">
                  {Object.entries(settings.available_models).map(([engine, models]) => (
                    <div key={engine}>
                      <h3
                        className="text-xs uppercase tracking-wider mb-2"
                        style={{ color: "var(--color-text-muted)", letterSpacing: "0.1em" }}
                      >
                        {ENGINE_META[engine]?.emoji} {ENGINE_META[engine]?.label ?? engine}
                      </h3>
                      <div className="space-y-1">
                        {models.map(([id, label]) => (
                          <div
                            key={id}
                            className="flex items-center justify-between text-sm py-1.5 px-3 rounded-lg"
                            style={{
                              background:
                                settings.models[engine] === id
                                  ? "rgba(59, 130, 246, 0.08)"
                                  : "transparent",
                            }}
                          >
                            <span>{label}</span>
                            <span
                              className="text-xs font-mono"
                              style={{ color: "var(--color-text-muted)" }}
                            >
                              {id}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              {/* Auto routing info */}
              <section
                className="rounded-2xl p-6"
                style={{
                  background:
                    "linear-gradient(135deg, rgba(34, 197, 94, 0.08) 0%, transparent 100%)",
                  border: "1px solid var(--color-border)",
                }}
              >
                <h2 className="font-semibold mb-3 flex items-center gap-2">
                  <span>🔀</span>
                  <span>Auto Routing</span>
                </h2>
                <p className="text-sm mb-3" style={{ color: "var(--color-text-muted)" }}>
                  入力内容に応じてエンジンが自動選択されます。各ページの selector で手動上書き可。
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                  {[
                    ["決定・戦略・振り返り", "Claude"],
                    ["コード・要約・実行", "GPT"],
                    ["最新情報・Web検索", "Perplexity"],
                    ["長文PDF・Gmail解析", "Gemini"],
                    ["爆速・即答が欲しい", "Groq"],
                    ["制約なし・本音", "Venice"],
                  ].map(([trigger, engine]) => (
                    <div
                      key={trigger}
                      className="flex justify-between py-1.5 px-3 rounded-lg"
                      style={{ background: "rgba(255,255,255,0.02)" }}
                    >
                      <span style={{ color: "var(--color-text-muted)" }}>{trigger}</span>
                      <span className="font-medium">→ {engine}</span>
                    </div>
                  ))}
                </div>
              </section>

              {/* Developer tools */}
              <section className="rounded-2xl p-6" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
                <h2 className="font-semibold mb-3 flex items-center gap-2">
                  <span>🔧</span>
                  <span>Developer Tools</span>
                </h2>
                <p className="text-sm mb-3" style={{ color: "var(--color-text-muted)" }}>
                  Claude Code でこのアプリの機能追加・修正ができます。
                </p>
                <button
                  onClick={handleOpenClaudeCode}
                  className="px-4 py-2 rounded-lg text-sm font-medium transition-all hover:scale-[1.02]"
                  style={{ background: "#d97706", color: "white" }}
                >
                  Claude Code を開く
                </button>
              </section>

              {/* Export */}
              <section className="rounded-2xl p-6" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
                <h2 className="font-semibold mb-3 flex items-center gap-2">
                  <span>💾</span>
                  <span>Data Export</span>
                </h2>
                <p className="text-sm mb-3" style={{ color: "var(--color-text-muted)" }}>
                  全 interaction logs / memory / decisions を ZIP でダウンロード。
                </p>
                <button
                  onClick={handleExport}
                  className="px-4 py-2 rounded-lg text-sm font-medium transition-all hover:scale-[1.02]"
                  style={{ background: "var(--color-accent)", color: "white" }}
                >
                  Export All Data
                </button>
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
