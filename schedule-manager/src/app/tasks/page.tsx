"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession, signIn } from "next-auth/react";
import { format } from "date-fns";
import { ja } from "date-fns/locale";
import { toast } from "sonner";
import { CATEGORIES, getCategoryColorId } from "@/lib/categories";
import type { CategoryId } from "@/lib/categories";
import type { Task, TaskStatus, TaskPriority, RescheduleSuggestion } from "@/types/task";
import {
  loadTasks,
  createTask,
  updateTask,
  deleteTask,
} from "@/lib/task-storage";
import {
  Plus,
  Check,
  Circle,
  Clock,
  Trash2,
  CalendarPlus,
  Loader2,
  Sparkles,
  ChevronDown,
  ChevronRight,
  GripVertical,
  LogIn,
  Pencil,
  X,
} from "lucide-react";

const STATUS_CONFIG: Record<
  TaskStatus,
  { label: string; icon: typeof Circle; color: string }
> = {
  todo: { label: "未着手", icon: Circle, color: "#64748b" },
  in_progress: { label: "進行中", icon: Clock, color: "#3b82f6" },
  done: { label: "完了", icon: Check, color: "#10b981" },
};

const PRIORITY_CONFIG: Record<TaskPriority, { label: string; color: string }> =
  {
    high: { label: "高", color: "#ef4444" },
    medium: { label: "中", color: "#f59e0b" },
    low: { label: "低", color: "#64748b" },
  };

export default function TasksPage() {
  const { data: session } = useSession();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [rescheduleLoading, setRescheduleLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<RescheduleSuggestion[]>([]);
  const [suggestionSummary, setSuggestionSummary] = useState("");
  const [collapsedSections, setCollapsedSections] = useState<
    Record<string, boolean>
  >({ done: true });
  const [filterCategory, setFilterCategory] = useState<CategoryId | "all">(
    "all"
  );

  // New task form
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newCategory, setNewCategory] = useState<CategoryId>("class");
  const [newPriority, setNewPriority] = useState<TaskPriority>("medium");
  const [newDueDate, setNewDueDate] = useState("");
  const [newDueTime, setNewDueTime] = useState("");
  const [newEstimate, setNewEstimate] = useState("");

  // Edit form
  const [editTitle, setEditTitle] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editCategory, setEditCategory] = useState<CategoryId>("class");
  const [editPriority, setEditPriority] = useState<TaskPriority>("medium");
  const [editDueDate, setEditDueDate] = useState("");
  const [editDueTime, setEditDueTime] = useState("");
  const [editEstimate, setEditEstimate] = useState("");

  const refresh = useCallback(() => {
    setTasks(loadTasks());
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleAdd = () => {
    if (!newTitle.trim()) {
      toast.error("タイトルを入力してください");
      return;
    }
    createTask({
      title: newTitle.trim(),
      description: newDesc,
      category: newCategory,
      priority: newPriority,
      dueDate: newDueDate || null,
      dueTime: newDueTime || null,
      estimatedMinutes: newEstimate ? parseInt(newEstimate) : null,
    });
    setNewTitle("");
    setNewDesc("");
    setNewCategory("class");
    setNewPriority("medium");
    setNewDueDate("");
    setNewDueTime("");
    setNewEstimate("");
    setShowAddForm(false);
    refresh();
    toast.success("タスクを追加しました");
  };

  const handleStatusChange = async (
    task: Task,
    newStatus: TaskStatus
  ) => {
    const prev = task.status;
    updateTask(task.id, { status: newStatus });
    refresh();

    if (newStatus === "done" && prev !== "done") {
      toast.success(`「${task.title}」を完了にしました`);
      requestReschedule(task, "completed");
    }
  };

  const handleEdit = (task: Task) => {
    setEditingId(task.id);
    setEditTitle(task.title);
    setEditDesc(task.description);
    setEditCategory(task.category);
    setEditPriority(task.priority);
    setEditDueDate(task.dueDate || "");
    setEditDueTime(task.dueTime || "");
    setEditEstimate(task.estimatedMinutes?.toString() || "");
  };

  const handleSaveEdit = () => {
    if (!editingId || !editTitle.trim()) return;
    const oldTask = tasks.find((t) => t.id === editingId);
    const dateChanged =
      oldTask &&
      (oldTask.dueDate !== (editDueDate || null) ||
        oldTask.dueTime !== (editDueTime || null));

    updateTask(editingId, {
      title: editTitle.trim(),
      description: editDesc,
      category: editCategory,
      priority: editPriority,
      dueDate: editDueDate || null,
      dueTime: editDueTime || null,
      estimatedMinutes: editEstimate ? parseInt(editEstimate) : null,
    });

    const updated = loadTasks().find((t) => t.id === editingId);
    setEditingId(null);
    refresh();
    toast.success("タスクを更新しました");

    if (dateChanged && updated) {
      requestReschedule(updated, "rescheduled");
    }
  };

  const handleDelete = (task: Task) => {
    deleteTask(task.id);
    refresh();
    toast.success(`「${task.title}」を削除しました`);
    requestReschedule(task, "deleted");
  };

  const handleSyncToGCal = async (task: Task) => {
    if (!session?.accessToken) {
      signIn("google");
      return;
    }
    if (!task.dueDate) {
      toast.error("期限を設定してからGCalに登録してください");
      return;
    }

    try {
      const startTime = task.dueTime || "09:00";
      const duration = task.estimatedMinutes || 60;
      const [h, m] = startTime.split(":").map(Number);
      const endDate = new Date(2026, 0, 1, h, m);
      endDate.setMinutes(endDate.getMinutes() + duration);
      const endTime = format(endDate, "HH:mm");

      const event = {
        summary: task.title,
        description: task.description,
        start: { dateTime: `${task.dueDate}T${startTime}:00+09:00` },
        end: { dateTime: `${task.dueDate}T${endTime}:00+09:00` },
        colorId: getCategoryColorId(task.category),
        reminders: {
          useDefault: false,
          overrides: [{ method: "popup", minutes: 30 }],
        },
      };

      const res = await fetch("/api/calendar/training", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: [event] }),
      });

      if (res.ok) {
        const data = await res.json();
        updateTask(task.id, {
          gcalEventId: data.events?.[0]?.id || "synced",
        });
        refresh();
        toast.success(`「${task.title}」をGCalに登録しました`);
      } else {
        throw new Error("Failed");
      }
    } catch {
      toast.error("GCal登録に失敗しました");
    }
  };

  const requestReschedule = async (
    changedTask: Task,
    action: string
  ) => {
    const allTasks = loadTasks();
    const pendingTasks = allTasks.filter((t) => t.status !== "done");
    if (pendingTasks.length < 2) return;

    setRescheduleLoading(true);
    try {
      const res = await fetch("/api/tasks/reschedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          changedTask,
          action,
          tasks: allTasks,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.suggestions?.length > 0) {
          setSuggestions(data.suggestions);
          setSuggestionSummary(data.summary || "");
        }
      }
    } catch {
      // Silently fail — reschedule is optional
    } finally {
      setRescheduleLoading(false);
    }
  };

  const applySuggestion = (suggestion: RescheduleSuggestion) => {
    updateTask(suggestion.taskId, {
      dueDate: suggestion.newDueDate,
      dueTime: suggestion.newDueTime,
    });
    setSuggestions((prev) =>
      prev.filter((s) => s.taskId !== suggestion.taskId)
    );
    refresh();
    toast.success("日程を更新しました");
  };

  const dismissSuggestions = () => {
    setSuggestions([]);
    setSuggestionSummary("");
  };

  const toggleSection = (status: string) => {
    setCollapsedSections((prev) => ({ ...prev, [status]: !prev[status] }));
  };

  const filteredTasks =
    filterCategory === "all"
      ? tasks
      : tasks.filter((t) => t.category === filterCategory);

  const grouped: Record<TaskStatus, Task[]> = {
    todo: filteredTasks.filter((t) => t.status === "todo"),
    in_progress: filteredTasks.filter((t) => t.status === "in_progress"),
    done: filteredTasks.filter((t) => t.status === "done"),
  };

  // Sort: priority high→low, then by due date
  const sortTasks = (arr: Task[]) =>
    [...arr].sort((a, b) => {
      const pOrder = { high: 0, medium: 1, low: 2 };
      if (pOrder[a.priority] !== pOrder[b.priority])
        return pOrder[a.priority] - pOrder[b.priority];
      if (a.dueDate && b.dueDate) return a.dueDate.localeCompare(b.dueDate);
      if (a.dueDate) return -1;
      if (b.dueDate) return 1;
      return 0;
    });

  return (
    <div className="min-h-screen px-4 py-6">
      <div className="mx-auto max-w-lg">
        {/* Header */}
        <div className="mb-4 flex items-start justify-between">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[4px] text-muted-foreground">
              Schedule Manager
            </p>
            <h1 className="mt-1 text-2xl font-black">タスク管理</h1>
          </div>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-xs font-bold transition-colors hover:border-[var(--color-cat-growth)]"
          >
            <Plus className="h-4 w-4 text-[var(--color-cat-growth)]" />
            タスク追加
          </button>
        </div>

        {/* Auth prompt */}
        {!session?.accessToken && (
          <button
            onClick={() => signIn("google")}
            className="mb-4 flex w-full items-center gap-2 rounded-xl border border-border bg-card p-3 transition-colors hover:border-[var(--color-cat-research)]"
          >
            <LogIn className="h-4 w-4 text-[var(--color-cat-research)]" />
            <span className="text-xs">
              GCal連携するにはGoogleでログイン
            </span>
          </button>
        )}

        {/* AI Reschedule Suggestions */}
        {suggestions.length > 0 && (
          <div className="mb-4 rounded-xl border border-[#3b82f6]/30 bg-[#3b82f6]/5 p-3">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="flex items-center gap-1.5 text-xs font-bold text-[#3b82f6]">
                <Sparkles className="h-3.5 w-3.5" />
                AI リスケジュール提案
              </h3>
              <button
                onClick={dismissSuggestions}
                className="text-[10px] text-muted-foreground hover:text-foreground"
              >
                閉じる
              </button>
            </div>
            {suggestionSummary && (
              <p className="mb-2 text-[11px] text-muted-foreground">
                {suggestionSummary}
              </p>
            )}
            {suggestions.map((s) => {
              const task = tasks.find((t) => t.id === s.taskId);
              if (!task) return null;
              return (
                <div
                  key={s.taskId}
                  className="mb-2 flex items-center justify-between rounded-lg border border-border/50 bg-card p-2 last:mb-0"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[11px] font-bold">
                      {task.title}
                    </p>
                    <p className="text-[10px] text-muted-foreground">
                      → {s.newDueDate}
                      {s.newDueTime ? ` ${s.newDueTime}` : ""} — {s.reason}
                    </p>
                  </div>
                  <button
                    onClick={() => applySuggestion(s)}
                    className="ml-2 flex-shrink-0 rounded border border-[#3b82f6]/30 px-2 py-1 text-[10px] font-bold text-[#3b82f6] hover:bg-[#3b82f6]/10"
                  >
                    適用
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {rescheduleLoading && (
          <div className="mb-4 flex items-center gap-2 rounded-xl border border-border bg-card p-3">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-[#3b82f6]" />
            <span className="text-[11px] text-muted-foreground">
              AI がスケジュール最適化を分析中...
            </span>
          </div>
        )}

        {/* Category filter */}
        <div className="mb-3 flex gap-1.5 overflow-x-auto">
          <button
            onClick={() => setFilterCategory("all")}
            className="rounded-md border px-2.5 py-1.5 text-[10px] font-bold transition-colors"
            style={{
              borderColor:
                filterCategory === "all" ? "#e2e8f0" : "var(--border)",
              background:
                filterCategory === "all" ? "#e2e8f015" : "transparent",
              color:
                filterCategory === "all" ? "#e2e8f0" : "var(--muted-foreground)",
            }}
          >
            全て ({tasks.length})
          </button>
          {CATEGORIES.map((cat) => {
            const count = tasks.filter((t) => t.category === cat.id).length;
            return (
              <button
                key={cat.id}
                onClick={() => setFilterCategory(cat.id)}
                className="rounded-md border px-2.5 py-1.5 text-[10px] font-bold transition-colors"
                style={{
                  borderColor:
                    filterCategory === cat.id ? cat.color : "var(--border)",
                  background:
                    filterCategory === cat.id
                      ? `${cat.color}15`
                      : "transparent",
                  color:
                    filterCategory === cat.id
                      ? cat.color
                      : "var(--muted-foreground)",
                }}
              >
                {cat.label} ({count})
              </button>
            );
          })}
        </div>

        {/* Add Task Form */}
        {showAddForm && (
          <div className="mb-4 rounded-xl border border-[var(--color-cat-growth)]/30 bg-card p-4">
            <h3 className="mb-3 text-sm font-bold">新しいタスク</h3>
            <div className="space-y-2.5">
              <input
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="タスク名"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                autoFocus
                onKeyDown={(e) => e.key === "Enter" && handleAdd()}
              />
              <textarea
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="メモ（任意）"
                rows={2}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
              <div className="flex flex-wrap gap-1.5">
                {CATEGORIES.map((cat) => (
                  <button
                    key={cat.id}
                    onClick={() => setNewCategory(cat.id)}
                    className="rounded-md border px-2 py-1 text-[10px] font-bold"
                    style={{
                      borderColor:
                        newCategory === cat.id ? cat.color : "var(--border)",
                      background:
                        newCategory === cat.id
                          ? `${cat.color}15`
                          : "transparent",
                      color:
                        newCategory === cat.id
                          ? cat.color
                          : "var(--muted-foreground)",
                    }}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>
              <div className="flex gap-1.5">
                {(["high", "medium", "low"] as TaskPriority[]).map((p) => (
                  <button
                    key={p}
                    onClick={() => setNewPriority(p)}
                    className="rounded-md border px-2.5 py-1 text-[10px] font-bold"
                    style={{
                      borderColor:
                        newPriority === p
                          ? PRIORITY_CONFIG[p].color
                          : "var(--border)",
                      background:
                        newPriority === p
                          ? `${PRIORITY_CONFIG[p].color}15`
                          : "transparent",
                      color:
                        newPriority === p
                          ? PRIORITY_CONFIG[p].color
                          : "var(--muted-foreground)",
                    }}
                  >
                    {PRIORITY_CONFIG[p].label}
                  </button>
                ))}
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="mb-1 block text-[10px] text-muted-foreground">
                    期限
                  </label>
                  <input
                    type="date"
                    value={newDueDate}
                    onChange={(e) => setNewDueDate(e.target.value)}
                    className="w-full rounded-md border border-border bg-background px-2 py-1.5 font-mono text-[11px]"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[10px] text-muted-foreground">
                    時間
                  </label>
                  <input
                    type="time"
                    value={newDueTime}
                    onChange={(e) => setNewDueTime(e.target.value)}
                    className="w-full rounded-md border border-border bg-background px-2 py-1.5 font-mono text-[11px]"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[10px] text-muted-foreground">
                    見積(分)
                  </label>
                  <input
                    type="number"
                    value={newEstimate}
                    onChange={(e) => setNewEstimate(e.target.value)}
                    placeholder="60"
                    className="w-full rounded-md border border-border bg-background px-2 py-1.5 font-mono text-[11px]"
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleAdd}
                  className="flex-1 rounded-md bg-[var(--color-cat-growth)] px-3 py-2 text-xs font-bold text-white"
                >
                  追加
                </button>
                <button
                  onClick={() => setShowAddForm(false)}
                  className="rounded-md border border-border px-3 py-2 text-xs text-muted-foreground"
                >
                  キャンセル
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Task Sections */}
        {(["in_progress", "todo", "done"] as TaskStatus[]).map((status) => {
          const statusTasks = sortTasks(grouped[status]);
          const config = STATUS_CONFIG[status];
          const isCollapsed = collapsedSections[status];
          const Icon = config.icon;

          return (
            <div key={status} className="mb-3">
              <button
                onClick={() => toggleSection(status)}
                className="mb-2 flex w-full items-center gap-2"
              >
                {isCollapsed ? (
                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                ) : (
                  <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                )}
                <Icon
                  className="h-3.5 w-3.5"
                  style={{ color: config.color }}
                />
                <span
                  className="text-xs font-bold"
                  style={{ color: config.color }}
                >
                  {config.label}
                </span>
                <span className="text-[10px] text-muted-foreground">
                  ({statusTasks.length})
                </span>
              </button>

              {!isCollapsed && (
                <div className="space-y-1.5">
                  {statusTasks.length === 0 && (
                    <p className="py-2 text-center text-[11px] text-muted-foreground">
                      タスクなし
                    </p>
                  )}
                  {statusTasks.map((task) => {
                    const cat = CATEGORIES.find(
                      (c) => c.id === task.category
                    );
                    const isEditing = editingId === task.id;

                    if (isEditing) {
                      return (
                        <div
                          key={task.id}
                          className="rounded-xl border border-[#3b82f6]/30 bg-card p-3"
                        >
                          <div className="space-y-2">
                            <input
                              type="text"
                              value={editTitle}
                              onChange={(e) => setEditTitle(e.target.value)}
                              className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm"
                              autoFocus
                            />
                            <textarea
                              value={editDesc}
                              onChange={(e) => setEditDesc(e.target.value)}
                              rows={2}
                              className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm"
                            />
                            <div className="flex flex-wrap gap-1">
                              {CATEGORIES.map((c) => (
                                <button
                                  key={c.id}
                                  onClick={() => setEditCategory(c.id)}
                                  className="rounded border px-2 py-0.5 text-[9px] font-bold"
                                  style={{
                                    borderColor:
                                      editCategory === c.id
                                        ? c.color
                                        : "var(--border)",
                                    color:
                                      editCategory === c.id
                                        ? c.color
                                        : "var(--muted-foreground)",
                                  }}
                                >
                                  {c.label}
                                </button>
                              ))}
                            </div>
                            <div className="flex gap-1">
                              {(
                                ["high", "medium", "low"] as TaskPriority[]
                              ).map((p) => (
                                <button
                                  key={p}
                                  onClick={() => setEditPriority(p)}
                                  className="rounded border px-2 py-0.5 text-[9px] font-bold"
                                  style={{
                                    borderColor:
                                      editPriority === p
                                        ? PRIORITY_CONFIG[p].color
                                        : "var(--border)",
                                    color:
                                      editPriority === p
                                        ? PRIORITY_CONFIG[p].color
                                        : "var(--muted-foreground)",
                                  }}
                                >
                                  {PRIORITY_CONFIG[p].label}
                                </button>
                              ))}
                            </div>
                            <div className="grid grid-cols-3 gap-2">
                              <input
                                type="date"
                                value={editDueDate}
                                onChange={(e) => setEditDueDate(e.target.value)}
                                className="rounded-md border border-border bg-background px-2 py-1 font-mono text-[10px]"
                              />
                              <input
                                type="time"
                                value={editDueTime}
                                onChange={(e) => setEditDueTime(e.target.value)}
                                className="rounded-md border border-border bg-background px-2 py-1 font-mono text-[10px]"
                              />
                              <input
                                type="number"
                                value={editEstimate}
                                onChange={(e) =>
                                  setEditEstimate(e.target.value)
                                }
                                placeholder="分"
                                className="rounded-md border border-border bg-background px-2 py-1 font-mono text-[10px]"
                              />
                            </div>
                            <div className="flex gap-2">
                              <button
                                onClick={handleSaveEdit}
                                className="flex-1 rounded-md bg-[#3b82f6] px-3 py-1.5 text-xs font-bold text-white"
                              >
                                保存
                              </button>
                              <button
                                onClick={() => setEditingId(null)}
                                className="rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground"
                              >
                                <X className="h-3 w-3" />
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    }

                    return (
                      <div
                        key={task.id}
                        className="group rounded-xl border border-border bg-card transition-colors hover:border-border/80"
                        style={{
                          opacity: task.status === "done" ? 0.5 : 1,
                        }}
                      >
                        <div className="flex items-start gap-2 px-3 py-2.5">
                          {/* Status toggle */}
                          <button
                            onClick={() =>
                              handleStatusChange(
                                task,
                                task.status === "done"
                                  ? "todo"
                                  : task.status === "todo"
                                  ? "in_progress"
                                  : "done"
                              )
                            }
                            className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border-2 text-[10px] transition-colors"
                            style={{
                              borderColor:
                                task.status === "done"
                                  ? "#10b981"
                                  : task.status === "in_progress"
                                  ? "#3b82f6"
                                  : "var(--border)",
                              background:
                                task.status === "done"
                                  ? "#10b98133"
                                  : task.status === "in_progress"
                                  ? "#3b82f633"
                                  : "transparent",
                              color:
                                task.status === "done"
                                  ? "#10b981"
                                  : task.status === "in_progress"
                                  ? "#3b82f6"
                                  : "transparent",
                            }}
                            title={
                              task.status === "done"
                                ? "未着手に戻す"
                                : task.status === "todo"
                                ? "進行中にする"
                                : "完了にする"
                            }
                          >
                            {task.status === "done" && "✓"}
                            {task.status === "in_progress" && "●"}
                          </button>

                          {/* Content */}
                          <div className="min-w-0 flex-1">
                            <div className="flex items-start justify-between gap-2">
                              <span
                                className={`text-[13px] font-bold ${
                                  task.status === "done" ? "line-through" : ""
                                }`}
                              >
                                {task.title}
                              </span>
                              <div className="flex flex-shrink-0 items-center gap-1">
                                {/* Priority badge */}
                                <span
                                  className="rounded px-1.5 py-0.5 text-[8px] font-bold"
                                  style={{
                                    background: `${PRIORITY_CONFIG[task.priority].color}15`,
                                    color:
                                      PRIORITY_CONFIG[task.priority].color,
                                  }}
                                >
                                  {PRIORITY_CONFIG[task.priority].label}
                                </span>
                                {/* Category dot */}
                                <div
                                  className="h-2 w-2 rounded-full"
                                  style={{
                                    background: cat?.color || "#64748b",
                                  }}
                                  title={cat?.label}
                                />
                              </div>
                            </div>
                            {task.description && (
                              <p className="mt-0.5 text-[11px] text-muted-foreground">
                                {task.description}
                              </p>
                            )}
                            <div className="mt-1 flex items-center gap-3 text-[10px] text-muted-foreground">
                              {task.dueDate && (
                                <span className="font-mono">
                                  {task.dueDate}
                                  {task.dueTime ? ` ${task.dueTime}` : ""}
                                </span>
                              )}
                              {task.estimatedMinutes && (
                                <span>{task.estimatedMinutes}分</span>
                              )}
                              {task.gcalEventId && (
                                <span className="text-[var(--color-cat-growth)]">
                                  GCal✓
                                </span>
                              )}
                            </div>

                            {/* Actions */}
                            <div className="mt-1.5 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                              <button
                                onClick={() => handleEdit(task)}
                                className="rounded border border-border px-2 py-0.5 text-[9px] text-muted-foreground hover:text-foreground"
                              >
                                <Pencil className="h-2.5 w-2.5" />
                              </button>
                              {!task.gcalEventId && task.dueDate && (
                                <button
                                  onClick={() => handleSyncToGCal(task)}
                                  className="rounded border border-border px-2 py-0.5 text-[9px] text-[var(--color-cat-training)] hover:border-[var(--color-cat-training)]/30"
                                >
                                  <CalendarPlus className="h-2.5 w-2.5" />
                                </button>
                              )}
                              <button
                                onClick={() => handleDelete(task)}
                                className="rounded border border-border px-2 py-0.5 text-[9px] text-muted-foreground hover:text-[#ef4444]"
                              >
                                <Trash2 className="h-2.5 w-2.5" />
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}

        {/* Empty state */}
        {tasks.length === 0 && !showAddForm && (
          <div className="py-12 text-center">
            <p className="mb-2 text-sm text-muted-foreground">
              タスクがありません
            </p>
            <button
              onClick={() => setShowAddForm(true)}
              className="rounded-lg border border-border bg-card px-4 py-2 text-xs font-bold transition-colors hover:border-[var(--color-cat-growth)]"
            >
              <Plus className="mr-1 inline h-3 w-3" />
              最初のタスクを追加
            </button>
          </div>
        )}

        {/* Stats */}
        {tasks.length > 0 && (
          <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-4 pb-8">
            <div className="text-center">
              <div className="text-lg font-black text-[#3b82f6]">
                {tasks.filter((t) => t.status === "in_progress").length}
              </div>
              <div className="text-[10px] text-muted-foreground">進行中</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-black text-[#64748b]">
                {tasks.filter((t) => t.status === "todo").length}
              </div>
              <div className="text-[10px] text-muted-foreground">未着手</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-black text-[#10b981]">
                {tasks.filter((t) => t.status === "done").length}
              </div>
              <div className="text-[10px] text-muted-foreground">完了</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
