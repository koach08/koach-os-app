export type Domain =
  | "teaching"
  | "research"
  | "platform"
  | "revenue"
  | "personal"
  | "business";

export type Level = "L1" | "L2" | "L3" | "L4";
export type Engine = "claude" | "gpt";
export type Gradient = "soft" | "medium" | "direct" | "blunt";

export interface MessageMetadata {
  engine: Engine;
  model: string;
  level: Level;
  biases: string[];
  task_type: string;
  gradient: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata?: MessageMetadata;
  files?: { name: string; size: number; type: string }[];
  timestamp: string;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  domain: Domain;
  intervention_level: Level;
  routing: { engine: Engine; model: string; reason: string };
  cognitive_biases: { detected: string[]; labels: string[] };
  user_input_preview: string;
  ai_response_preview: string;
  task_type: string;
}

export interface WeeklySummary {
  id: string;
  period_start: string;
  period_end: string;
  total_interactions: number;
  domain_distribution: Record<string, number>;
  level_distribution: Record<string, number>;
  bias_frequency: Record<string, number>;
  counterpoint_rate_pct: number;
  routing_distribution: Record<string, number>;
  generated_at: string;
}

export const DOMAIN_LABELS: Record<Domain, string> = {
  teaching: "Teaching",
  research: "Research",
  platform: "Platform",
  revenue: "Revenue",
  personal: "Personal",
  business: "Business",
};

export const DOMAIN_EMOJI: Record<Domain, string> = {
  teaching: "📚",
  research: "🔬",
  platform: "💻",
  revenue: "💰",
  personal: "🧘",
  business: "📈",
};

export const LEVEL_COLORS: Record<Level, string> = {
  L1: "#22c55e",
  L2: "#eab308",
  L3: "#f97316",
  L4: "#ef4444",
};
