"use client";

import { useState } from "react";

type Priority = "high" | "medium" | "low";

type Proposal = {
  title: string;
  description: string;
  priority: Priority;
  due_date: string | null;
  estimated_minutes: number | null;
  category: string;
};

type ExtractResponse = {
  proposals: Proposal[];
  extracted_chars: number;
  filename: string;
  engine_used: string;
  model_used: string;
};

const PRIORITY_COLOR: Record<Priority, string> = {
  high: "#ef4444",
  medium: "#eab308",
  low: "#71717a",
};

export default function DocumentsPage() {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [meta, setMeta] = useState<{ filename: string; chars: number; engine: string; model: string } | null>(null);
  const [accepted, setAccepted] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setError(null);
    setSuccess(null);
    setProposals([]);
    setAccepted(new Set());

    const fd = new FormData();
    fd.append("file", file);
    fd.append("engine", "gemini");

    try {
      const res = await fetch("/api/documents/extract-tasks", {
        method: "POST",
        body: fd,
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || `HTTP ${res.status}`);
      }
      const data = (await res.json()) as ExtractResponse;
      setProposals(data.proposals);
      setMeta({
        filename: data.filename,
        chars: data.extracted_chars,
        engine: data.engine_used,
        model: data.model_used,
      });
      // By default, accept all
      setAccepted(new Set(data.proposals.map((_, i) => i)));
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setLoading(false);
    }
  };

  const toggleAccept = (i: number) => {
    setAccepted((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  const handleCreate = async () => {
    const selected = proposals.filter((_, i) => accepted.has(i));
    if (selected.length === 0) return;
    try {
      const res = await fetch("/api/documents/create-tasks-batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ proposals: selected }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSuccess(`${data.count} 件のタスクを作成しました`);
      setProposals([]);
      setAccepted(new Set());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div
        className="px-8 pt-10 pb-6"
        style={{
          background:
            "radial-gradient(ellipse at top left, rgba(168, 85, 247, 0.10), transparent 50%)",
        }}
      >
        <div className="max-w-5xl mx-auto">
          <h1
            className="text-4xl font-bold tracking-tight"
            style={{
              background: "linear-gradient(90deg, #fafafa 0%, #c084fc 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Documents → Tasks
          </h1>
          <p className="mt-2 text-sm max-w-xl" style={{ color: "var(--color-text-muted)" }}>
            PDF / Word / Markdown / TXT をアップロード → Gemini が読んでタスク候補を抽出 → 必要なものだけ Tasks に追加
          </p>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-5xl mx-auto space-y-5">
          {/* Upload */}
          <div
            className="rounded-2xl p-6 border-2 border-dashed transition-colors"
            style={{
              background: "var(--color-surface)",
              borderColor: "var(--color-border-light)",
            }}
          >
            <label className="block text-center cursor-pointer">
              <input
                type="file"
                accept=".pdf,.docx,.txt,.md,.csv"
                onChange={handleUpload}
                disabled={loading}
                className="hidden"
              />
              <div className="text-3xl mb-2">📄</div>
              <div className="font-medium">
                {loading ? "解析中..." : "ファイルをドロップ or クリックして選択"}
              </div>
              <div className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                PDF / DOCX / TXT / Markdown (最大 10MB)
              </div>
            </label>
          </div>

          {meta && (
            <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {meta.filename} — {meta.chars.toLocaleString()} 文字解析 / {meta.engine} ({meta.model})
            </div>
          )}

          {error && (
            <div
              className="rounded-2xl p-4 text-sm"
              style={{
                background: "rgba(239, 68, 68, 0.08)",
                border: "1px solid var(--color-red)",
                color: "var(--color-red)",
              }}
            >
              {error}
            </div>
          )}

          {success && (
            <div
              className="rounded-2xl p-4 text-sm"
              style={{
                background: "rgba(34, 197, 94, 0.08)",
                border: "1px solid var(--color-green)",
                color: "var(--color-green)",
              }}
            >
              {success}
            </div>
          )}

          {/* Proposals */}
          {proposals.length > 0 && (
            <>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold">
                  {proposals.length} 件の候補 / {accepted.size} 件選択中
                </h2>
                <button
                  onClick={handleCreate}
                  disabled={accepted.size === 0}
                  className="px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50 transition-all hover:scale-[1.02]"
                  style={{
                    background: "var(--color-accent)",
                    color: "white",
                    boxShadow: "0 4px 14px rgba(59, 130, 246, 0.35)",
                  }}
                >
                  選択した {accepted.size} 件をタスクに追加
                </button>
              </div>

              <div className="space-y-2">
                {proposals.map((p, i) => {
                  const isAccepted = accepted.has(i);
                  return (
                    <div
                      key={i}
                      className="rounded-2xl p-4 transition-all cursor-pointer"
                      onClick={() => toggleAccept(i)}
                      style={{
                        background: "var(--color-surface)",
                        border: isAccepted
                          ? "1px solid var(--color-accent)"
                          : "1px solid var(--color-border)",
                        opacity: isAccepted ? 1 : 0.55,
                      }}
                    >
                      <div className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={isAccepted}
                          onChange={() => toggleAccept(i)}
                          onClick={(e) => e.stopPropagation()}
                          className="mt-1 shrink-0"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h3 className="font-medium">{p.title}</h3>
                            <span
                              className="text-[10px] font-medium px-2 py-0.5 rounded-full"
                              style={{
                                background: `${PRIORITY_COLOR[p.priority]}20`,
                                color: PRIORITY_COLOR[p.priority],
                              }}
                            >
                              {p.priority}
                            </span>
                            <span
                              className="text-[10px] px-2 py-0.5 rounded-full"
                              style={{
                                background: "var(--color-surface-hover)",
                                color: "var(--color-text-muted)",
                              }}
                            >
                              {p.category}
                            </span>
                          </div>
                          {p.description && (
                            <p
                              className="text-sm mt-1"
                              style={{ color: "var(--color-text-muted)" }}
                            >
                              {p.description}
                            </p>
                          )}
                          <div className="flex items-center gap-3 mt-1.5 text-xs" style={{ color: "var(--color-text-muted)" }}>
                            {p.due_date && <span>📅 {p.due_date}</span>}
                            {p.estimated_minutes && <span>⏱ {p.estimated_minutes}分</span>}
                          </div>
                        </div>
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
