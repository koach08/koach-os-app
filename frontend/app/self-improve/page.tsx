"use client";

import { useEffect, useState } from "react";

type Stats = {
  total?: number;
  engines?: [string, number][];
  domains?: [string, number][];
  task_types?: [string, number][];
};

type Report = {
  ok: boolean;
  days: number;
  stats: Stats;
  report: string;
  engine?: string;
  model?: string;
};

type Snapshot = {
  timestamp: string;
  days: number;
  stats: Stats;
  report: string;
  engine?: string;
  model?: string;
};

export default function SelfImprovePage() {
  const [days, setDays] = useState(7);
  const [engine, setEngine] = useState("claude");
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [selectedSnap, setSelectedSnap] = useState<Snapshot | null>(null);

  const loadSnapshots = () => {
    fetch("/api/self-improve/snapshots")
      .then((r) => r.json())
      .then((d) => setSnapshots(d.items ?? []));
  };

  useEffect(() => {
    loadSnapshots();
  }, []);

  const generate = async () => {
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const r = await fetch(`/api/self-improve/report?days=${days}&engine=${engine}`);
      if (!r.ok) throw new Error(await r.text());
      setReport(await r.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      await fetch("/api/self-improve/snapshot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ days, engine }),
      });
      loadSnapshots();
    } finally {
      setSaving(false);
    }
  };

  const current = selectedSnap ?? report;

  return (
    <div className="flex-1 overflow-y-auto">
      <div
        className="px-8 pt-12 pb-8"
        style={{ background: "radial-gradient(ellipse at top, rgba(34, 197, 94, 0.10), transparent 60%)" }}
      >
        <div className="max-w-5xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            Self Improve
          </p>
          <h1 className="text-4xl font-bold tracking-tight">🌱 自己改善ループ</h1>
          <p className="mt-3 text-sm" style={{ color: "var(--color-text-muted)" }}>
            メタ AI が過去ログを見て、 使用パターン / エンジン分布 / 次の打ち手 を返す。 read-only (prompt 自動書換なし)。
          </p>

          <div className="mt-6 flex items-center gap-2 flex-wrap">
            <label className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              期間:
            </label>
            {[7, 14, 30].map((d) => (
              <button
                key={d}
                onClick={() => {
                  setDays(d);
                  setSelectedSnap(null);
                }}
                className="text-xs px-3 py-1 rounded-full"
                style={{
                  background: days === d ? "#22c55e" : "var(--color-surface-hover)",
                  color: days === d ? "white" : "var(--color-text-muted)",
                }}
              >
                {d} 日
              </button>
            ))}
            <label className="text-xs ml-3" style={{ color: "var(--color-text-muted)" }}>
              メタ AI:
            </label>
            {["claude", "gpt", "gemini"].map((en) => (
              <button
                key={en}
                onClick={() => setEngine(en)}
                className="text-xs px-2.5 py-1 rounded-full"
                style={{
                  background: engine === en ? "#22c55e" : "var(--color-surface-hover)",
                  color: engine === en ? "white" : "var(--color-text-muted)",
                }}
              >
                {en}
              </button>
            ))}
            <button
              onClick={generate}
              disabled={loading}
              className="ml-auto text-xs px-4 py-1.5 rounded-full disabled:opacity-50"
              style={{ background: "#22c55e", color: "white" }}
            >
              {loading ? "分析中..." : "🪞 レポート生成"}
            </button>
            {report && (
              <button
                onClick={save}
                disabled={saving}
                className="text-xs px-3 py-1.5 rounded-full disabled:opacity-50"
                style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}
              >
                {saving ? "保存中..." : "📸 baseline 保存"}
              </button>
            )}
          </div>

          {error && (
            <div className="mt-4 p-3 rounded-xl text-sm" style={{ background: "rgba(239, 68, 68, 0.08)", color: "var(--color-red)" }}>
              {error}
            </div>
          )}
        </div>
      </div>

      <div className="px-8 pb-32">
        <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-[1fr,2fr] gap-4">
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-widest mb-1" style={{ color: "var(--color-text-muted)" }}>
              過去 baseline
            </p>
            {snapshots.length === 0 && (
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                まだ保存なし。 レポート生成 → 📸 baseline 保存。
              </p>
            )}
            {snapshots.map((s, i) => (
              <button
                key={i}
                onClick={() => setSelectedSnap(s)}
                className="w-full text-left rounded-xl p-3"
                style={{
                  background: selectedSnap === s ? "var(--color-surface-hover)" : "var(--color-surface)",
                  border: `1px solid ${selectedSnap === s ? "#22c55e" : "var(--color-border)"}`,
                }}
              >
                <p className="text-xs font-mono">{s.timestamp.slice(0, 16)}</p>
                <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                  {s.days} 日 / {s.stats.total ?? 0} 件 / {s.engine}
                </p>
              </button>
            ))}
            {selectedSnap && (
              <button
                onClick={() => setSelectedSnap(null)}
                className="text-xs px-3 py-1 rounded-full mt-2"
                style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}
              >
                最新に戻る
              </button>
            )}
          </div>

          <div className="rounded-2xl p-5" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
            {!current && (
              <p className="text-sm text-center py-12" style={{ color: "var(--color-text-muted)" }}>
                右上の「🪞 レポート生成」を押す
              </p>
            )}
            {current && (
              <>
                <div className="mb-4 flex items-center gap-3 flex-wrap">
                  <span className="text-xs font-mono" style={{ color: "var(--color-text-muted)" }}>
                    {current.stats.total ?? 0} 件のログから分析 · {current.engine ?? "—"}
                  </span>
                </div>
                {current.stats.engines && current.stats.engines.length > 0 && (
                  <div className="mb-4">
                    <p className="text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>
                      エンジン使用
                    </p>
                    <div className="flex gap-2 flex-wrap">
                      {current.stats.engines.map(([en, n]) => (
                        <span
                          key={en}
                          className="text-xs px-2 py-1 rounded-full"
                          style={{ background: "var(--color-surface-hover)" }}
                        >
                          {en}: {n}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <pre
                  className="text-sm whitespace-pre-wrap"
                  style={{ fontFamily: "inherit", lineHeight: 1.8 }}
                >
                  {current.report}
                </pre>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
