"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PHASES } from "@/lib/training-data";
import { loadProgress } from "@/lib/training-storage";
import type { TrainingProgress } from "@/types/training";
import { Progress } from "@/components/ui/progress";
import { ExportSectionButton } from "@/components/training/export-section-button";
import { EventCreator } from "@/components/event-creator";
import { Shield, ClipboardList, Calendar, CalendarPlus } from "lucide-react";

export default function TrainingDashboard() {
  const [progress, setProgress] = useState<TrainingProgress | null>(null);

  useEffect(() => {
    setProgress(loadProgress());
  }, []);

  const currentPhaseId = progress?.currentPhase ?? 0;
  const phase = PHASES[currentPhaseId];

  const totalExercises = phase.sections.reduce(
    (sum, s) => sum + s.exercises.length,
    0
  );
  const checkedCount = progress
    ? phase.sections.reduce(
        (sum, s, si) =>
          sum +
          s.exercises.filter(
            (_, ei) => progress.checkedItems[`${currentPhaseId}-${si}-${ei}`]
          ).length,
        0
      )
    : 0;
  const progressPercent =
    totalExercises > 0 ? (checkedCount / totalExercises) * 100 : 0;

  const milestoneChecked = progress
    ? phase.milestones.filter(
        (_, mi) => progress.checkedItems[`m-${currentPhaseId}-${mi}`]
      ).length
    : 0;

  // Determine today's sessions based on section name patterns
  const todaySections = phase.sections.filter((s) => {
    const name = s.name;
    if (name.includes("毎朝") || name.includes("朝")) return true;
    if (name.includes("昼")) return true;
    if (name.includes("夜") || name.includes("寝る前")) return true;
    return false;
  });

  return (
    <div className="min-h-screen px-4 py-6">
      <div className="mx-auto max-w-lg">
        {/* Header */}
        <div className="mb-4">
          <p
            className="font-mono text-[10px] uppercase tracking-[4px]"
            style={{ color: phase.color }}
          >
            B-Boy Comeback Plan — 41歳
          </p>
          <h1 className="mt-1 text-2xl font-black">トレーニング</h1>
        </div>

        {/* Phase selector */}
        <div className="mb-4 flex gap-1.5 overflow-x-auto">
          {PHASES.map((p) => (
            <Link
              key={p.id}
              href={`/training/${p.id}`}
              className="flex min-w-0 flex-1 flex-col items-center rounded-lg border-2 px-2 py-2.5 text-center transition-colors"
              style={{
                borderColor:
                  currentPhaseId === p.id ? p.color : "var(--border)",
                background:
                  currentPhaseId === p.id ? `${p.color}12` : "var(--card)",
                color: currentPhaseId === p.id ? p.color : "var(--muted-foreground)",
              }}
            >
              <span className="text-xs font-bold">P{p.id}</span>
              <span className="mt-0.5 text-[9px]">{p.weeks}</span>
            </Link>
          ))}
        </div>

        {/* Current Phase Card */}
        <div
          className="mb-4 rounded-xl border p-4"
          style={{
            borderColor: `${phase.color}33`,
            background: `${phase.color}08`,
          }}
        >
          <div className="flex items-start justify-between">
            <div>
              <p
                className="font-mono text-[10px] tracking-widest"
                style={{ color: phase.color }}
              >
                {phase.weeks}
              </p>
              <h2 className="mt-0.5 text-lg font-black">{phase.title}</h2>
              <p className="text-xs text-muted-foreground">{phase.subtitle}</p>
            </div>
            <div className="text-center">
              <div className="text-2xl font-black" style={{ color: phase.color }}>
                {checkedCount}
              </div>
              <div className="text-[10px] text-muted-foreground">
                / {totalExercises}
              </div>
            </div>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">🎯 {phase.goal}</p>
          <div className="mt-3">
            <Progress
              value={progressPercent}
              className="h-1"
              style={
                {
                  "--progress-color": phase.color,
                } as React.CSSProperties
              }
            />
          </div>
        </div>

        {/* Milestones */}
        <div
          className="mb-4 rounded-xl border p-4"
          style={{ borderColor: `${phase.color}22` }}
        >
          <h3
            className="mb-2 text-sm font-bold"
            style={{ color: phase.color }}
          >
            🏁 マイルストーン ({milestoneChecked}/{phase.milestones.length})
          </h3>
          <div className="space-y-1.5">
            {phase.milestones.map((m, i) => {
              const checked =
                progress?.checkedItems[`m-${currentPhaseId}-${i}`];
              return (
                <div
                  key={i}
                  className="flex items-center gap-2 text-xs"
                >
                  <div
                    className="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full border text-[8px]"
                    style={{
                      borderColor: checked ? phase.color : "var(--border)",
                      background: checked ? phase.color : "transparent",
                      color: checked ? "#fff" : "transparent",
                    }}
                  >
                    ✓
                  </div>
                  <span
                    className={checked ? "line-through opacity-50" : ""}
                    style={{ color: checked ? phase.color : "var(--foreground)" }}
                  >
                    {m}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Today's Menu */}
        {todaySections.length > 0 && (
          <div className="mb-4 rounded-xl border border-border bg-card p-4">
            <h3 className="mb-2 text-sm font-bold text-[var(--color-cat-training)]">
              📋 今日のメニュー
            </h3>
            {todaySections.map((sec, i) => (
              <div key={i} className="mb-3 last:mb-0">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-bold" style={{ color: phase.color }}>
                    {sec.name}
                  </p>
                  <ExportSectionButton
                    section={sec}
                    phaseId={currentPhaseId}
                    phaseColor={phase.color}
                  />
                </div>
                <ul className="mt-1 space-y-0.5">
                  {sec.exercises.map((ex, j) => (
                    <li
                      key={j}
                      className="text-[11px] text-muted-foreground"
                    >
                      {ex.name} — {ex.reps}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}

        {/* Quick Links */}
        <div className="grid grid-cols-4 gap-2">
          <Link
            href={`/training/${currentPhaseId}`}
            className="flex flex-col items-center gap-1.5 rounded-lg border border-border bg-card p-3 transition-colors hover:border-[var(--color-cat-training)]"
          >
            <ClipboardList className="h-5 w-5 text-[var(--color-cat-training)]" />
            <span className="text-[10px] font-bold">Phase詳細</span>
          </Link>
          <Link
            href="/training/schedule"
            className="flex flex-col items-center gap-1.5 rounded-lg border border-border bg-card p-3 transition-colors hover:border-[var(--color-cat-training)]"
          >
            <CalendarPlus className="h-5 w-5 text-[var(--color-cat-training)]" />
            <span className="text-[10px] font-bold">GCal登録</span>
          </Link>
          <Link
            href="/training/safety"
            className="flex flex-col items-center gap-1.5 rounded-lg border border-border bg-card p-3 transition-colors hover:border-[var(--color-cat-deadline)]"
          >
            <Shield className="h-5 w-5 text-[var(--color-cat-deadline)]" />
            <span className="text-[10px] font-bold">怪我予防</span>
          </Link>
          <Link
            href="/training/log"
            className="flex flex-col items-center gap-1.5 rounded-lg border border-border bg-card p-3 transition-colors hover:border-[var(--color-cat-research)]"
          >
            <Calendar className="h-5 w-5 text-[var(--color-cat-research)]" />
            <span className="text-[10px] font-bold">ログ</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
