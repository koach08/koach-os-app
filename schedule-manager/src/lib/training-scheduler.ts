import { addDays, format, startOfWeek, parse } from "date-fns";
import { PHASES } from "./training-data";
import type { TrainingScheduleTemplate } from "@/types/training";

type SessionType = TrainingScheduleTemplate["sessions"][number]["type"];

const SESSION_CONFIG: Record<
  SessionType,
  { label: string; emoji: string; durationMinutes: number; sectionPattern: string }
> = {
  morning: { label: "朝ルーティン", emoji: "🌅", durationMinutes: 7, sectionPattern: "朝" },
  noon: { label: "昼ルーティン", emoji: "🏢", durationMinutes: 7, sectionPattern: "昼" },
  evening: { label: "夜ルーティン", emoji: "🌙", durationMinutes: 10, sectionPattern: "夜" },
  workout: { label: "筋力トレーニング", emoji: "🏋️", durationMinutes: 45, sectionPattern: "筋力" },
  breaking: { label: "ブレイキン練習", emoji: "🔥", durationMinutes: 60, sectionPattern: "ブレイキン" },
  acrobat: { label: "アクロバット", emoji: "🤸", durationMinutes: 60, sectionPattern: "アクロバット" },
};

function getSectionExercises(phaseId: number, sectionPattern: string): string {
  const phase = PHASES[phaseId];
  if (!phase) return "";

  const section = phase.sections.find((s) =>
    s.name.includes(sectionPattern)
  );
  if (!section) return "";

  return section.exercises
    .map((ex) => `${ex.name} ${ex.reps}`)
    .join("\n");
}

export function generateCalendarEvents(
  templates: TrainingScheduleTemplate[],
  phaseId: number,
  startDate: Date,
  weeks: number
): {
  summary: string;
  description: string;
  start: { dateTime: string };
  end: { dateTime: string };
  colorId: string;
  reminders: { useDefault: boolean; overrides: { method: string; minutes: number }[] };
}[] {
  const phase = PHASES[phaseId];
  if (!phase) return [];

  const events: ReturnType<typeof generateCalendarEvents> = [];
  const weekStart = startOfWeek(startDate, { weekStartsOn: 1 }); // Monday

  for (let w = 0; w < weeks; w++) {
    for (const template of templates) {
      const dayDate = addDays(weekStart, w * 7 + ((template.dayOfWeek + 6) % 7));

      for (const session of template.sessions) {
        if (!session.enabled) continue;

        const config = SESSION_CONFIG[session.type];
        const [hours, minutes] = session.startTime.split(":").map(Number);

        const startDt = new Date(dayDate);
        startDt.setHours(hours, minutes, 0, 0);

        const endDt = new Date(startDt);
        endDt.setMinutes(endDt.getMinutes() + config.durationMinutes);

        const description = getSectionExercises(phaseId, config.sectionPattern);

        events.push({
          summary: `${config.emoji} ${config.label}（Phase ${phaseId}）`,
          description: description || `${config.label} - ${phase.title}`,
          start: { dateTime: format(startDt, "yyyy-MM-dd'T'HH:mm:ssxxx") },
          end: { dateTime: format(endDt, "yyyy-MM-dd'T'HH:mm:ssxxx") },
          colorId: "6", // orange for training
          reminders: {
            useDefault: false,
            overrides: [
              { method: "popup", minutes: session.type === "morning" ? 5 : 15 },
            ],
          },
        });
      }
    }
  }

  return events.sort(
    (a, b) =>
      new Date(a.start.dateTime).getTime() - new Date(b.start.dateTime).getTime()
  );
}

export function getDefaultTemplates(): TrainingScheduleTemplate[] {
  const DAYS = [1, 2, 3, 4, 5, 6, 0]; // Mon-Sun

  return DAYS.map((dayOfWeek) => ({
    dayOfWeek,
    sessions: [
      { type: "morning" as const, startTime: "06:30", enabled: dayOfWeek !== 0 },
      { type: "noon" as const, startTime: "12:15", enabled: dayOfWeek >= 1 && dayOfWeek <= 5 },
      { type: "evening" as const, startTime: "22:00", enabled: dayOfWeek !== 0 },
      {
        type: "workout" as const,
        startTime: "18:00",
        enabled: dayOfWeek === 2 || dayOfWeek === 5, // Tue, Fri
      },
      {
        type: "breaking" as const,
        startTime: "19:00",
        enabled: dayOfWeek === 6, // Sat
      },
      {
        type: "acrobat" as const,
        startTime: "14:00",
        enabled: false,
      },
    ],
  }));
}

export const DAY_LABELS = ["日", "月", "火", "水", "木", "金", "土"];

export const SESSION_LABELS: Record<SessionType, { label: string; emoji: string; color: string }> = {
  morning: { label: "朝ルーティン", emoji: "🌅", color: "#fbbf24" },
  noon: { label: "昼ルーティン", emoji: "🏢", color: "#60a5fa" },
  evening: { label: "夜ルーティン", emoji: "🌙", color: "#818cf8" },
  workout: { label: "筋力トレーニング", emoji: "🏋️", color: "#f87171" },
  breaking: { label: "ブレイキン", emoji: "🔥", color: "#fb923c" },
  acrobat: { label: "アクロバット", emoji: "🤸", color: "#34d399" },
};
