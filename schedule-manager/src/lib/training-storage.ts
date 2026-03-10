import type { TrainingLog, TrainingProgress } from "@/types/training";

const STORAGE_KEY = "schedule-manager-training";

function getDefaultProgress(): TrainingProgress {
  return {
    checkedItems: {},
    currentPhase: 0,
    logs: [],
  };
}

export function loadProgress(): TrainingProgress {
  if (typeof window === "undefined") return getDefaultProgress();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return getDefaultProgress();
    return JSON.parse(raw) as TrainingProgress;
  } catch {
    return getDefaultProgress();
  }
}

export function saveProgress(progress: TrainingProgress): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
}

export function toggleExercise(key: string): TrainingProgress {
  const progress = loadProgress();
  progress.checkedItems[key] = !progress.checkedItems[key];
  saveProgress(progress);
  return progress;
}

export function setCurrentPhase(phaseId: number): TrainingProgress {
  const progress = loadProgress();
  progress.currentPhase = phaseId;
  saveProgress(progress);
  return progress;
}

export function addLog(log: TrainingLog): TrainingProgress {
  const progress = loadProgress();
  const existingIdx = progress.logs.findIndex((l) => l.date === log.date);
  if (existingIdx >= 0) {
    progress.logs[existingIdx] = log;
  } else {
    progress.logs.push(log);
  }
  progress.logs.sort((a, b) => b.date.localeCompare(a.date));
  saveProgress(progress);
  return progress;
}

export function getLog(date: string): TrainingLog | undefined {
  const progress = loadProgress();
  return progress.logs.find((l) => l.date === date);
}

export function getRecentLogs(n: number = 30): TrainingLog[] {
  const progress = loadProgress();
  return progress.logs.slice(0, n);
}
