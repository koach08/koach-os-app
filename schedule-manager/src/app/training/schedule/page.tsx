"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSession, signIn } from "next-auth/react";
import { format, addDays, startOfWeek, addWeeks } from "date-fns";
import { ja } from "date-fns/locale";
import {
  getDefaultTemplates,
  generateCalendarEvents,
  DAY_LABELS,
  SESSION_LABELS,
} from "@/lib/training-scheduler";
import { PHASES } from "@/lib/training-data";
import { loadProgress } from "@/lib/training-storage";
import type { TrainingScheduleTemplate } from "@/types/training";
import { Button } from "@/components/ui/button";
import {
  ChevronLeft,
  CalendarPlus,
  AlertTriangle,
  Check,
  Loader2,
  LogIn,
} from "lucide-react";

type SessionType = TrainingScheduleTemplate["sessions"][number]["type"];

export default function SchedulePage() {
  const { data: session } = useSession();
  const [templates, setTemplates] = useState<TrainingScheduleTemplate[]>(
    getDefaultTemplates
  );
  const [phaseId, setPhaseId] = useState(0);
  const [weeks, setWeeks] = useState(1);
  const [showPreview, setShowPreview] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [checkingConflicts, setCheckingConflicts] = useState(false);
  const [conflicts, setConflicts] = useState<
    { proposed: { summary: string }; conflictsWith: { summary: string; start: string }[] }[]
  >([]);
  const [result, setResult] = useState<{ created: number } | null>(null);

  useEffect(() => {
    const progress = loadProgress();
    setPhaseId(progress.currentPhase);
  }, []);

  const phase = PHASES[phaseId];
  const startDate = startOfWeek(addDays(new Date(), 1), { weekStartsOn: 1 });
  const previewEvents = generateCalendarEvents(templates, phaseId, startDate, weeks);

  const toggleSession = (dayOfWeek: number, sessionType: SessionType) => {
    setTemplates((prev) =>
      prev.map((t) =>
        t.dayOfWeek === dayOfWeek
          ? {
              ...t,
              sessions: t.sessions.map((s) =>
                s.type === sessionType ? { ...s, enabled: !s.enabled } : s
              ),
            }
          : t
      )
    );
    setResult(null);
  };

  const updateTime = (dayOfWeek: number, sessionType: SessionType, time: string) => {
    setTemplates((prev) =>
      prev.map((t) =>
        t.dayOfWeek === dayOfWeek
          ? {
              ...t,
              sessions: t.sessions.map((s) =>
                s.type === sessionType ? { ...s, startTime: time } : s
              ),
            }
          : t
      )
    );
  };

  const handleCheckConflicts = async () => {
    if (!session?.accessToken) return;
    setCheckingConflicts(true);
    setConflicts([]);
    try {
      const res = await fetch("/api/calendar/conflicts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: previewEvents }),
      });
      if (res.ok) {
        const data = await res.json();
        setConflicts(data.conflicts || []);
      }
    } catch {
      // silently fail
    } finally {
      setCheckingConflicts(false);
    }
  };

  const handleRegister = async () => {
    if (!session?.accessToken) return;
    setRegistering(true);
    setResult(null);
    try {
      const res = await fetch("/api/calendar/training", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: previewEvents }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult({ created: data.created });
      }
    } catch {
      // silently fail
    } finally {
      setRegistering(false);
    }
  };

  const sessionTypes: SessionType[] = [
    "morning",
    "noon",
    "evening",
    "workout",
    "breaking",
    "acrobat",
  ];

  // Order days: Mon(1) - Sun(0)
  const dayOrder = [1, 2, 3, 4, 5, 6, 0];

  return (
    <div className="min-h-screen px-3 py-4">
      <div className="mx-auto max-w-lg">
        <Link
          href="/training"
          className="mb-3 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-4 w-4" />
          トレーニングに戻る
        </Link>

        <h1 className="mb-1 text-xl font-black">📅 スケジュール設定</h1>
        <p className="mb-4 text-xs text-muted-foreground">
          曜日×時間帯を設定 → Google Calendarに一括登録
        </p>

        {/* Phase & Weeks selector */}
        <div className="mb-4 flex gap-3">
          <div className="flex-1">
            <label className="mb-1 block text-[10px] font-bold text-muted-foreground">
              Phase
            </label>
            <select
              value={phaseId}
              onChange={(e) => setPhaseId(Number(e.target.value))}
              className="w-full rounded-md border border-border bg-card px-2 py-1.5 text-sm"
            >
              {PHASES.map((p) => (
                <option key={p.id} value={p.id}>
                  P{p.id}: {p.title.replace(`Phase ${p.id}: `, "")}
                </option>
              ))}
            </select>
          </div>
          <div className="w-24">
            <label className="mb-1 block text-[10px] font-bold text-muted-foreground">
              期間
            </label>
            <select
              value={weeks}
              onChange={(e) => setWeeks(Number(e.target.value))}
              className="w-full rounded-md border border-border bg-card px-2 py-1.5 text-sm"
            >
              <option value={1}>1週間</option>
              <option value={2}>2週間</option>
              <option value={4}>1ヶ月</option>
            </select>
          </div>
        </div>

        {/* Schedule grid */}
        <div className="mb-4 overflow-x-auto rounded-xl border border-border bg-card">
          <table className="w-full text-[10px]">
            <thead>
              <tr className="border-b border-border">
                <th className="px-2 py-2 text-left font-bold text-muted-foreground">
                  セッション
                </th>
                {dayOrder.map((d) => (
                  <th
                    key={d}
                    className={`px-1.5 py-2 text-center font-bold ${
                      d === 0 || d === 6
                        ? "text-[var(--color-cat-training)]"
                        : "text-muted-foreground"
                    }`}
                  >
                    {DAY_LABELS[d]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sessionTypes.map((type) => {
                const info = SESSION_LABELS[type];
                return (
                  <tr key={type} className="border-b border-border/50 last:border-b-0">
                    <td className="px-2 py-2">
                      <div className="flex items-center gap-1">
                        <span>{info.emoji}</span>
                        <span className="font-medium" style={{ color: info.color }}>
                          {info.label}
                        </span>
                      </div>
                    </td>
                    {dayOrder.map((d) => {
                      const template = templates.find((t) => t.dayOfWeek === d);
                      const sess = template?.sessions.find((s) => s.type === type);
                      return (
                        <td key={d} className="px-1 py-1.5 text-center">
                          <button
                            onClick={() => toggleSession(d, type)}
                            className="mx-auto flex h-7 w-7 items-center justify-center rounded-md border transition-colors"
                            style={{
                              borderColor: sess?.enabled
                                ? info.color
                                : "var(--border)",
                              background: sess?.enabled
                                ? `${info.color}22`
                                : "transparent",
                              color: sess?.enabled ? info.color : "var(--muted-foreground)",
                            }}
                          >
                            {sess?.enabled ? "✓" : ""}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Time settings (collapsible per session type) */}
        <div className="mb-4 space-y-2">
          <h3 className="text-xs font-bold text-muted-foreground">開始時間</h3>
          {sessionTypes.map((type) => {
            const info = SESSION_LABELS[type];
            // Find a representative time from the first enabled template
            const enabledTemplate = templates.find((t) =>
              t.sessions.some((s) => s.type === type && s.enabled)
            );
            const time =
              enabledTemplate?.sessions.find((s) => s.type === type)?.startTime || "06:30";

            const hasEnabled = templates.some((t) =>
              t.sessions.some((s) => s.type === type && s.enabled)
            );
            if (!hasEnabled) return null;

            return (
              <div key={type} className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2">
                <span className="text-sm">{info.emoji}</span>
                <span className="flex-1 text-xs font-medium" style={{ color: info.color }}>
                  {info.label}
                </span>
                <input
                  type="time"
                  value={time}
                  onChange={(e) => {
                    dayOrder.forEach((d) => updateTime(d, type, e.target.value));
                  }}
                  className="rounded border border-border bg-background px-2 py-1 font-mono text-xs"
                />
              </div>
            );
          })}
        </div>

        {/* Preview */}
        <div className="mb-4">
          <button
            onClick={() => setShowPreview(!showPreview)}
            className="mb-2 text-xs font-bold text-[var(--color-cat-research)] hover:underline"
          >
            {showPreview ? "▲ プレビューを閉じる" : "▼ プレビュー表示"} ({previewEvents.length}件)
          </button>

          {showPreview && (
            <div className="max-h-60 space-y-1 overflow-y-auto rounded-xl border border-border bg-card p-3">
              {previewEvents.map((event, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 rounded-md px-2 py-1.5 text-[11px]"
                >
                  <div className="h-2 w-2 flex-shrink-0 rounded-full bg-[var(--color-cat-training)]" />
                  <span className="flex-1 truncate font-medium">
                    {event.summary}
                  </span>
                  <span className="flex-shrink-0 font-mono text-[9px] text-muted-foreground">
                    {format(new Date(event.start.dateTime), "M/d（E） HH:mm", {
                      locale: ja,
                    })}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Conflicts */}
        {conflicts.length > 0 && (
          <div className="mb-4 rounded-xl border border-[var(--color-cat-deadline)]/30 bg-[var(--color-cat-deadline)]/5 p-3">
            <h3 className="mb-2 flex items-center gap-1.5 text-xs font-bold text-[var(--color-cat-deadline)]">
              <AlertTriangle className="h-3.5 w-3.5" />
              衝突あり ({conflicts.length}件)
            </h3>
            {conflicts.map((c, i) => (
              <div key={i} className="mb-1.5 text-[11px] last:mb-0">
                <span className="font-medium">{c.proposed.summary}</span>
                <span className="text-muted-foreground">
                  {" "}
                  ← {c.conflictsWith.map((x) => x.summary).join(", ")}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Result */}
        {result && (
          <div className="mb-4 rounded-xl border border-[var(--color-cat-growth)]/30 bg-[var(--color-cat-growth)]/5 p-3">
            <p className="flex items-center gap-1.5 text-xs font-bold text-[var(--color-cat-growth)]">
              <Check className="h-3.5 w-3.5" />
              {result.created}件のイベントを登録しました
            </p>
          </div>
        )}

        {/* Action buttons */}
        {!session?.accessToken ? (
          <Button
            onClick={() => signIn("google")}
            className="w-full gap-2"
            variant="outline"
          >
            <LogIn className="h-4 w-4" />
            Googleでログインして登録
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button
              onClick={handleCheckConflicts}
              variant="outline"
              className="flex-1 gap-1.5 text-xs"
              disabled={checkingConflicts || previewEvents.length === 0}
            >
              {checkingConflicts ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <AlertTriangle className="h-3.5 w-3.5" />
              )}
              衝突チェック
            </Button>
            <Button
              onClick={handleRegister}
              className="flex-1 gap-1.5 bg-[var(--color-cat-training)] text-xs text-white hover:bg-[var(--color-cat-training)]/80"
              disabled={registering || previewEvents.length === 0}
            >
              {registering ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <CalendarPlus className="h-3.5 w-3.5" />
              )}
              GCalに登録 ({previewEvents.length}件)
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
