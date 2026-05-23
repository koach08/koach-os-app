"use client";

import { useEffect, useRef, useState } from "react";

type ActiveSession = {
  session_id: string;
  task: string;
  category: string;
  planned_minutes: number;
  started_at: string;
};

type Session = ActiveSession & {
  ended_at?: string;
  actual_minutes?: number;
  note?: string;
  completed?: boolean;
  date?: string;
};

type Today = {
  date: string;
  sessions: Session[];
  total_minutes: number;
  by_category: Record<string, number>;
};

const CATEGORIES: { id: string; label: string; emoji: string }[] = [
  { id: "research", label: "研究", emoji: "🔬" },
  { id: "career", label: "授業/大学", emoji: "💼" },
  { id: "side_project", label: "副プロジェクト", emoji: "🚀" },
  { id: "creative", label: "クリエイティブ", emoji: "🎨" },
  { id: "learning", label: "学習", emoji: "📚" },
  { id: "admin", label: "事務", emoji: "📋" },
  { id: "family", label: "家族", emoji: "👨‍👩‍👧" },
  { id: "health", label: "健康", emoji: "💪" },
  { id: "other", label: "その他", emoji: "✨" },
];

const PRESETS = [25, 50, 90];

export default function FocusPage() {
  const [active, setActive] = useState<ActiveSession | null>(null);
  const [today, setToday] = useState<Today | null>(null);
  const [task, setTask] = useState("");
  const [category, setCategory] = useState("research");
  const [planned, setPlanned] = useState(50);
  const [elapsed, setElapsed] = useState(0);
  const [stopping, setStopping] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const refresh = async () => {
    const [a, t] = await Promise.all([
      fetch("/api/focus/active").then((r) => r.json()),
      fetch("/api/focus/today").then((r) => r.json()),
    ]);
    setActive(a.active ?? null);
    setToday(t);
  };

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (!active) return;
    const tick = () => {
      const start = new Date(active.started_at).getTime();
      const sec = Math.max(0, Math.floor((Date.now() - start) / 1000));
      setElapsed(sec);
      if (sec >= active.planned_minutes * 60 && sec < active.planned_minutes * 60 + 2) {
        try {
          audioRef.current?.play();
        } catch {}
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [active]);

  const start = async () => {
    if (!task.trim()) return;
    const res = await fetch("/api/focus/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task: task.trim(), category, planned_minutes: planned }),
    });
    if (res.ok) {
      const a = await res.json();
      setActive(a);
      setTask("");
    }
  };

  const stop = async (completed: boolean) => {
    if (!active) return;
    setStopping(true);
    try {
      await fetch("/api/focus/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: active.session_id, completed }),
      });
      setActive(null);
      setElapsed(0);
      await refresh();
    } finally {
      setStopping(false);
    }
  };

  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");
  const pct = active ? Math.min(100, (elapsed / (active.planned_minutes * 60)) * 100) : 0;

  return (
    <div className="flex-1 overflow-y-auto">
      <audio ref={audioRef} src="data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=" />
      <div className="px-8 pt-12 pb-8" style={{ background: "radial-gradient(ellipse at top, rgba(16, 185, 129, 0.12), transparent 60%)" }}>
        <div className="max-w-3xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            Focus Timer
          </p>
          <h1 className="text-4xl font-bold tracking-tight">集中セッション</h1>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-3xl mx-auto space-y-6">
          {active ? (
            <div
              className="rounded-3xl p-8 text-center"
              style={{
                background: "linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(20, 184, 166, 0.08) 100%)",
                border: "1px solid rgba(16, 185, 129, 0.3)",
              }}
            >
              <p className="text-xs uppercase tracking-widest" style={{ color: "#10b981" }}>
                進行中
              </p>
              <p className="text-2xl font-medium mt-3">{active.task}</p>
              <p className="text-sm mt-1" style={{ color: "var(--color-text-muted)" }}>
                {active.category} ・ 予定 {active.planned_minutes} 分
              </p>
              <div className="text-7xl font-mono font-bold my-8" style={{ color: "var(--color-text)" }}>
                {mm}:{ss}
              </div>
              <div className="h-2 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
                <div
                  className="h-full transition-all"
                  style={{ width: `${pct}%`, background: pct >= 100 ? "#10b981" : "#34d399" }}
                />
              </div>
              <div className="flex justify-center gap-3 mt-8">
                <button
                  onClick={() => stop(true)}
                  disabled={stopping}
                  className="px-6 py-2.5 rounded-full text-sm font-medium disabled:opacity-50"
                  style={{ background: "#10b981", color: "white" }}
                >
                  完了
                </button>
                <button
                  onClick={() => stop(false)}
                  disabled={stopping}
                  className="px-6 py-2.5 rounded-full text-sm"
                  style={{ background: "transparent", border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}
                >
                  中断
                </button>
              </div>
            </div>
          ) : (
            <div
              className="rounded-3xl p-7 space-y-4"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            >
              <div>
                <label className="block text-xs mb-1.5 uppercase tracking-wider" style={{ color: "var(--color-text-muted)" }}>
                  タスク
                </label>
                <input
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  placeholder="科研費 introduction の骨子"
                  className="w-full px-4 py-2.5 rounded-lg text-sm"
                  style={{
                    background: "var(--color-background)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") start();
                  }}
                />
              </div>
              <div>
                <label className="block text-xs mb-1.5 uppercase tracking-wider" style={{ color: "var(--color-text-muted)" }}>
                  カテゴリ
                </label>
                <div className="flex flex-wrap gap-2">
                  {CATEGORIES.map((c) => (
                    <button
                      key={c.id}
                      onClick={() => setCategory(c.id)}
                      className="px-3 py-1.5 rounded-full text-xs"
                      style={{
                        background: category === c.id ? "var(--color-text)" : "transparent",
                        color: category === c.id ? "var(--color-background)" : "var(--color-text-muted)",
                        border: "1px solid var(--color-border)",
                      }}
                    >
                      <span className="mr-1">{c.emoji}</span>
                      {c.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs mb-1.5 uppercase tracking-wider" style={{ color: "var(--color-text-muted)" }}>
                  時間
                </label>
                <div className="flex gap-2">
                  {PRESETS.map((p) => (
                    <button
                      key={p}
                      onClick={() => setPlanned(p)}
                      className="px-4 py-2 rounded-lg text-sm"
                      style={{
                        background: planned === p ? "var(--color-accent)" : "transparent",
                        color: planned === p ? "white" : "var(--color-text-muted)",
                        border: "1px solid var(--color-border)",
                      }}
                    >
                      {p} 分
                    </button>
                  ))}
                  <input
                    type="number"
                    value={planned}
                    onChange={(e) => setPlanned(Math.max(5, Math.min(180, Number(e.target.value) || 25)))}
                    className="w-20 px-3 py-2 rounded-lg text-sm"
                    style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                  />
                </div>
              </div>
              <button
                onClick={start}
                disabled={!task.trim()}
                className="w-full px-5 py-3 rounded-full text-sm font-medium disabled:opacity-50"
                style={{ background: "var(--color-accent)", color: "white" }}
              >
                スタート
              </button>
            </div>
          )}

          {today && (
            <div
              className="rounded-2xl p-6"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            >
              <header className="flex items-center justify-between mb-4">
                <h2 className="font-semibold">今日の集中</h2>
                <span className="text-xs font-mono" style={{ color: "var(--color-text-muted)" }}>
                  合計 {Math.floor(today.total_minutes / 60)}h {today.total_minutes % 60}m / {today.sessions.length} セッション
                </span>
              </header>
              {Object.entries(today.by_category).length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
                  {Object.entries(today.by_category)
                    .sort((a, b) => b[1] - a[1])
                    .map(([cat, min]) => {
                      const meta = CATEGORIES.find((c) => c.id === cat);
                      return (
                        <div
                          key={cat}
                          className="px-3 py-2 rounded-lg text-xs"
                          style={{ background: "var(--color-surface-hover)" }}
                        >
                          <div style={{ color: "var(--color-text-muted)" }}>
                            {meta?.emoji} {meta?.label ?? cat}
                          </div>
                          <div className="font-mono text-sm mt-0.5">{min} 分</div>
                        </div>
                      );
                    })}
                </div>
              )}
              {today.sessions.length === 0 ? (
                <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                  まだセッションなし
                </p>
              ) : (
                <ul className="space-y-1.5">
                  {today.sessions.map((s, i) => (
                    <li key={i} className="text-sm flex justify-between items-center">
                      <span style={{ opacity: s.completed ? 1 : 0.5 }}>
                        {s.completed ? "✓" : "⊘"} {s.task}
                      </span>
                      <span className="font-mono text-xs" style={{ color: "var(--color-text-muted)" }}>
                        {s.actual_minutes ?? s.planned_minutes} 分
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
