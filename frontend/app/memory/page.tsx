"use client";

import { useEffect, useState } from "react";

type Tab = "decisions" | "failures" | "voice" | "feedback" | "experiences" | "heuristics";

const TABS: { key: Tab; label: string; emoji: string }[] = [
  { key: "decisions", label: "Decisions", emoji: "🧭" },
  { key: "failures", label: "Failures", emoji: "🪨" },
  { key: "voice", label: "Voice", emoji: "🎙" },
  { key: "feedback", label: "Feedback", emoji: "🪞" },
  { key: "experiences", label: "Experiences", emoji: "📚" },
  { key: "heuristics", label: "Heuristics", emoji: "📐" },
];

type Entry = Record<string, unknown>;

function fieldLabel(key: string): string {
  return key.replaceAll("_", " ");
}

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (Array.isArray(v)) return v.length ? v.map(String).join(", ") : "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function formatTimestamp(ts: unknown): string {
  if (typeof ts !== "string") return "";
  try {
    return new Date(ts).toLocaleString("ja-JP", {
      year: "numeric",
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

export default function MemoryPage() {
  const [activeTab, setActiveTab] = useState<Tab>("decisions");
  const [data, setData] = useState<Entry[] | Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setData(null);
    fetch(`/api/memory/${activeTab}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((json) => {
        if (activeTab === "heuristics") {
          setData(json);
        } else {
          setData(json.entries ?? []);
        }
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [activeTab]);

  const entries = Array.isArray(data) ? data : null;
  const heuristics = !Array.isArray(data) && data !== null ? data : null;

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Hero header */}
      <div
        className="px-8 pt-10 pb-6"
        style={{
          background:
            "linear-gradient(180deg, rgba(59, 130, 246, 0.08) 0%, transparent 100%)",
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
            Memory
          </h1>
          <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>
            意思決定 / 失敗 / 声 / フィードバック / 経験 / ヒューリスティクス
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="px-8 sticky top-0 z-10" style={{ background: "var(--color-background)" }}>
        <div className="max-w-5xl mx-auto flex gap-1 overflow-x-auto" style={{ borderBottom: "1px solid var(--color-border)" }}>
          {TABS.map((t) => {
            const active = activeTab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                className="px-4 py-3 text-sm whitespace-nowrap transition-all relative"
                style={{
                  color: active ? "var(--color-text)" : "var(--color-text-muted)",
                  fontWeight: active ? 600 : 400,
                }}
              >
                <span className="mr-1.5">{t.emoji}</span>
                {t.label}
                {active && (
                  <span
                    className="absolute left-2 right-2 -bottom-px h-0.5 rounded-full"
                    style={{ background: "var(--color-accent)" }}
                  />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <div className="px-8 py-8">
        <div className="max-w-5xl mx-auto">
          {loading && (
            <div className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              読み込み中...
            </div>
          )}
          {error && (
            <div
              className="p-4 rounded-xl text-sm"
              style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid var(--color-red)", color: "var(--color-red)" }}
            >
              読み込み失敗: {error}
            </div>
          )}

          {/* Heuristics — YAML object */}
          {!loading && !error && heuristics && (
            <div className="rounded-2xl p-6" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
              {Object.keys(heuristics).length === 0 ? (
                <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                  まだヒューリスティクスは登録されていません
                </p>
              ) : (
                <pre
                  className="text-xs font-mono whitespace-pre-wrap"
                  style={{ color: "var(--color-text)" }}
                >
                  {JSON.stringify(heuristics, null, 2)}
                </pre>
              )}
            </div>
          )}

          {/* Entries — JSONL list */}
          {!loading && !error && entries && (
            <>
              {entries.length === 0 ? (
                <div className="rounded-2xl p-10 text-center" style={{ background: "var(--color-surface)", border: "1px dashed var(--color-border-light)" }}>
                  <p className="text-2xl mb-2">📭</p>
                  <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                    まだ {TABS.find((t) => t.key === activeTab)?.label} は登録されていません
                  </p>
                  <p className="text-xs mt-2" style={{ color: "var(--color-text-muted)" }}>
                    Chat 画面から会話を続けると自動的に蓄積されます
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {[...entries].reverse().map((entry, i) => {
                    const id = (entry.id as string) ?? `entry-${i}`;
                    const ts = entry.timestamp;
                    const fields = Object.entries(entry).filter(
                      ([k]) => !["id", "timestamp"].includes(k)
                    );
                    const primaryField = fields.find(([k]) =>
                      ["title", "what_happened", "what", "observation", "lesson", "pattern"].includes(k)
                    );
                    return (
                      <div
                        key={id}
                        className="rounded-2xl p-5 transition-all hover:translate-y-[-1px]"
                        style={{
                          background: "var(--color-surface)",
                          border: "1px solid var(--color-border)",
                        }}
                      >
                        {primaryField && (
                          <h3 className="font-semibold mb-2 text-base">
                            {formatValue(primaryField[1])}
                          </h3>
                        )}
                        <dl className="space-y-1.5">
                          {fields
                            .filter(([k]) => k !== primaryField?.[0])
                            .map(([k, v]) => (
                              <div key={k} className="flex gap-3 text-sm">
                                <dt
                                  className="capitalize shrink-0"
                                  style={{ color: "var(--color-text-muted)", minWidth: "5.5rem" }}
                                >
                                  {fieldLabel(k)}
                                </dt>
                                <dd className="flex-1" style={{ color: "var(--color-text)" }}>
                                  {formatValue(v)}
                                </dd>
                              </div>
                            ))}
                        </dl>
                        {Boolean(ts) && (
                          <div
                            className="text-xs mt-3 pt-3"
                            style={{
                              color: "var(--color-text-muted)",
                              borderTop: "1px solid var(--color-border)",
                            }}
                          >
                            {formatTimestamp(ts)}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
