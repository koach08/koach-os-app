"use client";

import { useEffect, useState } from "react";

type Followup = {
  id: string;
  thread_id: string;
  from: string;
  subject: string;
  received_at: string;
  snippet: string;
  category: string;
  urgency: "high" | "medium" | "low";
  deadline_date?: string | null;
  summary: string;
  action_hint: string;
  done_at?: string | null;
  snooze_until?: string | null;
  days_since_received?: number;
};

const URGENCY_COLOR: Record<string, string> = {
  high: "#ef4444",
  medium: "#f59e0b",
  low: "#71717a",
};

const CAT_EMOJI: Record<string, string> = {
  university: "🎓",
  research: "🔬",
  prospective_student: "🎯",
  personal: "👤",
  promo: "📣",
  system: "🔧",
  other: "📌",
};

export default function EmailWatchPage() {
  const [items, setItems] = useState<Followup[]>([]);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [recentlyDone, setRecentlyDone] = useState<Followup | null>(null);
  const [undoCountdown, setUndoCountdown] = useState<number>(0);
  // 返信案 modal
  const [replyFor, setReplyFor] = useState<Followup | null>(null);
  const [replyHint, setReplyHint] = useState<string>("");
  const [replyEngine, setReplyEngine] = useState<string>("claude");
  const [replyText, setReplyText] = useState<string>("");
  const [replyLoading, setReplyLoading] = useState<boolean>(false);
  const [replyCopied, setReplyCopied] = useState<boolean>(false);

  const load = () => {
    setLoading(true);
    setError(null);
    fetch(`/api/email-watch/pending${overdueOnly ? "?overdue_only=true" : ""}`)
      .then((r) => r.json())
      .then((d) => setItems(d.items ?? []))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [overdueOnly]);

  const scan = async () => {
    setScanning(true);
    setError(null);
    setScanResult(null);
    try {
      const r = await fetch("/api/email-watch/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slot: 2, days: 30, max_emails: 150 }),
      });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      setScanResult(`スキャン: ${d.scanned} 件 / 新規分類: ${d.new_classified} 件 / 追跡追加: ${d.added_followups} 件 / 合計追跡: ${d.total_tracked} 件`);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setScanning(false);
    }
  };

  const markDone = async (id: string) => {
    const target = items.find((x) => x.id === id);
    await fetch(`/api/email-watch/${id}/done`, { method: "POST" });
    setItems((prev) => prev.filter((x) => x.id !== id));
    if (target) {
      setRecentlyDone(target);
      setUndoCountdown(5);
    }
  };

  const undoDone = async () => {
    if (!recentlyDone) return;
    const it = recentlyDone;
    setRecentlyDone(null);
    setUndoCountdown(0);
    try {
      await fetch(`/api/email-watch/${it.id}/reopen`, { method: "POST" });
      setItems((prev) => [{ ...it, done_at: null }, ...prev]);
    } catch {
      // 戻せなかった場合は再 load で実態を取得
      load();
    }
  };

  useEffect(() => {
    if (!recentlyDone) return;
    if (undoCountdown <= 0) {
      setRecentlyDone(null);
      return;
    }
    const t = setTimeout(() => setUndoCountdown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [recentlyDone, undoCountdown]);

  const openReply = (it: Followup) => {
    setReplyFor(it);
    setReplyHint("");
    setReplyText("");
    setReplyCopied(false);
  };

  const closeReply = () => {
    setReplyFor(null);
    setReplyHint("");
    setReplyText("");
    setReplyLoading(false);
    setReplyCopied(false);
  };

  const generateReply = async () => {
    if (!replyFor) return;
    setReplyLoading(true);
    setReplyText("");
    try {
      const r = await fetch(`/api/email-watch/${replyFor.id}/draft-reply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hint: replyHint, engine: replyEngine }),
      });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      setReplyText(d.reply_text || "");
    } catch (e) {
      setReplyText(`生成失敗: ${(e as Error).message}`);
    } finally {
      setReplyLoading(false);
    }
  };

  const copyReply = async () => {
    if (!replyText) return;
    try {
      await navigator.clipboard.writeText(replyText);
      setReplyCopied(true);
      setTimeout(() => setReplyCopied(false), 2000);
    } catch {
      // noop
    }
  };

  const snooze = async (id: string, days: number) => {
    await fetch(`/api/email-watch/${id}/snooze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ days }),
    });
    setItems((prev) => prev.filter((x) => x.id !== id));
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div
        className="px-8 pt-12 pb-8"
        style={{
          background:
            "radial-gradient(ellipse at top left, rgba(245, 158, 11, 0.12), transparent 60%)",
        }}
      >
        <div className="max-w-4xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            Email Watch
          </p>
          <h1 className="text-4xl font-bold tracking-tight">対応待ちメール</h1>
          <p className="mt-3 text-sm" style={{ color: "var(--color-text-muted)" }}>
            slot 2 (kshgks59 = 大学転送) から AI が「要返信」を抽出。返信済みは自動で消える。
          </p>
          <div className="mt-5 flex items-center gap-2 flex-wrap">
            <button
              onClick={scan}
              disabled={scanning}
              className="px-4 py-1.5 rounded-full text-xs font-medium disabled:opacity-50"
              style={{ background: "#f59e0b", color: "white" }}
            >
              {scanning ? "スキャン中... (30秒〜)" : "🔄 過去30日をスキャン"}
            </button>
            <label className="text-xs flex items-center gap-1.5" style={{ color: "var(--color-text-muted)" }}>
              <input type="checkbox" checked={overdueOnly} onChange={(e) => setOverdueOnly(e.target.checked)} />
              2 日以上未対応のみ
            </label>
            <span className="ml-auto text-xs font-mono" style={{ color: "var(--color-text-muted)" }}>
              {items.length} 件
            </span>
          </div>
          {scanResult && (
            <div className="mt-3 text-xs" style={{ color: "var(--color-text-muted)" }}>
              ✓ {scanResult}
            </div>
          )}
        </div>
      </div>

      <div className="px-8 pb-32">
        <div className="max-w-4xl mx-auto space-y-3">
          {error && (
            <div className="p-3 rounded-xl text-sm" style={{ background: "rgba(239, 68, 68, 0.08)", color: "var(--color-red)" }}>
              {error}
            </div>
          )}

          {loading && <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>読み込み中...</p>}

          {!loading && items.length === 0 && (
            <div className="rounded-2xl p-6 text-sm text-center" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}>
              {scanResult ? "✓ 対応待ちなし。さっぱり。" : "まだスキャンされていません。上の「スキャン」ボタンを押してください。"}
            </div>
          )}

          {items.map((it) => {
            const color = URGENCY_COLOR[it.urgency];
            return (
              <div
                key={it.id}
                className="rounded-2xl p-4"
                style={{
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  borderLeft: `3px solid ${color}`,
                }}
              >
                <div className="flex items-start gap-3 mb-2">
                  <span className="text-lg" title={it.category}>{CAT_EMOJI[it.category] ?? "📌"}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-sm">{it.subject}</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded" style={{ background: `${color}20`, color }}>
                        {it.urgency}
                      </span>
                      {it.deadline_date && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded" style={{ background: "rgba(239, 68, 68, 0.15)", color: "#ef4444" }}>
                          📅 {it.deadline_date}
                        </span>
                      )}
                      <span className="text-[10px] ml-auto font-mono" style={{ color: "var(--color-text-muted)" }}>
                        {it.days_since_received ?? 0}日前
                      </span>
                    </div>
                    <div className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                      {it.from}
                    </div>
                  </div>
                </div>
                <div className="text-sm mb-1">{it.summary}</div>
                <div className="text-xs mb-3" style={{ color: "var(--color-text-muted)" }}>
                  → {it.action_hint}
                </div>
                <details>
                  <summary className="text-[11px] cursor-pointer" style={{ color: "var(--color-text-muted)" }}>
                    本文プレビュー
                  </summary>
                  <div className="text-[11px] mt-1 p-2 rounded" style={{ background: "var(--color-background)", color: "var(--color-text-muted)" }}>
                    {it.snippet}
                  </div>
                </details>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <button
                    onClick={() => markDone(it.id)}
                    className="text-xs px-3 py-1 rounded-full"
                    style={{ background: "rgba(16, 185, 129, 0.15)", color: "#10b981" }}
                  >
                    対応済みにする
                  </button>
                  {[1, 3, 7].map((d) => (
                    <button
                      key={d}
                      onClick={() => snooze(it.id, d)}
                      className="text-xs px-3 py-1 rounded-full"
                      style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}
                    >
                      😴 +{d}d
                    </button>
                  ))}
                  <button
                    onClick={() => openReply(it)}
                    className="text-xs px-3 py-1 rounded-full ml-auto"
                    style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}
                    title="AI に返信案を相談"
                  >
                    ✉️ 返信を相談
                  </button>
                  <a
                    href={`https://mail.google.com/mail/u/1/#inbox/${it.thread_id || it.id}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs px-3 py-1 rounded-full"
                    style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}
                  >
                    Gmail で開く
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {replyFor && (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.5)" }}
          onClick={closeReply}
        >
          <div
            className="rounded-2xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1 min-w-0">
                <p className="text-xs uppercase tracking-widest mb-1" style={{ color: "var(--color-text-muted)" }}>
                  ✉️ 返信案 AI 相談
                </p>
                <h2 className="text-base font-semibold truncate">{replyFor.subject}</h2>
                <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                  From: {replyFor.from}
                </p>
              </div>
              <button onClick={closeReply} className="text-xl px-2" style={{ color: "var(--color-text-muted)" }}>
                ×
              </button>
            </div>

            <div className="mb-4">
              <label className="text-xs block mb-1" style={{ color: "var(--color-text-muted)" }}>
                返信の方針・ヒント (任意)
              </label>
              <textarea
                value={replyHint}
                onChange={(e) => setReplyHint(e.target.value)}
                placeholder="例: 候補日を 6/15 (月) 14時 と 6/17 (水) 10時 で提示してほしい"
                className="w-full rounded-lg p-2 text-sm"
                style={{ background: "var(--color-surface-hover)", border: "1px solid var(--color-border)", minHeight: 60 }}
              />
            </div>

            <div className="mb-4 flex items-center gap-2">
              <label className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                エンジン:
              </label>
              {["claude", "gpt", "gemini"].map((en) => (
                <button
                  key={en}
                  onClick={() => setReplyEngine(en)}
                  className="text-xs px-2.5 py-1 rounded-full"
                  style={{
                    background: replyEngine === en ? "#f59e0b" : "var(--color-surface-hover)",
                    color: replyEngine === en ? "white" : "var(--color-text-muted)",
                  }}
                >
                  {en}
                </button>
              ))}
              <button
                onClick={generateReply}
                disabled={replyLoading}
                className="ml-auto text-xs px-4 py-1.5 rounded-full disabled:opacity-50"
                style={{ background: "#f59e0b", color: "white" }}
              >
                {replyLoading ? "生成中..." : "返信案を生成"}
              </button>
            </div>

            {replyText && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                    返信案 ({replyText.length} 字)
                  </span>
                  <button
                    onClick={copyReply}
                    className="text-xs px-3 py-1 rounded-full"
                    style={{ background: replyCopied ? "#10b981" : "var(--color-surface-hover)", color: replyCopied ? "white" : "var(--color-text-muted)" }}
                  >
                    {replyCopied ? "✓ コピー済み" : "コピー"}
                  </button>
                </div>
                <pre
                  className="text-sm whitespace-pre-wrap p-3 rounded-lg"
                  style={{ background: "var(--color-surface-hover)", border: "1px solid var(--color-border)", fontFamily: "inherit", lineHeight: 1.7 }}
                >
                  {replyText}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}

      {recentlyDone && (
        <div
          className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-2.5 rounded-full shadow-lg"
          style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
        >
          <span className="text-sm">
            ✓ 対応済みにしました
            <span className="ml-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
              {recentlyDone.subject.slice(0, 30)}
            </span>
          </span>
          <button
            onClick={undoDone}
            className="text-xs px-3 py-1 rounded-full"
            style={{ background: "#f59e0b", color: "white" }}
          >
            ↩ 元に戻す ({undoCountdown})
          </button>
        </div>
      )}
    </div>
  );
}
