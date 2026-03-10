export interface AppSettings {
  currentPhase: number;
  openaiApiKey: string;
  scanKeywords: string[];
  reminderMinutes: number;
  categoryColors: Record<string, string>;
}

const SETTINGS_KEY = "schedule-manager-settings";

const DEFAULT_SETTINGS: AppSettings = {
  currentPhase: 0,
  openaiApiKey: "",
  scanKeywords: ["締切", "deadline", "〆切", "提出", "会議", "学会"],
  reminderMinutes: 30,
  categoryColors: {
    class: "#64748b",
    deadline: "#ef4444",
    research: "#3b82f6",
    growth: "#10b981",
    training: "#f97316",
    family: "#8b5cf6",
  },
};

export function loadSettings(): AppSettings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveSettings(settings: AppSettings): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}

export function getDefaultSettings(): AppSettings {
  return { ...DEFAULT_SETTINGS };
}
