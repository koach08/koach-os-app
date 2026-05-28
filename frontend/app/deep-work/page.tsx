"use client";

import { useEffect, useState } from "react";

type Slot = { date: string; start_iso: string; end_iso: string; minutes: number };
type Plan = {
  generated_at: string;
  slot_count: number;
  free_total_minutes: number;
  backlog_count: number;
  pending_email_count: number;
  engine_used: string;
  plan: string;
  slots: Slot[];
};

export default function DeepWorkPage() {
  const [data, setData] = useState<Plan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [daysAhead, setDaysAhead] = useState(2);
  const [minMinutes, setMinMinutes] = useState(45);
  const [engine, setEngine] = useState("claude");
  const [freeSlots, setFreeSlots] = useState<Slot[]>([]);

  const fetchSlots = async () => {
    try {
      const r = await fetch(`/api/scheduling/free-slots?days_ahead=${daysAhead}&min_minutes=${minMinutes}`);
      if (r.ok) {
        const d = await r.json();
        setFreeSlots(d.slots ?? []);
      }
    } catch {}
  };

  useEffect(() => {
    fetchSlots();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [daysAhead, minMinutes]);

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/scheduling/deep-work-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ days_ahead: daysAhead, min_minutes: minMinutes, engine }),
      });
      if (!r.ok) throw new Error(await r.text());
      setData(await r.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div
        className="px-8 pt-12 pb-8"
        style={{
          background:
            "radial-gradient(ellipse at top left, rgba(16, 185, 129, 0.12), transparent 60%), radial-gradient(ellipse at top right, rgba(59, 130, 246, 0.06), transparent 50%)",
        }}
      >
        <div className="max-w-4xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            Deep Work Plan
          </p>
          <h1 className="text-4xl font-bold tracking-tight">空き時間にこれをやる</h1>
          <p className="mt-3 text-sm" style={{ color: "var(--color-text-muted)" }}>
            Calendar の隙間 × バックログ × 対応待ちメール を組み合わせて、Claude Code / Codex / Claude.ai 等のどの AI で進めるかまで AI が提案。
          </p>
          <div className="mt-5 flex items-center gap-3 flex-wrap">
            <label className="text-xs flex items-center gap-1.5" style={{ color: "var(--color-text-muted)" }}>
              日数:
              <select
                value={daysAhead}
                onChange={(e) => setDaysAhead(Number(e.target.value))}
                className="px-2 py-1 rounded text-xs"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
              >
                {[0, 1, 2, 3, 7].map((d) => (
                  <option key={d} value={d}>{d === 0 ? "今日のみ" : `${d} 日先まで`}</option>
                ))}
              </select>
            </label>
            <label className="text-xs flex items-center gap-1.5" style={{ color: "var(--color-text-muted)" }}>
              最小:
              <select
                value={minMinutes}
                onChange={(e) => setMinMinutes(Number(e.target.value))}
                className="px-2 py-1 rounded text-xs"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
              >
                {[25, 45, 60, 90, 120].map((m) => (
                  <option key={m} value={m}>{m} 分</option>
                ))}
              </select>
            </label>
            <select
              value={engine}
              onChange={(e) => setEngine(e.target.value)}
              className="px-2 py-1 rounded text-xs"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
            >
              <option value="claude">Claude (推奨)</option>
              <option value="gpt">GPT</option>
              <option value="gemini">Gemini</option>
            </select>
            <button
              onClick={generate}
              disabled={loading}
              className="ml-auto px-4 py-1.5 rounded-full text-xs font-medium disabled:opacity-50"
              style={{ background: "#10b981", color: "white" }}
            >
              {loading ? "生成中..." : "🪄 計画を生成"}
            </button>
          </div>
        </div>
      </div>

      <div className="px-8 pb-32">
        <div className="max-w-4xl mx-auto space-y-6">
          {freeSlots.length > 0 && (
            <div
              className="rounded-2xl p-5"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            >
              <h2 className="text-sm font-semibold mb-3">
                空き slot ({freeSlots.length} 件 / 合計 {Math.floor(freeSlots.reduce((s, x) => s + x.minutes, 0) / 60)}h {freeSlots.reduce((s, x) => s + x.minutes, 0) % 60}m)
              </h2>
              <ul className="space-y-1 text-xs">
                {freeSlots.map((s, i) => (
                  <li key={i} className="flex gap-3" style={{ color: "var(--color-text-muted)" }}>
                    <span className="font-mono shrink-0" style={{ minWidth: "9rem" }}>
                      {s.date.slice(5)} {s.start_iso.slice(11, 16)}〜{s.end_iso.slice(11, 16)}
                    </span>
                    <span>{s.minutes} 分</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {error && (
            <div className="p-3 rounded-xl text-sm" style={{ background: "rgba(239, 68, 68, 0.08)", color: "var(--color-red)" }}>
              {error}
            </div>
          )}

          {data && (
            <div
              className="rounded-2xl p-6"
              style={{
                background: "linear-gradient(135deg, rgba(16, 185, 129, 0.10) 0%, rgba(59, 130, 246, 0.04) 100%)",
                border: "1px solid rgba(16, 185, 129, 0.25)",
              }}
            >
              <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                <h2 className="text-base font-semibold flex items-center gap-2">
                  <span>🧭</span>
                  <span>AI 計画 ({data.engine_used})</span>
                </h2>
                <span className="text-[10px] font-mono" style={{ color: "var(--color-text-muted)" }}>
                  空き {Math.floor(data.free_total_minutes / 60)}h {data.free_total_minutes % 60}m /
                  backlog {data.backlog_count} 件 /
                  メール {data.pending_email_count} 件
                </span>
              </div>
              <div className="text-sm whitespace-pre-wrap leading-[1.85]">{data.plan}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
