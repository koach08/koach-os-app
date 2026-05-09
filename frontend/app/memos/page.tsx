"use client";

import { useEffect, useState } from "react";

type Color = "yellow" | "blue" | "green" | "pink";

type Memo = {
  id: string;
  content: string;
  color: Color;
  pinned: boolean;
  created_at: string;
  updated_at: string;
};

const COLOR_STYLES: Record<Color, { bg: string; border: string; dot: string }> = {
  yellow: { bg: "rgba(234, 179, 8, 0.15)", border: "rgba(234, 179, 8, 0.5)", dot: "#eab308" },
  blue: { bg: "rgba(59, 130, 246, 0.15)", border: "rgba(59, 130, 246, 0.5)", dot: "#3b82f6" },
  green: { bg: "rgba(34, 197, 94, 0.15)", border: "rgba(34, 197, 94, 0.5)", dot: "#22c55e" },
  pink: { bg: "rgba(236, 72, 153, 0.15)", border: "rgba(236, 72, 153, 0.5)", dot: "#ec4899" },
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("ja-JP", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function MemosPage() {
  const [memos, setMemos] = useState<Memo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [selectedColor, setSelectedColor] = useState<Color>("yellow");

  const load = () => {
    setLoading(true);
    setError(null);
    fetch("/api/memos")
      .then((r) => r.json())
      .then((d) => setMemos(d.memos ?? []))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const handleAdd = async () => {
    if (!input.trim()) return;
    try {
      await fetch("/api/memos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: input, color: selectedColor }),
      });
      setInput("");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleTogglePin = async (m: Memo) => {
    try {
      await fetch(`/api/memos/${m.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pinned: !m.pinned }),
      });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("メモを削除しますか？")) return;
    try {
      await fetch(`/api/memos/${id}`, { method: "DELETE" });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleColorChange = async (m: Memo, color: Color) => {
    try {
      await fetch(`/api/memos/${m.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ color }),
      });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Hero */}
      <div
        className="px-8 pt-10 pb-6"
        style={{
          background:
            "radial-gradient(ellipse at top right, rgba(234, 179, 8, 0.10), transparent 50%)",
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
            Memos
          </h1>
          <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>
            付箋風のクイックメモ。色で分類、ピン留めで上に固定
          </p>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-5xl mx-auto space-y-6">
          {/* Input */}
          <div
            className="rounded-2xl p-4"
            style={{
              background: COLOR_STYLES[selectedColor].bg,
              border: `1px solid ${COLOR_STYLES[selectedColor].border}`,
            }}
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="メモを書く..."
              rows={3}
              className="w-full px-3 py-2 rounded-lg text-sm resize-none"
              style={{
                background: "var(--color-background)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
              }}
            />
            <div className="flex items-center justify-between mt-3">
              <div className="flex gap-2">
                {(Object.keys(COLOR_STYLES) as Color[]).map((c) => (
                  <button
                    key={c}
                    onClick={() => setSelectedColor(c)}
                    className="w-6 h-6 rounded-full transition-all"
                    style={{
                      background: COLOR_STYLES[c].dot,
                      transform: selectedColor === c ? "scale(1.2)" : "scale(1)",
                      boxShadow: selectedColor === c ? "0 0 0 2px var(--color-text)" : "none",
                    }}
                    title={c}
                  />
                ))}
              </div>
              <button
                onClick={handleAdd}
                disabled={!input.trim()}
                className="px-5 py-1.5 rounded-full text-sm font-medium disabled:opacity-50 transition-all hover:scale-[1.02]"
                style={{ background: "var(--color-text)", color: "var(--color-background)" }}
              >
                追加
              </button>
            </div>
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

          {/* Memo grid */}
          {loading ? (
            <div className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              読み込み中...
            </div>
          ) : memos.length === 0 ? (
            <div
              className="rounded-2xl p-10 text-center"
              style={{ background: "var(--color-surface)", border: "1px dashed var(--color-border-light)" }}
            >
              <p className="text-3xl mb-2">🪧</p>
              <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                まだメモはありません
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {memos.map((m) => {
                const cs = COLOR_STYLES[m.color];
                return (
                  <div
                    key={m.id}
                    className="rounded-xl p-4 relative transition-all hover:translate-y-[-2px]"
                    style={{
                      background: cs.bg,
                      border: `1px solid ${cs.border}`,
                      minHeight: "120px",
                    }}
                  >
                    {m.pinned && (
                      <div
                        className="absolute top-2 right-2 w-2 h-2 rounded-full"
                        style={{ background: cs.dot }}
                      />
                    )}
                    <p className="text-sm whitespace-pre-wrap" style={{ color: "var(--color-text)" }}>
                      {m.content}
                    </p>
                    <div
                      className="flex items-center justify-between mt-3 pt-2 text-[10px]"
                      style={{
                        color: "var(--color-text-muted)",
                        borderTop: `1px solid ${cs.border}`,
                      }}
                    >
                      <span>{formatDate(m.created_at)}</span>
                      <div className="flex gap-1">
                        <button
                          onClick={() => handleTogglePin(m)}
                          className="px-1.5 py-0.5 rounded hover:bg-black/10"
                          title={m.pinned ? "ピン解除" : "ピン留め"}
                        >
                          {m.pinned ? "📌" : "📍"}
                        </button>
                        <select
                          value={m.color}
                          onChange={(e) => handleColorChange(m, e.target.value as Color)}
                          className="text-[10px] rounded"
                          style={{ background: "transparent", border: "none", color: "var(--color-text-muted)" }}
                          title="色変更"
                        >
                          {(Object.keys(COLOR_STYLES) as Color[]).map((c) => (
                            <option key={c} value={c}>
                              {c}
                            </option>
                          ))}
                        </select>
                        <button
                          onClick={() => handleDelete(m.id)}
                          className="px-1.5 py-0.5 rounded hover:bg-black/10"
                          title="削除"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
