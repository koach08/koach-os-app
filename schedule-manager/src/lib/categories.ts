export type CategoryId =
  | "class"
  | "deadline"
  | "research"
  | "growth"
  | "training"
  | "family";

export interface Category {
  id: CategoryId;
  label: string;
  color: string;
  keywords: string[];
}

export const CATEGORIES: Category[] = [
  {
    id: "class",
    label: "授業・会議",
    color: "#64748b",
    keywords: [
      "授業", "講義", "会議", "ミーティング", "meeting", "class", "lecture",
      "セミナー", "seminar", "ゼミ", "教授会", "委員会", "オフィスアワー",
    ],
  },
  {
    id: "deadline",
    label: "締切",
    color: "#ef4444",
    keywords: [
      "締切", "〆切", "deadline", "提出", "submit", "due", "期限",
      "申請", "報告", "レポート",
    ],
  },
  {
    id: "research",
    label: "研究",
    color: "#3b82f6",
    keywords: [
      "研究", "論文", "paper", "research", "執筆", "writing", "投稿",
      "アーカイブ", "KAKENHI", "科研費", "学会", "conference",
    ],
  },
  {
    id: "growth",
    label: "Growth",
    color: "#10b981",
    keywords: [
      "開発", "dev", "プラットフォーム", "platform", "Kindle", "収益",
      "revenue", "EdTech", "consulting", "コンサル", "Redbubble",
    ],
  },
  {
    id: "training",
    label: "トレーニング",
    color: "#f97316",
    keywords: [
      "トレーニング", "training", "ジム", "gym", "ブレイキン", "breaking",
      "筋トレ", "ストレッチ", "stretch", "ルーティン", "routine",
      "朝ルーティン", "夜ルーティン", "有酸素", "アクロバット",
    ],
  },
  {
    id: "family",
    label: "家族",
    color: "#8b5cf6",
    keywords: [
      "家族", "family", "育児", "子ども", "妻", "病院", "保育園",
      "幼稚園", "ペルシア語", "Persian",
    ],
  },
];

export function classifyEvent(title: string, description?: string): Category {
  const text = `${title} ${description || ""}`.toLowerCase();
  for (const cat of CATEGORIES) {
    for (const kw of cat.keywords) {
      if (text.includes(kw.toLowerCase())) {
        return cat;
      }
    }
  }
  return CATEGORIES[0]; // default: 授業・会議
}

// Google Calendar colorId mapping (approximate)
export function getCategoryColorId(categoryId: CategoryId): string {
  const map: Record<CategoryId, string> = {
    class: "8",     // graphite
    deadline: "11",  // tomato
    research: "9",   // blueberry
    growth: "2",     // sage
    training: "6",   // tangerine
    family: "3",     // grape
  };
  return map[categoryId];
}
