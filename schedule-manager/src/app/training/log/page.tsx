"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { format } from "date-fns";
import { ja } from "date-fns/locale";
import { addLog, getRecentLogs, loadProgress } from "@/lib/training-storage";
import type { TrainingLog } from "@/types/training";
import { Button } from "@/components/ui/button";
import { ChevronLeft, Plus, TrendingDown } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export default function TrainingLogPage() {
  const [logs, setLogs] = useState<TrainingLog[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [date, setDate] = useState(format(new Date(), "yyyy-MM-dd"));
  const [weight, setWeight] = useState("");
  const [bodyFat, setBodyFat] = useState("");
  const [notes, setNotes] = useState("");

  const refreshLogs = useCallback(() => {
    setLogs(getRecentLogs(60));
  }, []);

  useEffect(() => {
    refreshLogs();
  }, [refreshLogs]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const progress = loadProgress();
    const completedExercises = Object.entries(progress.checkedItems)
      .filter(([, v]) => v)
      .map(([k]) => k);

    const log: TrainingLog = {
      date,
      completedExercises,
      notes: notes || undefined,
    };
    if (weight) log.weight = parseFloat(weight);
    if (bodyFat) log.bodyFat = parseFloat(bodyFat);

    addLog(log);
    refreshLogs();
    setShowForm(false);
    setWeight("");
    setBodyFat("");
    setNotes("");
  };

  const weightData = logs
    .filter((l) => l.weight)
    .map((l) => ({
      date: format(new Date(l.date), "M/d"),
      weight: l.weight,
      bodyFat: l.bodyFat,
    }))
    .reverse();

  return (
    <div className="min-h-screen px-4 py-6">
      <div className="mx-auto max-w-lg">
        <Link
          href="/training"
          className="mb-4 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-4 w-4" />
          トレーニングに戻る
        </Link>

        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-xl font-black">📊 進捗ログ</h1>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowForm(!showForm)}
            className="gap-1 text-xs"
          >
            <Plus className="h-3.5 w-3.5" />
            記録
          </Button>
        </div>

        {/* Add log form */}
        {showForm && (
          <form
            onSubmit={handleSubmit}
            className="mb-4 rounded-xl border border-border bg-card p-4"
          >
            <div className="mb-3">
              <label className="mb-1 block text-[11px] font-bold text-muted-foreground">
                日付
              </label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
            </div>
            <div className="mb-3 grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-[11px] font-bold text-muted-foreground">
                  体重 (kg)
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={weight}
                  onChange={(e) => setWeight(e.target.value)}
                  placeholder="73.5"
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-bold text-muted-foreground">
                  体脂肪率 (%)
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={bodyFat}
                  onChange={(e) => setBodyFat(e.target.value)}
                  placeholder="18.0"
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div className="mb-3">
              <label className="mb-1 block text-[11px] font-bold text-muted-foreground">
                メモ
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="今日の調子、気づいたこと..."
                rows={2}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
            </div>
            <div className="flex gap-2">
              <Button type="submit" size="sm" className="flex-1">
                保存
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => setShowForm(false)}
              >
                キャンセル
              </Button>
            </div>
          </form>
        )}

        {/* Weight chart */}
        {weightData.length >= 2 && (
          <div className="mb-4 rounded-xl border border-border bg-card p-4">
            <h3 className="mb-3 flex items-center gap-1.5 text-sm font-bold">
              <TrendingDown className="h-4 w-4 text-[var(--color-cat-training)]" />
              体重推移
            </h3>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={weightData}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--border)"
                />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                  stroke="var(--border)"
                />
                <YAxis
                  domain={["dataMin - 1", "dataMax + 1"]}
                  tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                  stroke="var(--border)"
                  width={35}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--card)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="weight"
                  stroke="var(--color-cat-training)"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "var(--color-cat-training)" }}
                  name="体重 (kg)"
                />
                {weightData.some((d) => d.bodyFat) && (
                  <Line
                    type="monotone"
                    dataKey="bodyFat"
                    stroke="var(--color-cat-growth)"
                    strokeWidth={2}
                    dot={{ r: 3, fill: "var(--color-cat-growth)" }}
                    name="体脂肪率 (%)"
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Log entries */}
        <div className="space-y-2">
          {logs.length === 0 ? (
            <div className="rounded-xl border border-border bg-card p-8 text-center">
              <p className="text-sm text-muted-foreground">
                まだ記録がありません
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                「記録」ボタンから体重やメモを記録しましょう
              </p>
            </div>
          ) : (
            logs.map((log, i) => (
              <div
                key={i}
                className="rounded-lg border border-border bg-card px-3 py-2.5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold">
                    {format(new Date(log.date), "M月d日（E）", { locale: ja })}
                  </span>
                  <div className="flex items-center gap-3">
                    {log.weight && (
                      <span className="font-mono text-xs text-[var(--color-cat-training)]">
                        {log.weight}kg
                      </span>
                    )}
                    {log.bodyFat && (
                      <span className="font-mono text-xs text-[var(--color-cat-growth)]">
                        {log.bodyFat}%
                      </span>
                    )}
                  </div>
                </div>
                {log.completedExercises.length > 0 && (
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    完了: {log.completedExercises.length}種目
                  </p>
                )}
                {log.notes && (
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    {log.notes}
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
