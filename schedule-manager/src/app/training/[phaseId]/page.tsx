"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { PHASES } from "@/lib/training-data";
import {
  loadProgress,
  toggleExercise,
  saveProgress,
} from "@/lib/training-storage";
import type { TrainingProgress } from "@/types/training";
import { Progress } from "@/components/ui/progress";
import { ExportSectionButton } from "@/components/training/export-section-button";
import { ChevronLeft, ExternalLink, Smartphone } from "lucide-react";

export default function PhaseDetailPage() {
  const params = useParams();
  const phaseId = Number(params.phaseId);
  const phase = PHASES[phaseId];
  const [progress, setProgress] = useState<TrainingProgress | null>(null);

  useEffect(() => {
    setProgress(loadProgress());
  }, []);

  if (!phase) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p>Phase not found</p>
      </div>
    );
  }

  const totalExercises = phase.sections.reduce(
    (sum, s) => sum + s.exercises.length,
    0
  );
  const checkedCount = progress
    ? phase.sections.reduce(
        (sum, s, si) =>
          sum +
          s.exercises.filter(
            (_, ei) => progress.checkedItems[`${phaseId}-${si}-${ei}`]
          ).length,
        0
      )
    : 0;
  const progressPercent =
    totalExercises > 0 ? (checkedCount / totalExercises) * 100 : 0;

  const handleToggle = (key: string) => {
    const updated = toggleExercise(key);
    setProgress({ ...updated });
  };

  const handleMilestoneToggle = (key: string) => {
    if (!progress) return;
    const updated = { ...progress };
    updated.checkedItems[key] = !updated.checkedItems[key];
    saveProgress(updated);
    setProgress({ ...updated });
  };

  return (
    <div className="min-h-screen px-3 py-4">
      <div className="mx-auto max-w-lg">
        {/* Back + Phase nav */}
        <div className="mb-3 flex items-center gap-2">
          <Link
            href="/training"
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <ChevronLeft className="h-4 w-4" />
            戻る
          </Link>
        </div>

        {/* Phase tabs */}
        <div className="mb-3 flex gap-1">
          {PHASES.map((p) => (
            <Link
              key={p.id}
              href={`/training/${p.id}`}
              className="flex flex-1 flex-col items-center rounded-lg border-2 px-1 py-2 text-center transition-colors"
              style={{
                borderColor: phaseId === p.id ? p.color : "var(--border)",
                background:
                  phaseId === p.id ? `${p.color}18` : "var(--card)",
                color:
                  phaseId === p.id ? p.color : "var(--muted-foreground)",
              }}
            >
              <span className="text-[10px] font-bold">P{p.id}</span>
              <span className="text-[8px]">{p.weeks}</span>
            </Link>
          ))}
        </div>

        {/* Phase header */}
        <div
          className="mb-3 rounded-xl border p-4"
          style={{
            borderColor: `${phase.color}22`,
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
              <h1 className="text-lg font-black">{phase.title}</h1>
              <p className="text-xs text-muted-foreground">{phase.subtitle}</p>
            </div>
            <div className="text-center">
              <div
                className="text-xl font-black"
                style={{ color: phase.color }}
              >
                {checkedCount}
              </div>
              <div className="text-[10px] text-muted-foreground">
                / {totalExercises}
              </div>
            </div>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">
            🎯 {phase.goal}
          </p>
          <div className="mt-2.5">
            <Progress value={progressPercent} className="h-0.5" />
          </div>
        </div>

        {/* Exercise Sections */}
        <div className="space-y-3">
          {phase.sections.map((sec, si) => (
            <div
              key={si}
              className="overflow-hidden rounded-xl border border-border bg-card"
            >
              <div
                className="flex items-center justify-between border-b border-border px-3 py-2.5"
                style={{ background: `${phase.color}08` }}
              >
                <h3
                  className="text-[13px] font-bold"
                  style={{ color: phase.color }}
                >
                  {sec.name}
                </h3>
                <ExportSectionButton
                  section={sec}
                  phaseId={phaseId}
                  phaseColor={phase.color}
                />
              </div>
              <div>
                {sec.exercises.map((ex, ei) => {
                  const key = `${phaseId}-${si}-${ei}`;
                  const checked = progress?.checkedItems[key] ?? false;
                  return (
                    <div
                      key={ei}
                      className="border-b border-border/50 px-3 py-2.5 last:border-b-0 transition-opacity"
                      style={{ opacity: checked ? 0.4 : 1 }}
                    >
                      <div className="flex items-start gap-2.5">
                        {/* Checkbox */}
                        <button
                          onClick={() => handleToggle(key)}
                          className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded border-2 text-[10px] transition-colors"
                          style={{
                            borderColor: checked
                              ? phase.color
                              : "var(--border)",
                            background: checked
                              ? `${phase.color}33`
                              : "transparent",
                            color: phase.color,
                          }}
                        >
                          {checked && "✓"}
                        </button>

                        <div className="min-w-0 flex-1">
                          <div className="flex items-baseline justify-between gap-2">
                            <span
                              className={`text-[13px] font-bold ${
                                checked ? "line-through" : ""
                              }`}
                            >
                              {ex.name}
                            </span>
                            <span
                              className="flex-shrink-0 text-[11px] font-semibold"
                              style={{ color: phase.color }}
                            >
                              {ex.reps}
                            </span>
                          </div>
                          <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">
                            {ex.note}
                          </p>
                          {ex.video ? (
                            <a
                              href={ex.video}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="mt-1.5 inline-flex items-center gap-1 rounded border border-[#2a1a2e] bg-[#1a1220] px-2.5 py-1 text-[11px] text-[#ff4466] no-underline"
                            >
                              <ExternalLink className="h-3 w-3" />
                              YouTube参考動画
                            </a>
                          ) : ex.note?.includes("Kajabi") ? (
                            <span className="mt-1.5 inline-flex items-center gap-1 rounded border border-[#2a2a1e] bg-[#1a1a12] px-2.5 py-1 text-[11px] text-[#aaaa44]">
                              <Smartphone className="h-3 w-3" />
                              HD Kajabiアプリで視聴
                            </span>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Milestones */}
        <div
          className="mt-4 rounded-xl border p-4"
          style={{ borderColor: `${phase.color}22` }}
        >
          <h3
            className="mb-3 text-[13px] font-bold"
            style={{ color: phase.color }}
          >
            🏁 達成マイルストーン
          </h3>
          {phase.milestones.map((m, mi) => {
            const key = `m-${phaseId}-${mi}`;
            const checked = progress?.checkedItems[key] ?? false;
            return (
              <button
                key={mi}
                onClick={() => handleMilestoneToggle(key)}
                className="flex w-full items-center gap-2.5 border-b border-border/50 py-2 last:border-b-0"
              >
                <div
                  className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border-2 text-[10px]"
                  style={{
                    borderColor: checked ? phase.color : "var(--border)",
                    background: checked ? phase.color : "transparent",
                    color: checked ? "#fff" : "transparent",
                  }}
                >
                  ✓
                </div>
                <span
                  className={`text-[13px] font-semibold ${
                    checked ? "line-through opacity-50" : ""
                  }`}
                  style={{
                    color: checked ? phase.color : "var(--foreground)",
                  }}
                >
                  {m}
                </span>
              </button>
            );
          })}
        </div>

        {/* Footer warning */}
        <div className="mt-4 border-t border-border pt-4 pb-8 text-[11px] leading-relaxed text-[#3a4455]">
          ⚠️
          バク転・バク宙はマット上・スポッター付き推奨。脈拍40bpmは循環器内科で確認を。痛みが出たら即中止。41歳の身体は10代と回復速度が違う。毎日15分のルーティンだけは継続が鍵。
        </div>
      </div>
    </div>
  );
}
