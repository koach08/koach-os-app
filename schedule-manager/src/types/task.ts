import type { CategoryId } from "@/lib/categories";

export type TaskStatus = "todo" | "in_progress" | "done";

export type TaskPriority = "high" | "medium" | "low";

export interface Task {
  id: string;
  title: string;
  description: string;
  category: CategoryId;
  status: TaskStatus;
  priority: TaskPriority;
  dueDate: string | null; // ISO date string e.g. "2026-03-15"
  dueTime: string | null; // "HH:mm" e.g. "17:00"
  estimatedMinutes: number | null;
  gcalEventId: string | null;
  createdAt: string; // ISO datetime
  updatedAt: string; // ISO datetime
  completedAt: string | null; // ISO datetime
}

export interface RescheduleRequest {
  changedTaskId: string;
  action: "completed" | "rescheduled" | "deleted";
  allTasks: Task[];
}

export interface Memo {
  id: string;
  content: string;
  color: "yellow" | "blue" | "green" | "pink";
  pinned: boolean;
  createdAt: string;
}

export interface RescheduleSuggestion {
  taskId: string;
  newDueDate: string;
  newDueTime: string | null;
  reason: string;
}
