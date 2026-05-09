"use client";

import { useEffect, useState } from "react";

type Status = "todo" | "in_progress" | "done";
type Priority = "high" | "medium" | "low";

type Task = {
  id: string;
  title: string;
  description: string;
  status: Status;
  priority: Priority;
  due_date: string | null;
  due_time: string | null;
  estimated_minutes: number | null;
  category: string;
  gcal_event_id: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
};

const STATUS_META: Record<Status, { label: string; emoji: string; color: string }> = {
  todo: { label: "Todo", emoji: "○", color: "#71717a" },
  in_progress: { label: "進行中", emoji: "◐", color: "#3b82f6" },
  done: { label: "完了", emoji: "●", color: "#22c55e" },
};

const PRIORITY_META: Record<Priority, { label: string; color: string }> = {
  high: { label: "高", color: "#ef4444" },
  medium: { label: "中", color: "#eab308" },
  low: { label: "低", color: "#71717a" },
};

const CATEGORIES = ["personal", "research", "teaching", "platform", "revenue", "business"];

function formatDue(date: string | null, time: string | null): string {
  if (!date) return "—";
  const today = new Date().toISOString().slice(0, 10);
  const isOverdue = date < today;
  const isToday = date === today;
  const datePart = new Date(date).toLocaleDateString("ja-JP", { month: "numeric", day: "numeric", weekday: "short" });
  const timePart = time ? ` ${time}` : "";
  const tag = isOverdue ? " ⚠ 期限切れ" : isToday ? " ⚡ 今日" : "";
  return `${datePart}${timePart}${tag}`;
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Status | "all">("all");
  const [showNewForm, setShowNewForm] = useState(false);

  // New task form state
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newPriority, setNewPriority] = useState<Priority>("medium");
  const [newDueDate, setNewDueDate] = useState("");
  const [newDueTime, setNewDueTime] = useState("");
  const [newEstimated, setNewEstimated] = useState("");
  const [newCategory, setNewCategory] = useState("personal");

  const load = () => {
    setLoading(true);
    setError(null);
    fetch("/api/tasks")
      .then((r) => r.json())
      .then((d) => setTasks(d.tasks ?? []))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async () => {
    if (!newTitle.trim()) return;
    try {
      const res = await fetch("/api/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: newTitle,
          description: newDescription,
          priority: newPriority,
          due_date: newDueDate || null,
          due_time: newDueTime || null,
          estimated_minutes: newEstimated ? Number(newEstimated) : null,
          category: newCategory,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      // Reset form
      setNewTitle("");
      setNewDescription("");
      setNewPriority("medium");
      setNewDueDate("");
      setNewDueTime("");
      setNewEstimated("");
      setShowNewForm(false);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleStatusChange = async (id: string, status: Status) => {
    try {
      await fetch(`/api/tasks/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("タスクを削除しますか？")) return;
    try {
      await fetch(`/api/tasks/${id}`, { method: "DELETE" });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleAddToCalendar = async (id: string) => {
    try {
      const res = await fetch(`/api/tasks/${id}/to-calendar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail);
      }
      const data = await res.json();
      if (data.html_link) {
        window.open(data.html_link, "_blank");
      }
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const filtered = filter === "all" ? tasks : tasks.filter((t) => t.status === filter);
  const counts = {
    all: tasks.length,
    todo: tasks.filter((t) => t.status === "todo").length,
    in_progress: tasks.filter((t) => t.status === "in_progress").length,
    done: tasks.filter((t) => t.status === "done").length,
  };

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Hero */}
      <div
        className="px-8 pt-10 pb-6"
        style={{
          background:
            "radial-gradient(ellipse at top right, rgba(34, 197, 94, 0.10), transparent 50%)",
        }}
      >
        <div className="max-w-5xl mx-auto flex items-end justify-between flex-wrap gap-4">
          <div>
            <h1
              className="text-4xl font-bold tracking-tight"
              style={{
                background: "linear-gradient(90deg, #fafafa 0%, #a1a1aa 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              Tasks
            </h1>
            <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>
              優先度 / 期限 / カテゴリで管理。Calendar に追加するとリマインダーも自動設定
            </p>
          </div>
          <button
            onClick={() => setShowNewForm(!showNewForm)}
            className="px-5 py-2.5 rounded-full text-sm font-medium transition-all hover:scale-[1.02]"
            style={{
              background: "var(--color-accent)",
              color: "white",
              boxShadow: "0 4px 14px rgba(59, 130, 246, 0.35)",
            }}
          >
            {showNewForm ? "キャンセル" : "+ 新規タスク"}
          </button>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-5xl mx-auto space-y-5">
          {/* New task form */}
          {showNewForm && (
            <div
              className="rounded-2xl p-6 space-y-3"
              style={{
                background:
                  "linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, transparent 100%)",
                border: "1px solid var(--color-accent)",
              }}
            >
              <input
                type="text"
                placeholder="タスク名"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                className="w-full px-4 py-2.5 rounded-lg text-base"
                style={{
                  background: "var(--color-background)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text)",
                }}
              />
              <textarea
                placeholder="詳細 (任意)"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                rows={2}
                className="w-full px-4 py-2.5 rounded-lg text-sm resize-none"
                style={{
                  background: "var(--color-background)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text)",
                }}
              />
              <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                <select
                  value={newPriority}
                  onChange={(e) => setNewPriority(e.target.value as Priority)}
                  className="px-3 py-2 rounded-lg text-sm"
                  style={{
                    background: "var(--color-background)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                >
                  <option value="high">優先度: 高</option>
                  <option value="medium">優先度: 中</option>
                  <option value="low">優先度: 低</option>
                </select>
                <input
                  type="date"
                  value={newDueDate}
                  onChange={(e) => setNewDueDate(e.target.value)}
                  className="px-3 py-2 rounded-lg text-sm"
                  style={{
                    background: "var(--color-background)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                />
                <input
                  type="time"
                  value={newDueTime}
                  onChange={(e) => setNewDueTime(e.target.value)}
                  className="px-3 py-2 rounded-lg text-sm"
                  style={{
                    background: "var(--color-background)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                />
                <select
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value)}
                  className="px-3 py-2 rounded-lg text-sm"
                  style={{
                    background: "var(--color-background)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex gap-2">
                <input
                  type="number"
                  placeholder="推定時間 (分)"
                  value={newEstimated}
                  onChange={(e) => setNewEstimated(e.target.value)}
                  className="flex-1 px-3 py-2 rounded-lg text-sm"
                  style={{
                    background: "var(--color-background)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                />
                <button
                  onClick={handleCreate}
                  disabled={!newTitle.trim()}
                  className="px-5 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                  style={{ background: "var(--color-accent)", color: "white" }}
                >
                  作成
                </button>
              </div>
            </div>
          )}

          {/* Filter pills */}
          <div className="flex gap-2 flex-wrap">
            {(["all", "todo", "in_progress", "done"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className="px-3.5 py-1.5 rounded-full text-xs transition-all"
                style={{
                  background: filter === f ? "var(--color-text)" : "transparent",
                  color: filter === f ? "var(--color-background)" : "var(--color-text-muted)",
                  border: filter === f ? "1px solid var(--color-text)" : "1px solid var(--color-border)",
                  fontWeight: filter === f ? 600 : 400,
                }}
              >
                {f === "all" ? "すべて" : STATUS_META[f as Status].label} ({counts[f]})
              </button>
            ))}
          </div>

          {error && (
            <div
              className="rounded-2xl p-4 text-sm"
              style={{
                background: "rgba(239, 68, 68, 0.08)",
                border: "1px solid var(--color-red)",
                color: "var(--color-red)",
              }}
            >
              {error}
            </div>
          )}

          {/* Task list */}
          {loading ? (
            <div className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              読み込み中...
            </div>
          ) : filtered.length === 0 ? (
            <div
              className="rounded-2xl p-10 text-center"
              style={{ background: "var(--color-surface)", border: "1px dashed var(--color-border-light)" }}
            >
              <p className="text-3xl mb-2">✨</p>
              <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                {filter === "all" ? "まだタスクがありません" : "該当するタスクがありません"}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {filtered.map((t) => {
                const sm = STATUS_META[t.status];
                const pm = PRIORITY_META[t.priority];
                const isDone = t.status === "done";
                return (
                  <div
                    key={t.id}
                    className="rounded-2xl p-4 transition-all hover:translate-y-[-1px]"
                    style={{
                      background: "var(--color-surface)",
                      border: "1px solid var(--color-border)",
                      opacity: isDone ? 0.55 : 1,
                    }}
                  >
                    <div className="flex items-start gap-3">
                      {/* Status toggle button */}
                      <button
                        onClick={() => {
                          const next: Status =
                            t.status === "todo"
                              ? "in_progress"
                              : t.status === "in_progress"
                              ? "done"
                              : "todo";
                          handleStatusChange(t.id, next);
                        }}
                        className="text-2xl shrink-0 leading-none mt-0.5 hover:scale-110 transition-transform"
                        style={{ color: sm.color }}
                        title={`次の状態へ: ${STATUS_META[
                          t.status === "todo" ? "in_progress" : t.status === "in_progress" ? "done" : "todo"
                        ].label}`}
                      >
                        {sm.emoji}
                      </button>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3
                            className="font-medium"
                            style={{
                              textDecoration: isDone ? "line-through" : "none",
                            }}
                          >
                            {t.title}
                          </h3>
                          <span
                            className="text-[10px] font-medium px-2 py-0.5 rounded-full"
                            style={{
                              background: `${pm.color}20`,
                              color: pm.color,
                            }}
                          >
                            {pm.label}
                          </span>
                          <span
                            className="text-[10px] px-2 py-0.5 rounded-full"
                            style={{
                              background: "var(--color-surface-hover)",
                              color: "var(--color-text-muted)",
                            }}
                          >
                            {t.category}
                          </span>
                          {t.gcal_event_id && (
                            <span
                              className="text-[10px] px-2 py-0.5 rounded-full"
                              style={{
                                background: "rgba(34, 197, 94, 0.12)",
                                color: "#22c55e",
                              }}
                            >
                              📅 Cal
                            </span>
                          )}
                        </div>
                        {t.description && (
                          <p
                            className="text-sm mt-1"
                            style={{ color: "var(--color-text-muted)" }}
                          >
                            {t.description}
                          </p>
                        )}
                        <div className="flex items-center gap-3 mt-1.5 text-xs" style={{ color: "var(--color-text-muted)" }}>
                          <span>{formatDue(t.due_date, t.due_time)}</span>
                          {t.estimated_minutes && <span>· {t.estimated_minutes}分</span>}
                        </div>
                      </div>

                      <div className="flex flex-col gap-1 shrink-0">
                        {t.due_date && !t.gcal_event_id && (
                          <button
                            onClick={() => handleAddToCalendar(t.id)}
                            className="text-xs px-2.5 py-1 rounded-full transition-colors"
                            style={{
                              background: "rgba(59, 130, 246, 0.12)",
                              color: "var(--color-accent)",
                            }}
                            title="Calendar に追加"
                          >
                            → Cal
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete(t.id)}
                          className="text-xs px-2.5 py-1 rounded-full transition-colors"
                          style={{
                            background: "rgba(239, 68, 68, 0.08)",
                            color: "var(--color-red)",
                          }}
                          title="削除"
                        >
                          削除
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
