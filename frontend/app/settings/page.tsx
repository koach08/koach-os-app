"use client";

import { useState, useEffect } from "react";
import { fetchJSON } from "@/lib/api";

interface Settings {
  models: Record<string, string>;
  available_models: Record<string, [string, string][]>;
  has_anthropic_key: boolean;
  has_openai_key: boolean;
}

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
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold mb-6">Settings</h1>

        {settings && (
          <div className="space-y-6">
            {/* API Status */}
            <div className="p-5 rounded-xl" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
              <h3 className="font-semibold mb-3">API Keys</h3>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm">Anthropic (Claude)</span>
                  <span className="text-xs px-2 py-1 rounded-full" style={{
                    background: settings.has_anthropic_key ? "#22c55e20" : "#ef444420",
                    color: settings.has_anthropic_key ? "#22c55e" : "#ef4444",
                  }}>
                    {settings.has_anthropic_key ? "Connected" : "Not Set"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">OpenAI (GPT)</span>
                  <span className="text-xs px-2 py-1 rounded-full" style={{
                    background: settings.has_openai_key ? "#22c55e20" : "#ef444420",
                    color: settings.has_openai_key ? "#22c55e" : "#ef4444",
                  }}>
                    {settings.has_openai_key ? "Connected" : "Not Set"}
                  </span>
                </div>
              </div>
            </div>

            {/* Current Models */}
            <div className="p-5 rounded-xl" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
              <h3 className="font-semibold mb-3">Active Models</h3>
              <div className="space-y-2">
                {Object.entries(settings.models).map(([engine, model]) => (
                  <div key={engine} className="flex items-center justify-between">
                    <span className="text-sm capitalize">{engine}</span>
                    <span className="text-xs font-mono px-2 py-1 rounded" style={{ background: "var(--color-background)" }}>
                      {model}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Available Models */}
            <div className="p-5 rounded-xl" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
              <h3 className="font-semibold mb-3">Available Models</h3>
              {Object.entries(settings.available_models).map(([engine, models]) => (
                <div key={engine} className="mb-3">
                  <h4 className="text-sm font-medium capitalize mb-2" style={{ color: "var(--color-text-muted)" }}>{engine}</h4>
                  <div className="space-y-1">
                    {models.map(([id, label]) => (
                      <div key={id} className="flex items-center justify-between text-sm py-1">
                        <span>{label}</span>
                        <span className="text-xs font-mono" style={{ color: "var(--color-text-muted)" }}>{id}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Developer Tools */}
            <div className="p-5 rounded-xl" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
              <h3 className="font-semibold mb-3">Developer Tools</h3>
              <p className="text-sm mb-3" style={{ color: "var(--color-text-muted)" }}>
                Claude Codeを起動して、Koach OSの機能追加・修正を行えます。
              </p>
              <button
                onClick={handleOpenClaudeCode}
                className="px-4 py-2 rounded-lg text-sm font-medium"
                style={{ background: "#d97706", color: "white" }}
              >
                Claude Code を開く
              </button>
            </div>

            {/* Export */}
            <div className="p-5 rounded-xl" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
              <h3 className="font-semibold mb-3">Data Export</h3>
              <p className="text-sm mb-3" style={{ color: "var(--color-text-muted)" }}>
                Download all interaction logs, memory, and settings as a ZIP file.
              </p>
              <button
                onClick={handleExport}
                className="px-4 py-2 rounded-lg text-sm font-medium"
                style={{ background: "var(--color-accent)", color: "white" }}
              >
                Export All Data
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
