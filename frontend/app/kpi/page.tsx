"use client";

import { useEffect, useState } from "react";

type Metric = {
  id: string;
  label: string;
  value: number;
  unit?: string;
  delta_7d?: number | null;
  url?: string;
  category?: string;
};

type Snapshot = {
  updated_at: string | null;
  metrics: Metric[];
  by_category: Record<string, Metric[]>;
};

const CAT_META: Record<string, { emoji: string; label: string; color: string }> = {
  growth: { emoji: "📈", label: "成長", color: "#10b981" },
  revenue: { emoji: "💰", label: "売上", color: "#f59e0b" },
  capital: { emoji: "🏦", label: "資産", color: "#3b82f6" },
  health: { emoji: "💪", label: "健康", color: "#ef4444" },
  other: { emoji: "📌", label: "その他", color: "#71717a" },
};

export default function KpiPage() {
  const [data, setData] = useState<Snapshot | null>(null);
  const [editing, setEditing] = useState<Metric | null>(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    fetch("/api/kpi")
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError((e as Error).message));
  };

  useEffect(() => {
    load();
  }, []);

  const save = async (m: Metric) => {
    setError(null);
    try {
      await fetch("/api/kpi/metric", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(m),
      });
      setEditing(null);
      setAdding(false);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const remove = async (id: string) => {
    if (!confirm(`「${id}」を削除しますか?`)) return;
    await fetch(`/api/kpi/metric/${encodeURIComponent(id)}`, { method: "DELETE" });
    load();
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="px-8 pt-12 pb-8" style={{ background: "radial-gradient(ellipse at top, rgba(59, 130, 246, 0.10), transparent 60%)" }}>
        <div className="max-w-5xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            KPI Dashboard
          </p>
          <h1 className="text-4xl font-bold tracking-tight">数字を視界に</h1>
          {data?.updated_at && (
            <p className="text-xs mt-2" style={{ color: "var(--color-text-muted)" }}>
              更新 {new Date(data.updated_at).toLocaleString("ja-JP")}
            </p>
          )}
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-5xl mx-auto space-y-6">
          {error && (
            <div className="p-3 rounded-xl text-sm" style={{ background: "rgba(239, 68, 68, 0.08)", color: "var(--color-red)" }}>
              {error}
            </div>
          )}

          {data && Object.keys(data.by_category).length === 0 && (
            <div
              className="rounded-2xl p-6 text-sm"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            >
              まだ KPI が登録されていません。「+ 追加」から指標を入れてください。
              外部スクリプトから <code className="font-mono text-xs px-1.5 py-0.5 rounded" style={{ background: "var(--color-surface-hover)" }}>POST /api/kpi</code> でも一括投入できます。
            </div>
          )}

          {data &&
            Object.entries(data.by_category).map(([cat, metrics]) => {
              const meta = CAT_META[cat] ?? CAT_META.other;
              return (
                <section key={cat}>
                  <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
                    <span>{meta.emoji}</span>
                    <span>{meta.label}</span>
                  </h2>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {metrics.map((m) => (
                      <div
                        key={m.id}
                        className="rounded-2xl p-5 group relative"
                        style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
                      >
                        <div className="text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>
                          {m.label}
                        </div>
                        <div className="text-2xl font-bold font-mono">
                          {m.value.toLocaleString()} <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{m.unit}</span>
                        </div>
                        {m.delta_7d != null && (
                          <div
                            className="text-xs mt-1 font-mono"
                            style={{ color: m.delta_7d >= 0 ? "#10b981" : "#ef4444" }}
                          >
                            {m.delta_7d >= 0 ? "▲" : "▼"} {Math.abs(m.delta_7d).toLocaleString()} / 7d
                          </div>
                        )}
                        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                          <button
                            onClick={() => setEditing(m)}
                            className="text-[10px] px-2 py-0.5 rounded"
                            style={{ background: "var(--color-surface-hover)" }}
                          >
                            edit
                          </button>
                          <button
                            onClick={() => remove(m.id)}
                            className="text-[10px] px-2 py-0.5 rounded"
                            style={{ background: "rgba(239,68,68,0.1)", color: "#ef4444" }}
                          >
                            ×
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              );
            })}

          <button
            onClick={() => {
              setAdding(true);
              setEditing({ id: "", label: "", value: 0, unit: "", category: "growth" });
            }}
            className="w-full py-3 rounded-2xl text-sm"
            style={{ border: "1px dashed var(--color-border)", color: "var(--color-text-muted)" }}
          >
            + KPI を追加
          </button>
        </div>
      </div>

      {editing && (
        <MetricEditor
          metric={editing}
          isNew={adding}
          onClose={() => {
            setEditing(null);
            setAdding(false);
          }}
          onSave={save}
        />
      )}
    </div>
  );
}

function MetricEditor({
  metric,
  isNew,
  onClose,
  onSave,
}: {
  metric: Metric;
  isNew: boolean;
  onClose: () => void;
  onSave: (m: Metric) => void;
}) {
  const [m, setM] = useState<Metric>(metric);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.6)" }}>
      <div
        className="rounded-2xl p-6 w-full max-w-md space-y-3"
        style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
      >
        <h3 className="font-semibold">{isNew ? "KPI 追加" : `${m.label} を編集`}</h3>
        <div className="grid grid-cols-2 gap-3">
          <Field label="ID" value={m.id} onChange={(v) => setM({ ...m, id: v })} disabled={!isNew} />
          <Field label="表示名" value={m.label} onChange={(v) => setM({ ...m, label: v })} />
          <Field label="値" value={String(m.value)} onChange={(v) => setM({ ...m, value: Number(v) || 0 })} type="number" />
          <Field label="単位" value={m.unit ?? ""} onChange={(v) => setM({ ...m, unit: v })} />
          <Field
            label="7日変化"
            value={String(m.delta_7d ?? "")}
            onChange={(v) => setM({ ...m, delta_7d: v === "" ? null : Number(v) })}
            type="number"
          />
          <div>
            <label className="block text-[10px] mb-1 uppercase" style={{ color: "var(--color-text-muted)" }}>
              カテゴリ
            </label>
            <select
              value={m.category ?? "growth"}
              onChange={(e) => setM({ ...m, category: e.target.value })}
              className="w-full px-3 py-2 rounded text-sm"
              style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
            >
              {Object.entries(CAT_META).map(([k, v]) => (
                <option key={k} value={k}>
                  {v.emoji} {v.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <Field label="URL (任意)" value={m.url ?? ""} onChange={(v) => setM({ ...m, url: v })} />
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="px-4 py-2 rounded-full text-sm" style={{ color: "var(--color-text-muted)" }}>
            キャンセル
          </button>
          <button
            onClick={() => onSave(m)}
            disabled={!m.id || !m.label}
            className="px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50"
            style={{ background: "var(--color-accent)", color: "white" }}
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  disabled,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  type?: string;
}) {
  return (
    <div>
      <label className="block text-[10px] mb-1 uppercase" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </label>
      <input
        type={type}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 rounded text-sm disabled:opacity-50"
        style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
      />
    </div>
  );
}
