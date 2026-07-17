"use client";

/**
 * BriefChat — Worklog Phase B-2「brief の対話化」レイヤー (追加のみ)
 *
 * 既存の一発ブリーフ (/daily /evening) はそのまま。その下に折りたたみで差し込む。
 * - 「昨日 / 直近やっていたこと → 今日は?」の連続性を先頭に出す (GET /api/brief/continuity)
 * - 「それは無理」「並べ替えて」と返すと AI が組み直す (POST /api/brief/chat)
 * - 返答は忖度しない二段生成 (生成 → 褒め/煽り削り) を通ってくる
 */

import { useState } from "react";

type Msg = { role: "user" | "assistant"; content: string; critiqued?: boolean };

type Continuity = {
  yesterday: string[];
  recent_days: { date: string; label: string; items: string[] }[];
  has_history: boolean;
  seed_question: string;
};

export default function BriefChat({
  mode,
  engine = "claude",
}: {
  mode: "daily" | "evening";
  engine?: string;
}) {
  const [open, setOpen] = useState(false);
  const [cont, setCont] = useState<Continuity | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  const expand = async () => {
    const next = !open;
    setOpen(next);
    if (next && !cont) {
      try {
        const r = await fetch("/api/brief/continuity?days_back=3");
        if (r.ok) setCont(await r.json());
      } catch {
        /* 連続性は出なくても対話は成立する */
      }
    }
  };

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (busy) return;
    const history = [...messages];
    if (trimmed) history.push({ role: "user", content: trimmed });
    setMessages(history);
    setInput("");
    setBusy(true);
    try {
      const r = await fetch("/api/brief/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode,
          engine,
          messages: history.map((m) => ({ role: m.role, content: m.content })),
        }),
      });
      const d = await r.json();
      setMessages([
        ...history,
        { role: "assistant", content: d.reply ?? "(応答なし)", critiqued: d.critiqued },
      ]);
    } catch {
      setMessages([...history, { role: "assistant", content: "(通信に失敗しました)" }]);
    } finally {
      setBusy(false);
    }
  };

  const title = mode === "daily" ? "🗣 対話で今日を組み直す" : "🗣 対話で振り返る";
  const quicks =
    mode === "daily"
      ? ["昨日の続きから", "順番を組み直して", "それは今日は無理", "隙間に何を入れる?"]
      : ["明日に繰り越すものは?", "今日の学びを一行で", "落としていいものは?"];

  return (
    <div
      className="rounded-3xl overflow-hidden"
      style={{ border: "1px solid var(--color-border)", background: "var(--color-surface)" }}
    >
      <button
        onClick={expand}
        className="w-full flex items-center justify-between px-6 py-4 text-left"
        style={{ color: "var(--color-text)" }}
      >
        <span className="font-semibold flex items-center gap-2">{title}</span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {open ? "閉じる" : "開く"}
        </span>
      </button>

      {open && (
        <div className="px-6 pb-6 space-y-4">
          {/* 連続性: 昨日 / 直近やっていたこと */}
          {cont && (
            <div
              className="rounded-2xl p-4 text-sm"
              style={{ background: "var(--color-surface-hover)", color: "var(--color-text)" }}
            >
              <div
                className="text-[11px] font-semibold uppercase tracking-wider mb-2"
                style={{ color: "var(--color-text-muted)" }}
              >
                直近やっていたこと
              </div>
              {cont.has_history ? (
                <ul className="space-y-1">
                  {cont.recent_days.slice(0, 3).map((d) => (
                    <li key={d.date}>
                      <span style={{ color: "var(--color-text-muted)" }}>{d.label}:</span>{" "}
                      {d.items.slice(0, 6).join(" / ")}
                    </li>
                  ))}
                </ul>
              ) : (
                <p style={{ color: "var(--color-text-muted)" }}>
                  記録がまだ薄いです。完了ログ / 実績ログが溜まると連続性が出ます。
                </p>
              )}
              <p className="mt-2" style={{ color: "var(--color-text-muted)" }}>
                {cont.seed_question}
              </p>
            </div>
          )}

          {/* 会話ログ */}
          {messages.length > 0 && (
            <div className="space-y-3">
              {messages.map((m, i) => (
                <div
                  key={i}
                  className="rounded-2xl px-4 py-3 text-[15px] whitespace-pre-wrap leading-[1.8]"
                  style={{
                    background:
                      m.role === "user" ? "var(--color-surface-hover)" : "rgba(59,130,246,0.10)",
                    border: m.role === "user" ? "none" : "1px solid rgba(59,130,246,0.22)",
                    color: "var(--color-text)",
                  }}
                >
                  {m.content}
                  {m.role === "assistant" && m.critiqued && (
                    <span
                      className="ml-2 text-[10px] font-mono px-2 py-0.5 rounded-full align-middle"
                      style={{ background: "rgba(16,185,129,0.12)", color: "#10b981" }}
                    >
                      忖度チェック済
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

          {busy && (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              考えています...
            </p>
          )}

          {/* クイック返答 */}
          <div className="flex flex-wrap gap-2">
            {quicks.map((q) => (
              <button
                key={q}
                onClick={() => send(q)}
                disabled={busy}
                className="text-xs px-3 py-1.5 rounded-full disabled:opacity-40"
                style={{
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text-muted)",
                }}
              >
                {q}
              </button>
            ))}
          </div>

          {/* 入力欄 */}
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.nativeEvent.isComposing) send(input);
              }}
              placeholder={mode === "daily" ? "今日の組み方を相談..." : "振り返りを相談..."}
              disabled={busy}
              className="flex-1 rounded-full px-4 py-2 text-sm outline-none"
              style={{
                background: "var(--color-surface-hover)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
              }}
            />
            <button
              onClick={() => send(input)}
              disabled={busy || !input.trim()}
              className="rounded-full px-4 py-2 text-sm font-medium disabled:opacity-40"
              style={{ background: "var(--color-accent)", color: "#fff" }}
            >
              送信
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
