"use client";

import { useEffect, useState } from "react";
import { PHASES } from "@/lib/training-data";
import type { Section, Exercise, Phase } from "@/lib/training-types";

type LogEntry = {
  date: string;
  weight?: number | null;
  body_fat?: number | null;
  notes?: string | null;
};

type Progress = {
  checkedItems: Record<string, boolean>;
  currentPhase: number;
  logs: LogEntry[];
};

function exerciseKey(phaseId: number, sectionIdx: number, exIdx: number): string {
  return `p${phaseId}_s${sectionIdx}_e${exIdx}`;
}

export default function TrainingPage() {
  const [progress, setProgress] = useState<Progress | null>(null);
  const [activePhaseId, setActivePhaseId] = useState<number>(0);
  const [showLogForm, setShowLogForm] = useState(false);
  const [weight, setWeight] = useState("");
  const [bodyFat, setBodyFat] = useState("");
  const [notes, setNotes] = useState("");

  const load = () => {
    fetch("/api/training/progress")
      .then((r) => r.json())
      .then((d) => {
        const checked = (d.checked_items as Record<string, boolean>) ?? {};
        setProgress({
          checkedItems: checked,
          currentPhase: d.current_phase ?? 0,
          logs: d.logs ?? [],
        });
        setActivePhaseId(d.current_phase ?? 0);
      });
  };

  useEffect(() => {
    load();
  }, []);

  const toggleCheck = async (key: string) => {
    if (!progress) return;
    const next = !progress.checkedItems[key];
    setProgress({ ...progress, checkedItems: { ...progress.checkedItems, [key]: next } });
    await fetch("/api/training/progress", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ checked_items: { [key]: next } }),
    });
  };

  const handlePhaseChange = async (phaseId: number) => {
    setActivePhaseId(phaseId);
    if (progress?.currentPhase !== phaseId) {
      await fetch("/api/training/progress", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_phase: phaseId }),
      });
      load();
    }
  };

  const handleSaveLog = async () => {
    if (!weight && !bodyFat && !notes.trim()) return;
    await fetch("/api/training/progress", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        weight: weight ? Number(weight) : null,
        body_fat: bodyFat ? Number(bodyFat) : null,
        notes: notes || null,
      }),
    });
    setWeight("");
    setBodyFat("");
    setNotes("");
    setShowLogForm(false);
    load();
  };

  const activePhase = PHASES.find((p) => p.id === activePhaseId);

  // Progress per phase
  const phaseProgress = (phaseId: number) => {
    if (!progress) return 0;
    const phase = PHASES.find((p) => p.id === phaseId);
    if (!phase) return 0;
    let total = 0;
    let checked = 0;
    phase.sections.forEach((s: Section, si: number) => {
      s.exercises.forEach((_, ei: number) => {
        total += 1;
        if (progress.checkedItems[exerciseKey(phaseId, si, ei)]) checked += 1;
      });
    });
    return total > 0 ? Math.round((checked / total) * 100) : 0;
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div
        className="px-8 pt-10 pb-6 relative"
        style={{
          background:
            "radial-gradient(ellipse at top right, rgba(239, 68, 68, 0.10), transparent 50%)",
        }}
      >
        <div className="max-w-5xl mx-auto flex items-end justify-between flex-wrap gap-4">
          <div>
            <h1
              className="text-4xl font-bold tracking-tight"
              style={{
                background: "linear-gradient(90deg, #fafafa 0%, #fb7185 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              Training
            </h1>
            <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>
              フェーズベースのトレーニングプログラム
            </p>
          </div>
          <button
            onClick={() => setShowLogForm(!showLogForm)}
            className="px-5 py-2.5 rounded-full text-sm font-medium transition-all hover:scale-[1.02]"
            style={{ background: "var(--color-accent)", color: "white" }}
          >
            {showLogForm ? "閉じる" : "+ ログ記録"}
          </button>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-5xl mx-auto space-y-5">
          {/* Log form */}
          {showLogForm && (
            <div
              className="rounded-2xl p-5 grid grid-cols-1 md:grid-cols-3 gap-3"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            >
              <input
                type="number"
                step="0.1"
                placeholder="体重 (kg)"
                value={weight}
                onChange={(e) => setWeight(e.target.value)}
                className="px-3 py-2 rounded-lg text-sm"
                style={{
                  background: "var(--color-background)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text)",
                }}
              />
              <input
                type="number"
                step="0.1"
                placeholder="体脂肪率 (%)"
                value={bodyFat}
                onChange={(e) => setBodyFat(e.target.value)}
                className="px-3 py-2 rounded-lg text-sm"
                style={{
                  background: "var(--color-background)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text)",
                }}
              />
              <button
                onClick={handleSaveLog}
                className="px-4 py-2 rounded-lg text-sm font-medium"
                style={{ background: "var(--color-accent)", color: "white" }}
              >
                保存
              </button>
              <textarea
                placeholder="メモ（今日の調子、達成感など）"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={2}
                className="md:col-span-3 px-3 py-2 rounded-lg text-sm resize-none"
                style={{
                  background: "var(--color-background)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text)",
                }}
              />
            </div>
          )}

          {/* Phase tabs */}
          <div className="flex gap-2 overflow-x-auto pb-1">
            {PHASES.map((p: Phase) => {
              const active = activePhaseId === p.id;
              const pct = phaseProgress(p.id);
              return (
                <button
                  key={p.id}
                  onClick={() => handlePhaseChange(p.id)}
                  className="px-4 py-2 rounded-xl text-left transition-all whitespace-nowrap"
                  style={{
                    background: active ? "var(--color-surface-hover)" : "var(--color-surface)",
                    border: active
                      ? `1px solid ${p.color}`
                      : "1px solid var(--color-border)",
                    minWidth: "200px",
                  }}
                >
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
                    <div className="font-medium text-sm">{p.title}</div>
                  </div>
                  <div className="text-[10px] mt-0.5" style={{ color: "var(--color-text-muted)" }}>
                    {p.weeks} · {pct}% 完了
                  </div>
                </button>
              );
            })}
          </div>

          {/* Active phase content */}
          {activePhase && progress && (
            <div className="space-y-4">
              {/* Phase summary card */}
              <div
                className="rounded-2xl p-5"
                style={{
                  background: `linear-gradient(135deg, ${activePhase.color}15, transparent 80%)`,
                  border: `1px solid ${activePhase.color}40`,
                }}
              >
                <h2 className="text-xl font-bold">{activePhase.title}</h2>
                <p className="text-sm mt-1" style={{ color: "var(--color-text-muted)" }}>
                  {activePhase.subtitle}
                </p>
                <p className="text-sm mt-2 font-medium" style={{ color: activePhase.color }}>
                  目標: {activePhase.goal}
                </p>
                {activePhase.milestones.length > 0 && (
                  <div className="mt-3 pt-3 text-xs" style={{ borderTop: `1px solid ${activePhase.color}30` }}>
                    <div className="font-semibold mb-1" style={{ color: "var(--color-text-muted)" }}>
                      Milestones
                    </div>
                    <ul className="space-y-0.5" style={{ color: "var(--color-text-muted)" }}>
                      {activePhase.milestones.map((m: string, i: number) => (
                        <li key={i}>• {m}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Sections */}
              {activePhase.sections.map((section: Section, sIdx: number) => (
                <div
                  key={sIdx}
                  className="rounded-2xl p-5"
                  style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
                >
                  <h3 className="font-semibold mb-3">{section.name}</h3>
                  <ul className="space-y-2">
                    {section.exercises.map((ex: Exercise, eIdx: number) => {
                      const key = exerciseKey(activePhase.id, sIdx, eIdx);
                      const checked = progress.checkedItems[key] || false;
                      return (
                        <li key={eIdx} className="flex items-start gap-3">
                          <button
                            onClick={() => toggleCheck(key)}
                            className="shrink-0 w-5 h-5 rounded mt-0.5 transition-colors"
                            style={{
                              background: checked ? "var(--color-green)" : "transparent",
                              border: checked
                                ? "1px solid var(--color-green)"
                                : "1px solid var(--color-border-light)",
                              color: "white",
                            }}
                          >
                            {checked ? "✓" : ""}
                          </button>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span
                                className="font-medium text-sm"
                                style={{
                                  textDecoration: checked ? "line-through" : "none",
                                  color: checked ? "var(--color-text-muted)" : "var(--color-text)",
                                }}
                              >
                                {ex.name}
                              </span>
                              <span
                                className="text-xs font-mono"
                                style={{ color: "var(--color-text-muted)" }}
                              >
                                {ex.reps}
                              </span>
                              {ex.video && (
                                <a
                                  href={ex.video}
                                  target="_blank"
                                  rel="noopener"
                                  className="text-xs px-2 py-0.5 rounded-full"
                                  style={{
                                    background: "rgba(239, 68, 68, 0.12)",
                                    color: "#ef4444",
                                  }}
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  ▶ 動画
                                </a>
                              )}
                            </div>
                            {ex.note && (
                              <p
                                className="text-xs mt-0.5"
                                style={{ color: "var(--color-text-muted)" }}
                              >
                                {ex.note}
                              </p>
                            )}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}

              {/* Recent logs */}
              {progress.logs.length > 0 && (
                <div
                  className="rounded-2xl p-5"
                  style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
                >
                  <h3 className="font-semibold mb-3">最近のログ</h3>
                  <ul className="space-y-2">
                    {progress.logs.slice(-5).reverse().map((log: LogEntry, i: number) => (
                      <li
                        key={i}
                        className="flex items-center gap-3 text-sm pb-2"
                        style={{ borderBottom: "1px solid var(--color-border)" }}
                      >
                        <span className="font-mono text-xs" style={{ color: "var(--color-text-muted)" }}>
                          {log.date}
                        </span>
                        {log.weight && <span>体重 {log.weight}kg</span>}
                        {log.body_fat && <span>体脂肪 {log.body_fat}%</span>}
                        {log.notes && (
                          <span style={{ color: "var(--color-text-muted)" }}>· {log.notes}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
