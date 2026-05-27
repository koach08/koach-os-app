"use client";

import { useEffect, useRef, useState } from "react";

type Attachment = { file_id: string; filename: string; mime: string; size_bytes: number };
type ChatMsg = { role: "user" | "assistant"; content: string; attachments?: Attachment[]; steps?: Step[] };
type Step = { type: "thought" | "tool"; content?: string; tool_name?: string; tool_input?: Record<string, unknown>; tool_result?: string };

const TOOL_EMOJI: Record<string, string> = {
  web_search: "🔍",
  web_fetch: "🌐",
  analyze_image: "🖼",
  analyze_pdf: "📄",
  analyze_video_url: "🎬",
  analyze_audio: "🎙",
  search_my_data: "🧠",
  list_calendar: "📅",
  create_event: "➕📅",
  add_backlog: "➕📋",
  save_memo: "💾🪧",
  save_decision: "💾🧭",
  tts_speak: "🔊",
};

export default function AgentPage() {
  const [history, setHistory] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, loading]);

  const upload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      for (const f of Array.from(files)) {
        const fd = new FormData();
        fd.append("file", f);
        const r = await fetch("/api/agent/upload", { method: "POST", body: fd });
        if (!r.ok) throw new Error(`upload ${r.status}`);
        const d = await r.json();
        setAttachments((prev) => [...prev, d]);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const send = async () => {
    if (!input.trim() && attachments.length === 0) return;
    if (loading) return;
    const userMsg: ChatMsg = { role: "user", content: input, attachments: [...attachments] };
    const next = [...history, userMsg];
    setHistory(next);
    setInput("");
    setAttachments([]);
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/agent/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMsg.content,
          history: history.map((h) => ({ role: h.role, content: h.content })),
          attachments: userMsg.attachments,
        }),
      });
      if (!r.ok) {
        const t = await r.text();
        throw new Error(t);
      }
      const d = await r.json();
      setHistory([...next, { role: "assistant", content: d.final || "(空回答)", steps: d.steps ?? [] }]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const removeAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((a) => a.file_id !== id));
  };

  const clearHistory = () => {
    if (!confirm("会話履歴をクリアしますか?")) return;
    setHistory([]);
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div
        className="px-8 pt-8 pb-4 shrink-0"
        style={{
          background:
            "radial-gradient(ellipse at top left, rgba(16, 185, 129, 0.12), transparent 60%), radial-gradient(ellipse at top right, rgba(168, 85, 247, 0.06), transparent 50%)",
        }}
      >
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-widest mb-1" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
              Koach Agent
            </p>
            <h1 className="text-2xl font-bold tracking-tight">エージェント (tool calling)</h1>
            <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
              Web / 自分のデータ / Calendar / 画像・PDF・動画・音声を Claude が組み合わせて回答
            </p>
          </div>
          {history.length > 0 && (
            <button
              onClick={clearHistory}
              className="text-xs px-3 py-1.5 rounded-full"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}
            >
              履歴クリア
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-8 py-4">
        <div className="max-w-4xl mx-auto space-y-4">
          {history.length === 0 && (
            <div
              className="rounded-2xl p-6 text-sm space-y-3"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}
            >
              <p style={{ color: "var(--color-text)" }} className="font-semibold">
                試してみる質問例:
              </p>
              <ul className="space-y-1.5">
                <li>• 「来週の科研費締切を調べて Calendar に入れて」 — web_search + create_event</li>
                <li>• 「先月の自分の決定で「EGAKU」関連を全部出して」 — search_my_data</li>
                <li>• [画像 drop] 「このホワイトボード写真の内容を memo に保存して」 — analyze_image + save_memo</li>
                <li>• [PDF drop] 「この規程の重要箇所 5 つ + アクションを backlog に入れて」 — analyze_pdf + add_backlog</li>
                <li>• 「明日の Daily Brief を音声化して」 — list_calendar + tts_speak</li>
              </ul>
              <p className="pt-2" style={{ borderTop: "1px solid var(--color-border)" }}>
                ⬇ 下のバーから入力 + ファイル添付 (画像 / PDF / 音声 / 動画) 可能
              </p>
            </div>
          )}

          {history.map((m, i) => (
            <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
              {m.role === "user" ? (
                <div
                  className="rounded-2xl p-3 max-w-[80%]"
                  style={{ background: "var(--color-accent)", color: "white" }}
                >
                  <div className="text-sm whitespace-pre-wrap">{m.content}</div>
                  {m.attachments && m.attachments.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {m.attachments.map((a) => (
                        <span key={a.file_id} className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: "rgba(255,255,255,0.15)" }}>
                          📎 {a.filename}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-2">
                  {m.steps && m.steps.length > 0 && (
                    <details
                      className="rounded-xl p-3 text-xs"
                      style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
                    >
                      <summary className="cursor-pointer" style={{ color: "var(--color-text-muted)" }}>
                        🔧 {m.steps.length} ステップ (思考 + 道具)
                      </summary>
                      <div className="mt-3 space-y-2">
                        {m.steps.map((s, si) => (
                          <div key={si}>
                            {s.type === "thought" && (
                              <div className="px-2 py-1.5 rounded text-[12px]" style={{ background: "var(--color-background)", color: "var(--color-text-muted)" }}>
                                💭 {s.content}
                              </div>
                            )}
                            {s.type === "tool" && (
                              <div className="px-2 py-1.5 rounded text-[12px]" style={{ background: "rgba(16, 185, 129, 0.05)", border: "1px solid rgba(16, 185, 129, 0.2)" }}>
                                <div className="font-semibold mb-1">
                                  {TOOL_EMOJI[s.tool_name ?? ""] ?? "🔧"} {s.tool_name}
                                </div>
                                <div className="font-mono text-[11px] mb-1 opacity-70">
                                  {JSON.stringify(s.tool_input).slice(0, 200)}
                                </div>
                                <div className="whitespace-pre-wrap text-[11px] opacity-80" style={{ maxHeight: "200px", overflowY: "auto" }}>
                                  {s.tool_result}
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                  <div
                    className="rounded-2xl p-4 text-sm whitespace-pre-wrap leading-relaxed"
                    style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
                  >
                    {m.content}
                  </div>
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div
              className="rounded-2xl p-3 text-sm flex items-center gap-2"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}
            >
              <span className="animate-pulse">●●●</span> エージェントが考え中... (道具を使うと 30〜60 秒かかる場合あり)
            </div>
          )}

          {error && (
            <div className="rounded-xl p-3 text-sm" style={{ background: "rgba(239, 68, 68, 0.08)", color: "var(--color-red)" }}>
              {error}
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      <div className="shrink-0 px-4 pb-4 md:pb-6">
        <div className="max-w-4xl mx-auto">
          {attachments.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-1.5">
              {attachments.map((a) => (
                <span
                  key={a.file_id}
                  className="text-[11px] px-2 py-1 rounded-full flex items-center gap-2"
                  style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
                >
                  📎 {a.filename}
                  <button onClick={() => removeAttachment(a.file_id)} style={{ color: "var(--color-text-muted)" }}>
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}

          <div
            className="rounded-2xl p-2 flex items-end gap-2"
            style={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              boxShadow: "0 8px 30px rgba(0,0,0,0.3)",
            }}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              upload(e.dataTransfer.files);
            }}
          >
            <input
              ref={fileRef}
              type="file"
              multiple
              hidden
              accept="image/*,application/pdf,audio/*,video/*"
              onChange={(e) => upload(e.target.files)}
            />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading || loading}
              title="ファイル添付"
              className="shrink-0 w-9 h-9 rounded-xl flex items-center justify-center disabled:opacity-50"
              style={{ background: "var(--color-surface-hover)", color: "var(--color-text)" }}
            >
              {uploading ? "…" : "📎"}
            </button>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  send();
                }
              }}
              rows={1}
              placeholder="質問・指示 / Enter で送信 / Shift+Enter 改行 / ファイル D&D 可"
              disabled={loading}
              className="flex-1 px-3 py-2 text-sm resize-none bg-transparent outline-none disabled:opacity-50"
              style={{ color: "var(--color-text)", maxHeight: "200px", minHeight: "36px" }}
            />
            <button
              onClick={send}
              disabled={loading || (!input.trim() && attachments.length === 0)}
              className="shrink-0 w-9 h-9 rounded-xl flex items-center justify-center disabled:opacity-30"
              style={{ background: input.trim() || attachments.length > 0 ? "var(--color-accent)" : "var(--color-surface-hover)", color: input.trim() || attachments.length > 0 ? "white" : "var(--color-text-muted)" }}
            >
              {loading ? "…" : "↑"}
            </button>
          </div>
          <div className="mt-1.5 text-[10px] text-center" style={{ color: "var(--color-text-muted)" }}>
            ファイル D&D で画像 / PDF / 音声 / 動画を添付
          </div>
        </div>
      </div>
    </div>
  );
}
