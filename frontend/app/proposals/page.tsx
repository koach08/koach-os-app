"use client";

/**
 * 承認待ち (KB Proposals) — Consolidate が出した構造化下書きを 1 タップで decisions に昇格する。
 * autopilot は提案のみ。実データ (decisions) への反映はこのページの「承認」でだけ起きる。
 */

import { useEffect, useState } from "react";

type Proposal = {
  id: string;
  kind: string;
  title: string;
  context: string;
  options: string[];
  chosen: string;
  reasoning: string;
  domain: string;
  status: string;
  created_at: string;
};

const DOMAIN_JA: Record<string, string> = {
  personal: "個人",
  research: "研究",
  platform: "プラットフォーム",
  revenue: "収益",
  teaching: "教育",
};

export default function ProposalsPage() {
  const [items, setItems] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<Record<string, string>>({});
  const [done, setDone] = useState<{ id: string; kind: "promoted" | "rejected" }[]>([]);

  const load = () => {
    setLoading(true);
    fetch("/api/proposals?status=pending")
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => setItems(d.items ?? []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const act = async (id: string, action: "promote" | "reject") => {
    if (busy[id]) return;
    setBusy((b) => ({ ...b, [id]: action }));
    try {
      const r = await fetch(`/api/proposals/${id}/${action}`, { method: "POST" });
      if (r.ok) {
        setItems((xs) => xs.filter((x) => x.id !== id));
        setDone((d) => [...d, { id, kind: action === "promote" ? "promoted" : "rejected" }]);
      }
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

  return (
    <main className="max-w-3xl mx-auto px-5 py-8 space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <span>📥</span> 承認待ち
        </h1>
        <p className="text-sm leading-relaxed" style={{ color: "var(--color-text-muted)" }}>
          水曜の Consolidate が、走り書き・実績から「残す価値のある知識」を下書きにしています。
          承認したものだけ decisions に昇格します。却下したものは記録に残りません。
        </p>
        {done.length > 0 && (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            このセッションで 昇格 {done.filter((d) => d.kind === "promoted").length} 件 / 却下{" "}
            {done.filter((d) => d.kind === "rejected").length} 件
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
          承認待ちの下書きはありません。
          <br />
          水曜 07:00 の Consolidate が新しい下書きを生成します。
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((p) => (
            <div
              key={p.id}
              className="rounded-3xl p-6 space-y-3"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            >
              <div className="flex items-start justify-between gap-3">
                <h2 className="font-semibold text-[17px] leading-snug">{p.title}</h2>
                <div className="flex gap-1.5 shrink-0">
                  <span
                    className="text-[10px] font-mono px-2 py-0.5 rounded-full"
                    style={{ background: "rgba(59,130,246,0.12)", color: "#3b82f6" }}
                  >
                    {p.kind}
                  </span>
                  <span
                    className="text-[10px] font-mono px-2 py-0.5 rounded-full"
                    style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}
                  >
                    {DOMAIN_JA[p.domain] ?? p.domain}
                  </span>
                </div>
              </div>

              {p.context && (
                <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                  {p.context}
                </p>
              )}
              {p.options && p.options.length > 0 && (
                <div className="text-sm">
                  <span style={{ color: "var(--color-text-muted)" }}>検討: </span>
                  {p.options.join(" / ")}
                </div>
              )}
              {p.chosen && (
                <div
                  className="text-sm rounded-2xl px-4 py-2"
                  style={{ background: "var(--color-surface-hover)" }}
                >
                  <span style={{ color: "var(--color-text-muted)" }}>結論: </span>
                  {p.chosen}
                </div>
              )}
              {p.reasoning && (
                <p className="text-sm leading-relaxed" style={{ color: "var(--color-text)" }}>
                  {p.reasoning}
                </p>
              )}

              <div className="flex gap-2 pt-1">
                <button
                  onClick={() => act(p.id, "promote")}
                  disabled={!!busy[p.id]}
                  className="rounded-full px-5 py-2 text-sm font-medium disabled:opacity-40"
                  style={{ background: "var(--color-accent)", color: "#fff" }}
                >
                  {busy[p.id] === "promote" ? "昇格中..." : "✓ 承認して昇格"}
                </button>
                <button
                  onClick={() => act(p.id, "reject")}
                  disabled={!!busy[p.id]}
                  className="rounded-full px-5 py-2 text-sm disabled:opacity-40"
                  style={{ border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}
                >
                  {busy[p.id] === "reject" ? "処理中..." : "却下"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
