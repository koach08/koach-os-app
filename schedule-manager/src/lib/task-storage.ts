import type { Task, TaskStatus } from "@/types/task";
import type { CategoryId } from "@/lib/categories";

const STORAGE_KEY = "schedule-manager-tasks";

function generateId(): string {
  return `task_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function now(): string {
  return new Date().toISOString();
}

export function loadTasks(): Task[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as Task[];
  } catch {
    return [];
  }
}

export function saveTasks(tasks: Task[]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
}

export function createTask(params: {
  title: string;
  description?: string;
  category?: CategoryId;
  priority?: "high" | "medium" | "low";
  dueDate?: string | null;
  dueTime?: string | null;
  estimatedMinutes?: number | null;
}): Task {
  const tasks = loadTasks();
  const task: Task = {
    id: generateId(),
    title: params.title,
    description: params.description || "",
    category: params.category || "class",
    status: "todo",
    priority: params.priority || "medium",
    dueDate: params.dueDate || null,
    dueTime: params.dueTime || null,
    estimatedMinutes: params.estimatedMinutes || null,
    gcalEventId: null,
    createdAt: now(),
    updatedAt: now(),
    completedAt: null,
  };
  tasks.push(task);
  saveTasks(tasks);
  return task;
}

export function updateTask(id: string, updates: Partial<Task>): Task | null {
  const tasks = loadTasks();
  const idx = tasks.findIndex((t) => t.id === id);
  if (idx === -1) return null;

  const updated = { ...tasks[idx], ...updates, updatedAt: now() };

  if (updates.status === "done" && !updated.completedAt) {
    updated.completedAt = now();
  }
  if (updates.status && updates.status !== "done") {
    updated.completedAt = null;
  }

  tasks[idx] = updated;
  saveTasks(tasks);
  return updated;
}

export function deleteTask(id: string): void {
  const tasks = loadTasks().filter((t) => t.id !== id);
  saveTasks(tasks);
}

export function getTasksByStatus(status: TaskStatus): Task[] {
  return loadTasks().filter((t) => t.status === status);
}

export function getTasksByCategory(category: CategoryId): Task[] {
  return loadTasks().filter((t) => t.category === category);
}

export function reorderTasks(orderedIds: string[]): void {
  const tasks = loadTasks();
  const taskMap = new Map(tasks.map((t) => [t.id, t]));
  const ordered: Task[] = [];
  for (const id of orderedIds) {
    const task = taskMap.get(id);
    if (task) {
      ordered.push(task);
      taskMap.delete(id);
    }
  }
  // Append any remaining tasks not in orderedIds
  for (const task of taskMap.values()) {
    ordered.push(task);
  }
  saveTasks(ordered);
}
