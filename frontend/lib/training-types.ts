export interface Exercise {
  name: string;
  reps: string;
  video: string | null;
  note: string;
}

export interface Section {
  name: string;
  exercises: Exercise[];
}

export interface Phase {
  id: number;
  title: string;
  subtitle: string;
  weeks: string;
  color: string;
  goal: string;
  sections: Section[];
  milestones: string[];
}

export interface KajabiMethod {
  name: string;
  steps: string[];
  note: string;
}

export interface KajabiInfo {
  title: string;
  methods: KajabiMethod[];
}

export interface InjuryPreventionItem {
  icon: string;
  title: string;
  desc: string;
}

export interface InjuryPrevention {
  title: string;
  items: InjuryPreventionItem[];
}

export interface TrainingScheduleTemplate {
  dayOfWeek: number;
  sessions: {
    type: "morning" | "noon" | "evening" | "workout" | "breaking" | "acrobat";
    startTime: string;
    enabled: boolean;
  }[];
}

export interface TrainingLog {
  date: string;
  completedExercises: string[];
  weight?: number;
  bodyFat?: number;
  notes?: string;
}

export interface TrainingProgress {
  checkedItems: Record<string, boolean>;
  currentPhase: number;
  logs: TrainingLog[];
}
