"use client";

import { useEffect, useRef, useState } from "react";

type Entry = { role: "user" | "assistant"; content: string; timestamp: string };

export default function PrivatePage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
  const [entries, setEntries] = useState<Entry[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const loadHistory = async () => {
    try {
      const r = await fetch(`${apiBase}/api/private-chat/history?limit=100`);
      if (!r.ok) return;
      const d = await r.json();
      setEntries(d.entries ?? []);
    } catch {}
  };

  useEffect(() => {
    loadHistory();
  }, []);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [entries, loading]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const message = input.trim();
    setInput("");
    setLoading(true);
    setError(null);
    // Optimistic add user message
    const newUser: Entry = { role: "user", content: message, timestamp: new Date().toISOString() };
    setEntries((p) => [...p, newUser]);
    try {
      const r = await fetch(`${apiBase}/api/private-chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          history: entries.slice(-20),
        }),
      });
      if (!r.ok) throw new Error((await r.text()) || `HTTP ${r.status}`);
      const d = await r.json();
      setEntries((p) => [...p, { role: "assistant", content: d.reply, timestamp: new Date().toISOString() }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const clearAll = async () => {
    if (!confirm("ここの会話履歴を全て削除します。元に戻せません。よろしいですか？")) return;
    await fetch(`${apiBase}/api/private-chat/history`, { method: "DELETE" });
    setEntries([]);
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <div
        className="px-8 pt-10 pb-6 shrink-0"
        style={{
          background:
            "radial-gradient(ellipse at top left, rgba(168, 85, 247, 0.12), transparent 60%), radial-gradient(ellipse at top right, rgba(239, 68, 68, 0.08), transparent 50%)",
        }}
      >
        <div className="max-w-3xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            PRIVATE · VENICE UNCENSORED
          </p>
          <div className="flex items-end justify-between gap-3">
            <h1
              className="text-3xl font-bold tracking-tight"
              style={{
                background: "linear-gradient(135deg, #fafafa 0%, #f87171 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              プライベート相談室
            </h1>
            <button onClick={clearAll} className="text-xs underline" style={{ color: "var(--color-text-muted)" }}>
              履歴を全消去
            </button>
          </div>
          <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>
            他の AI に聞きにくいこと、判断に迷うこと、誰にも言えないことを、ジャッジなしで話せる場所。Venice (uncensored) が応答します。ログは通常チャットと分離。
          </p>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-8 py-6">
        <div className="max-w-3xl mx-auto space-y-4">
          {entries.length === 0 && (
            <div
              className="rounded-2xl p-8 text-center"
              style={{ background: "var(--color-surface)", border: "1px dashed var(--color-border)" }}
            >
              <p className="text-3xl mb-2">🤫</p>
              <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                何でも書いていい。整理したいこと、迷ってること、感情的なこと、人に言えないこと。
              </p>
            </div>
          )}
          {entries.map((e, i) => (
            <div key={i} className={`flex ${e.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className="max-w-[80%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap"
                style={{
                  background: e.role === "user" ? "var(--color-accent)" : "var(--color-surface)",
                  color: e.role === "user" ? "white" : "var(--color-text)",
                  border: e.role === "assistant" ? "1px solid var(--color-border)" : "none",
                  lineHeight: 1.6,
                }}
              >
                {e.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div
                className="rounded-2xl px-4 py-3 text-sm"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}
              >
                考え中…
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="shrink-0 px-8 pb-6">
        <div className="max-w-3xl mx-auto">
          {error && (
            <div
              className="mb-2 rounded-lg p-2 text-xs"
              style={{ background: "rgba(239, 68, 68, 0.08)", color: "var(--color-red)" }}
            >
              {error}
            </div>
          )}
          <div className="flex gap-2 items-end">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder="何でも書いて (⌘/Ctrl + Enter で送信)"
              rows={3}
              className="flex-1 px-4 py-3 rounded-xl text-sm resize-none"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
              }}
            />
            <button
              onClick={send}
              disabled={loading || !input.trim()}
              className="px-5 py-3 rounded-xl text-sm font-medium disabled:opacity-50"
              style={{ background: "var(--color-accent)", color: "white" }}
            >
              {loading ? "..." : "送信"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
