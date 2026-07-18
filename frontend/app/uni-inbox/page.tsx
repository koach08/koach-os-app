"use client";

/**
 * 🎓 大学メール受信箱 — hokudai/ac.jp 由来の予定・締切を「見落とさない」トラッカー。
 * スキャンで拾った項目は反映か無視をするまで pending で残る。1 タップでカレンダーへ。
 * 自動 dedup が消した項目は「無視した項目」から戻せる (誤判定の安全弁)。
 */

import { useEffect, useState } from "react";

type Item = {
  id: string;
  title: string;
  start_iso: string;
  end_iso: string;
  description: string;
  location: string;
  confidence: string;
  event_type: string;
  source_subject: string;
  source_from: string;
  status: string;
  dismiss_reason?: string;
};

const TYPE_JA: Record<string, string> = {
  deadline: "締切",
  committee: "委員会",
  meeting: "会議",
  default: "予定",
};

const CONF_JA: Record<string, { label: string; color: string }> = {
  high: { label: "高信頼", color: "#10b981" },
  medium: { label: "要確認", color: "#f59e0b" },
  low: { label: "曖昧", color: "#64748b" },
};

const REASON_JA: Record<string, string> = {
  "near-duplicate": "重複(自動)",
  "ai-duplicate": "重複(AI)",
};

function fmtWhen(iso: string): string {
  if (!iso) return "日付未定";
  const day = iso.slice(0, 10);
  if (iso.includes("T")) return `${day} ${iso.slice(11, 16)}`;
  return `${day}（終日）`;
}

export default function UniInboxPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<Record<string, string>>({});
  const [scanning, setScanning] = useState(false);
  const [msg, setMsg] = useState<string>("");

  const [showDismissed, setShowDismissed] = useState(false);
  const [dismissed, setDismissed] = useState<Item[]>([]);
  const [loadingDismissed, setLoadingDismissed] = useState(false);

  const load = () => {
    setLoading(true);
    fetch("/api/uni-inbox?status=pending")
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => setItems(d.items ?? []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const loadDismissed = () => {
    setLoadingDismissed(true);
    fetch("/api/uni-inbox?status=dismissed")
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => setDismissed(d.items ?? []))
      .catch(() => setDismissed([]))
      .finally(() => setLoadingDismissed(false));
  };

  const toggleDismissed = () => {
    const next = !showDismissed;
    setShowDismissed(next);
    if (next) loadDismissed();
  };

  const scan = async () => {
    if (scanning) return;
    setScanning(true);
    setMsg("大学メールをスキャン中…（Gemini が抽出・重複整理しています）");
    try {
      const r = await fetch("/api/uni-inbox/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ days: 7, max_per_slot: 50 }),
      });
      const d = await r.json();
      if (r.ok) {
        setMsg(
          `スキャン完了: 新規 ${d.new_pending ?? 0} 件 / 既にカレンダー ${d.already_calendar ?? 0} 件 / 重複整理 ${(d.deduped ?? 0) + (d.ai_deduped ?? 0)} 件（メール ${d.emails_scanned ?? 0} 通）`
        );
        load();
      } else {
        setMsg(`スキャン失敗: ${d.detail ?? "unknown"}`);
      }
    } catch (e) {
      setMsg(`スキャン失敗: ${e}`);
    } finally {
      setScanning(false);
    }
  };

  const dedupe = async () => {
    if (scanning) return;
    setScanning(true);
    setMsg("重複を整理中…（AI が同じ予定をまとめています）");
    try {
      const r = await fetch("/api/uni-inbox/dedupe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ai: true }),
      });
      const d = await r.json();
      if (r.ok) {
        setMsg(`重複を ${(d.deduped ?? 0) + (d.ai_deduped ?? 0)} 件まとめました。`);
        load();
      } else {
        setMsg(`整理に失敗: ${d.detail ?? "unknown"}`);
      }
    } catch (e) {
      setMsg(`整理に失敗: ${e}`);
    } finally {
      setScanning(false);
    }
  };

  const act = async (id: string, action: "calendar" | "dismiss") => {
    if (busy[id]) return;
    setBusy((b) => ({ ...b, [id]: action }));
    try {
      const r = await fetch(`/api/uni-inbox/${id}/${action}`, { method: "POST" });
      if (r.ok) setItems((xs) => xs.filter((x) => x.id !== id));
    } catch {
      /* keep item; user can retry */
    } finally {
      setBusy((b) => {
        const n = { ...b };
        delete n[id];
        return n;
      });
    }
  };

  const restore = async (id: string) => {
    if (busy[id]) return;
    setBusy((b) => ({ ...b, [id]: "restore" }));
    try {
      const r = await fetch(`/api/uni-inbox/${id}/restore`, { method: "POST" });
      if (r.ok) {
        setDismissed((xs) => xs.filter((x) => x.id !== id));
        load();
      }
    } catch {
      /* keep */
    } finally {
      setBusy((b) => {
        const n = { ...b };
        delete n[id];
        return n;
      });
    }
  };

  const reflectAll = async () => {
    if (scanning) return;
    const highCount = items.filter((i) => i.confidence === "high").length;
    if (highCount === 0) {
      setMsg("高信頼の未反映がありません。個別に確認してください。");
      return;
    }
    if (!confirm(`高信頼 ${highCount} 件をまとめてカレンダーに追加します。よろしいですか？`)) return;
    setScanning(true);
    try {
      const r = await fetch("/api/uni-inbox/reflect-all", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ min_confidence: "high" }),
      });
      const d = await r.json();
      if (r.ok) {
        setMsg(`${d.reflected ?? 0} 件をカレンダーに追加しました。`);
        load();
      } else {
        setMsg(`一括反映に失敗: ${d.detail ?? "unknown"}`);
      }
    } catch (e) {
      setMsg(`一括反映に失敗: ${e}`);
    } finally {
      setScanning(false);
    }
  };

  const highCount = items.filter((i) => i.confidence === "high").length;

  return (
    <main className="max-w-3xl mx-auto px-5 py-8 space-y-6">
      <header className="space-y-3">
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <span>🎓</span> 大学メール
          {!loading && items.length > 0 && (
            <span
              className="text-xs font-semibold px-2.5 py-0.5 rounded-full"
              style={{ background: "var(--color-accent)", color: "#fff" }}
            >
              未反映 {items.length}
            </span>
          )}
        </h1>
        <p className="text-sm leading-relaxed" style={{ color: "var(--color-text-muted)" }}>
          hokudai / ac.jp から来た予定・締切を拾って未反映として並べます。反映か無視をするまで残るので取りこぼしません。
          毎朝 06:30 に自動スキャンし、未反映があればメールで「忘れていませんか」と知らせます。
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={scan}
            disabled={scanning}
            className="rounded-full px-5 py-2 text-sm font-medium disabled:opacity-40"
            style={{ background: "var(--color-accent)", color: "#fff" }}
          >
            {scanning ? "処理中…" : "🔄 今すぐスキャン"}
          </button>
          {highCount > 0 && (
            <button
              onClick={reflectAll}
              disabled={scanning}
              className="rounded-full px-5 py-2 text-sm font-medium disabled:opacity-40"
              style={{ background: "#10b981", color: "#fff" }}
            >
              ✓ 高信頼 {highCount} 件をまとめて反映
            </button>
          )}
          {items.length > 1 && (
            <button
              onClick={dedupe}
              disabled={scanning}
              className="rounded-full px-5 py-2 text-sm disabled:opacity-40"
              style={{ border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}
            >
              🧹 重複を整理
            </button>
          )}
        </div>
        {msg && (
          <p className="text-xs rounded-2xl px-4 py-2" style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}>
            {msg}
          </p>
        )}
      </header>

      {loading ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          読み込み中...
        </p>
      ) : items.length === 0 ? (
        <div
          className="rounded-3xl p-8 text-center text-sm"
          style={{ border: "1px dashed var(--color-border)", color: "var(--color-text-muted)" }}
        >
          未反映の大学メールはありません。
          <br />
          「今すぐスキャン」で最新メールを取り込めます。
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((it) => {
            const conf = CONF_JA[it.confidence] ?? CONF_JA.medium;
            return (
              <div
                key={it.id}
                className="rounded-3xl p-5 space-y-2"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
                      <span
                        className="font-mono px-2 py-0.5 rounded-full"
                        style={{ background: "rgba(59,130,246,0.12)", color: "#3b82f6" }}
                      >
                        {TYPE_JA[it.event_type] ?? "予定"}
                      </span>
                      <span>{fmtWhen(it.start_iso)}</span>
                    </div>
                    <h2 className="font-semibold text-[16px] leading-snug">{it.title}</h2>
                  </div>
                  <span
                    className="text-[10px] font-mono px-2 py-0.5 rounded-full shrink-0"
                    style={{ background: "var(--color-surface-hover)", color: conf.color }}
                  >
                    {conf.label}
                  </span>
                </div>

                {it.location && (
                  <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                    📍 {it.location}
                  </p>
                )}
                {it.source_subject && (
                  <p className="text-xs truncate" style={{ color: "var(--color-text-muted)" }}>
                    ✉️ {it.source_subject}
                  </p>
                )}

                <div className="flex gap-2 pt-1">
                  <button
                    onClick={() => act(it.id, "calendar")}
                    disabled={!!busy[it.id]}
                    className="rounded-full px-4 py-1.5 text-sm font-medium disabled:opacity-40"
                    style={{ background: "var(--color-accent)", color: "#fff" }}
                  >
                    {busy[it.id] === "calendar" ? "追加中..." : "📅 カレンダーに追加"}
                  </button>
                  <button
                    onClick={() => act(it.id, "dismiss")}
                    disabled={!!busy[it.id]}
                    className="rounded-full px-4 py-1.5 text-sm disabled:opacity-40"
                    style={{ border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}
                  >
                    {busy[it.id] === "dismiss" ? "処理中..." : "無視"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 無視した項目 — auto-dedup が消したものを見て戻せる */}
      <section className="pt-2">
        <button
          onClick={toggleDismissed}
          className="text-xs"
          style={{ color: "var(--color-text-muted)" }}
        >
          {showDismissed ? "▼" : "▶"} 無視・重複整理した項目を{showDismissed ? "隠す" : "見る"}
        </button>
        {showDismissed && (
          <div className="mt-3 space-y-2">
            {loadingDismissed ? (
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>読み込み中...</p>
            ) : dismissed.length === 0 ? (
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                無視した項目はありません。
              </p>
            ) : (
              dismissed.map((it) => (
                <div
                  key={it.id}
                  className="rounded-2xl px-4 py-2.5 flex items-center justify-between gap-3"
                  style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-[11px]" style={{ color: "var(--color-text-muted)" }}>
                      <span>{fmtWhen(it.start_iso)}</span>
                      {it.dismiss_reason && REASON_JA[it.dismiss_reason] && (
                        <span
                          className="px-1.5 py-0.5 rounded-full"
                          style={{ background: "var(--color-surface-hover)" }}
                        >
                          {REASON_JA[it.dismiss_reason]}
                        </span>
                      )}
                    </div>
                    <p className="text-sm truncate" style={{ color: "var(--color-text)" }}>
                      {it.title}
                    </p>
                  </div>
                  <button
                    onClick={() => restore(it.id)}
                    disabled={!!busy[it.id]}
                    className="rounded-full px-3 py-1 text-xs shrink-0 disabled:opacity-40"
                    style={{ border: "1px solid var(--color-border)", color: "var(--color-accent)" }}
                  >
                    {busy[it.id] === "restore" ? "戻し中..." : "↩ 戻す"}
                  </button>
                </div>
              ))
            )}
          </div>
        )}
      </section>
    </main>
  );
}
