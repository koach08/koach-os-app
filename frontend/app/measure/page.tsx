"use client";

/**
 * ループの効き目 — 提案→実行の測定。
 * 「autopilot が下書きを出す → 承認する → 実際に行動になる」が数字で回っているか。
 * 溜まるだけの劇場になっていないかを正直に見る。読み取り専用 (書き込みなし)。
 */

import { useEffect, useState } from "react";

type Measure = {
  days: number;
  proposals: {
    total: number;
    pending: number;
    promoted: number;
    rejected: number;
    approval_rate: number | null;
    triage_rate: number | null;
    median_days_to_decision: number | null;
    window_created: number;
    window_promoted: number;
  };
  protect: {
    window_confirmed: number;
    by_category: Record<string, number>;
    last: { title?: string; category?: string; confirmed_at?: string } | null;
  };
  execution: { completions: number; by_category: Record<string, number> };
  verdict: string;
};

const CAT_JA: Record<string, string> = {
  family: "家族",
  health: "健康",
  creative: "創作",
  research: "研究",
  career: "仕事",
  side_project: "個人開発",
  admin: "事務",
  rest: "休息",
  other: "その他",
};

function pct(x: number | null): string {
  return x === null ? "—" : `${Math.round(x * 100)}%`;
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div
      className="rounded-2xl p-4 flex flex-col gap-1"
      style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
    >
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </span>
      <span className="text-2xl font-semibold tabular-nums">{value}</span>
      {sub && (
        <span className="text-[11px]" style={{ color: "var(--color-text-muted)" }}>
          {sub}
        </span>
      )}
    </div>
  );
}

export default function MeasurePage() {
  const [data, setData] = useState<Measure | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/measure?days=${days}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [days]);

  const p = data?.proposals;
  const prot = data?.protect;
  const exe = data?.execution;

  return (
    <main className="max-w-3xl mx-auto px-5 py-8 space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <span>📐</span> ループの効き目
        </h1>
        <p className="text-sm leading-relaxed" style={{ color: "var(--color-text-muted)" }}>
          下書きを出す → 承認する → 行動になる。この流れが本当に回っているかを測ります。
          未処理が溜まるだけなら、propose-loop はただの劇場です。
        </p>
        <div className="flex gap-1.5 pt-1">
          {[7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className="text-xs rounded-full px-3 py-1"
              style={{
                background: days === d ? "var(--color-accent)" : "var(--color-surface)",
                color: days === d ? "#fff" : "var(--color-text-muted)",
                border: "1px solid var(--color-border)",
              }}
            >
              {d}日
            </button>
          ))}
        </div>
      </header>

      {loading ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          読み込み中...
        </p>
      ) : !data ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          読み込めませんでした。
        </p>
      ) : (
        <div className="space-y-6">
          {/* 正直な判定 */}
          <div
            className="rounded-3xl p-5 text-sm leading-relaxed"
            style={{ background: "var(--color-surface-hover)", border: "1px solid var(--color-border)" }}
          >
            {data.verdict}
          </div>

          {/* 下書きファネル */}
          <section className="space-y-3">
            <h2 className="text-sm font-semibold" style={{ color: "var(--color-text-muted)" }}>
              📥 下書き → 承認（全期間）
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <Stat label="生成された下書き" value={String(p!.total)} sub={`直近${days}日: ${p!.window_created}件`} />
              <Stat label="承認 → 昇格" value={String(p!.promoted)} sub={`直近${days}日: ${p!.window_promoted}件`} />
              <Stat label="却下" value={String(p!.rejected)} />
              <Stat label="未処理" value={String(p!.pending)} sub={p!.pending >= 5 ? "溜まっています" : undefined} />
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <Stat label="承認率" value={pct(p!.approval_rate)} sub="決着したうち昇格した割合" />
              <Stat label="処理率" value={pct(p!.triage_rate)} sub="出した下書きを捌けた割合" />
              <Stat
                label="反応の速さ"
                value={p!.median_days_to_decision === null ? "—" : `${p!.median_days_to_decision}日`}
                sub="生成→決着の中央値"
              />
            </div>
          </section>

          {/* 保護の実行 */}
          <section className="space-y-3">
            <h2 className="text-sm font-semibold" style={{ color: "var(--color-text-muted)" }}>
              ⛊ 保護ブロックの確保（直近{days}日）
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <Stat label="確保した回数" value={String(prot!.window_confirmed)} />
              {Object.entries(prot!.by_category).map(([c, n]) => (
                <Stat key={c} label={CAT_JA[c] ?? c} value={String(n)} sub="回 確保" />
              ))}
            </div>
            {prot!.window_confirmed === 0 && (
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                まだ確保がありません。Daily の「⛊ 家族・健康を守る」から 1 タップで確保すると、ここに実行として計上されます。
              </p>
            )}
          </section>

          {/* 実行の文脈 */}
          <section className="space-y-3">
            <h2 className="text-sm font-semibold" style={{ color: "var(--color-text-muted)" }}>
              ✅ 完了実績（直近{days}日・文脈）
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <Stat label="完了" value={String(exe!.completions)} sub="全カテゴリ合計" />
              {Object.entries(exe!.by_category)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 3)
                .map(([c, n]) => (
                  <Stat key={c} label={CAT_JA[c] ?? c} value={String(n)} />
                ))}
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
