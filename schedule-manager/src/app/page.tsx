"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSession, signIn } from "next-auth/react";
import { format, startOfWeek, endOfWeek, addDays, isToday, isBefore } from "date-fns";
import { ja } from "date-fns/locale";
import { PHASES } from "@/lib/training-data";
import { loadProgress } from "@/lib/training-storage";
import { classifyEvent, CATEGORIES } from "@/lib/categories";
import type { TrainingProgress } from "@/types/training";
import {
  Dumbbell,
  FileUp,
  ScanSearch,
  Settings,
  CalendarDays,
  CalendarPlus,
  AlertTriangle,
  LogIn,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { EventCreator } from "@/components/event-creator";
import { MemoNotes } from "@/components/memo-notes";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

interface CalendarEvent {
  id: string;
  summary: string;
  description?: string;
  start: { dateTime?: string; date?: string };
  end: { dateTime?: string; date?: string };
  colorId?: string;
}

export default function DashboardPage() {
  const { data: session, status } = useSession();
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<TrainingProgress | null>(null);

  useEffect(() => {
    setProgress(loadProgress());
  }, []);

  useEffect(() => {
    if (session?.accessToken) {
      fetchEvents();
    }
  }, [session]);

  const fetchEvents = async () => {
    setLoading(true);
    try {
      const now = new Date();
      const weekEnd = endOfWeek(now, { weekStartsOn: 1 });
      const res = await fetch(
        `/api/calendar/events?timeMin=${now.toISOString()}&timeMax=${weekEnd.toISOString()}`
      );
      if (res.ok) {
        const data = await res.json();
        setEvents(data.events || []);
      }
    } catch {
      // Silently fail - will show empty state
    } finally {
      setLoading(false);
    }
  };

  const currentPhaseId = progress?.currentPhase ?? 0;
  const phase = PHASES[currentPhaseId];

  // Today's training sections
  const todaySections = phase.sections.filter((s) => {
    const name = s.name;
    return name.includes("朝") || name.includes("昼") || name.includes("夜");
  });

  // Deadline events (within next 7 days)
  const deadlineEvents = events.filter((e) => {
    const cat = classifyEvent(e.summary || "", e.description);
    return cat.id === "deadline";
  });

  // Group events by category for summary
  const categorySummary = CATEGORIES.map((cat) => {
    const catEvents = events.filter(
      (e) => classifyEvent(e.summary || "", e.description).id === cat.id
    );
    const totalMinutes = catEvents.reduce((sum, e) => {
      const start = new Date(e.start.dateTime || e.start.date || "");
      const end = new Date(e.end.dateTime || e.end.date || "");
      return sum + (end.getTime() - start.getTime()) / 60000;
    }, 0);
    return { ...cat, count: catEvents.length, hours: Math.round(totalMinutes / 60 * 10) / 10 };
  }).filter((c) => c.count > 0);

  return (
    <div className="min-h-screen px-4 py-6">
      <div className="mx-auto max-w-lg">
        {/* Header */}
        <div className="mb-5 flex items-start justify-between">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[4px] text-muted-foreground">
              Schedule Manager
            </p>
            <h1 className="mt-1 text-2xl font-black">ダッシュボード</h1>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {format(new Date(), "yyyy年M月d日（E）", { locale: ja })}
          </p>
          </div>
          <EventCreator
            onCreated={fetchEvents}
            trigger={
              <button className="flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-xs font-bold transition-colors hover:border-[var(--color-cat-growth)]">
                <CalendarPlus className="h-4 w-4 text-[var(--color-cat-growth)]" />
                予定追加
              </button>
            }
          />
        </div>

        {/* Auth status */}
        {status === "unauthenticated" && (
          <button
            onClick={() => signIn("google")}
            className="mb-4 flex w-full items-center gap-2 rounded-xl border border-border bg-card p-4 transition-colors hover:border-[var(--color-cat-research)]"
          >
            <LogIn className="h-5 w-5 text-[var(--color-cat-research)]" />
            <div className="text-left">
              <p className="text-sm font-bold">Googleでログイン</p>
              <p className="text-[10px] text-muted-foreground">
                カレンダー連携を有効にする
              </p>
            </div>
          </button>
        )}

        {/* Deadline alerts */}
        {deadlineEvents.length > 0 && (
          <div className="mb-4 rounded-xl border border-[var(--color-cat-deadline)]/30 bg-[var(--color-cat-deadline)]/5 p-3">
            <h3 className="mb-2 flex items-center gap-1.5 text-xs font-bold text-[var(--color-cat-deadline)]">
              <AlertTriangle className="h-3.5 w-3.5" />
              直近の締切 ({deadlineEvents.length})
            </h3>
            {deadlineEvents.slice(0, 3).map((e) => (
              <div key={e.id} className="mb-1 flex items-center justify-between text-[11px] last:mb-0">
                <span className="truncate pr-2">{e.summary}</span>
                <span className="flex-shrink-0 font-mono text-[10px] text-muted-foreground">
                  {e.start.dateTime
                    ? format(new Date(e.start.dateTime), "M/d HH:mm")
                    : e.start.date
                    ? format(new Date(e.start.date), "M/d")
                    : ""}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Today's training widget */}
        <div className="mb-4 rounded-xl border border-border bg-card p-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="flex items-center gap-1.5 text-sm font-bold text-[var(--color-cat-training)]">
              <Dumbbell className="h-4 w-4" />
              今日のトレーニング
            </h3>
            <Link
              href={`/training/${currentPhaseId}`}
              className="text-[10px] text-muted-foreground hover:text-foreground"
            >
              Phase {currentPhaseId} →
            </Link>
          </div>
          {todaySections.map((sec, i) => (
            <div key={i} className="mb-2 last:mb-0">
              <p className="text-[11px] font-bold" style={{ color: phase.color }}>
                {sec.name}
              </p>
              <ul className="mt-0.5 space-y-0">
                {sec.exercises.map((ex, j) => (
                  <li key={j} className="text-[10px] text-muted-foreground">
                    {ex.name} — {ex.reps}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Calendar events */}
        {session?.accessToken && (
          <div className="mb-4 rounded-xl border border-border bg-card p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="flex items-center gap-1.5 text-sm font-bold">
                <CalendarDays className="h-4 w-4 text-[var(--color-cat-research)]" />
                今週の予定
              </h3>
              {loading && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
            </div>
            {events.length === 0 && !loading ? (
              <p className="text-xs text-muted-foreground">予定なし</p>
            ) : (
              <div className="space-y-1">
                {events.slice(0, 8).map((e) => {
                  const cat = classifyEvent(e.summary || "", e.description);
                  return (
                    <div
                      key={e.id}
                      className="flex items-center gap-2 rounded-md px-2 py-1.5"
                    >
                      <div
                        className="h-2 w-2 flex-shrink-0 rounded-full"
                        style={{ background: cat.color }}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[11px] font-medium">
                          {e.summary}
                        </p>
                      </div>
                      <span className="flex-shrink-0 font-mono text-[9px] text-muted-foreground">
                        {e.start.dateTime
                          ? format(new Date(e.start.dateTime), "E HH:mm", {
                              locale: ja,
                            })
                          : e.start.date
                          ? format(new Date(e.start.date), "M/d（E）", {
                              locale: ja,
                            })
                          : ""}
                      </span>
                    </div>
                  );
                })}
                {events.length > 8 && (
                  <p className="text-center text-[10px] text-muted-foreground">
                    他 {events.length - 8} 件
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Category time summary chart */}
        {categorySummary.length > 0 && (
          <div className="mb-4 rounded-xl border border-border bg-card p-4">
            <h3 className="mb-3 text-sm font-bold">📊 今週の時間配分</h3>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart
                data={categorySummary}
                layout="vertical"
                margin={{ left: 0, right: 8, top: 0, bottom: 0 }}
              >
                <XAxis
                  type="number"
                  tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                  stroke="var(--border)"
                  unit="h"
                />
                <YAxis
                  type="category"
                  dataKey="label"
                  tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                  stroke="var(--border)"
                  width={80}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--card)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    fontSize: 11,
                  }}
                  formatter={(value) => [`${value}h`, "時間"]}
                />
                <Bar dataKey="hours" radius={[0, 4, 4, 0]} barSize={16}>
                  {categorySummary.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
              {categorySummary.map((cat) => (
                <div key={cat.id} className="flex items-center gap-1.5">
                  <div
                    className="h-2 w-2 rounded-full"
                    style={{ background: cat.color }}
                  />
                  <span className="font-mono text-[9px] text-muted-foreground">
                    {cat.label} {cat.count}件/{cat.hours}h
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Memo notes */}
        <div className="mb-4">
          <MemoNotes />
        </div>

        {/* Navigation grid */}
        <div className="grid grid-cols-2 gap-2.5">
          <Link
            href="/training"
            className="flex flex-col items-center gap-1.5 rounded-xl border border-border bg-card p-4 transition-colors hover:border-[var(--color-cat-training)]"
          >
            <Dumbbell className="h-6 w-6 text-[var(--color-cat-training)]" />
            <span className="text-xs font-bold">トレーニング</span>
          </Link>
          <Link
            href="/training/schedule"
            className="flex flex-col items-center gap-1.5 rounded-xl border border-border bg-card p-4 transition-colors hover:border-[var(--color-cat-training)]"
          >
            <CalendarDays className="h-6 w-6 text-[var(--color-cat-training)]" />
            <span className="text-xs font-bold">スケジュール</span>
          </Link>
          <Link
            href="/import"
            className="flex flex-col items-center gap-1.5 rounded-xl border border-border bg-card p-4 transition-colors hover:border-[var(--color-cat-research)]"
          >
            <FileUp className="h-6 w-6 text-[var(--color-cat-research)]" />
            <span className="text-xs font-bold">インポート</span>
          </Link>
          <Link
            href="/settings"
            className="flex flex-col items-center gap-1.5 rounded-xl border border-border bg-card p-4 transition-colors hover:border-muted-foreground"
          >
            <Settings className="h-6 w-6 text-muted-foreground" />
            <span className="text-xs font-bold">設定</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
