"use client";

import { LEVEL_COLORS, type Level } from "@/lib/types";

interface Props {
  level: Level;
  size?: "sm" | "md";
}

export function LevelBadge({ level, size = "md" }: Props) {
  const color = LEVEL_COLORS[level];
  const cls = size === "sm" ? "text-xs px-1.5 py-0.5" : "text-sm px-2 py-1";

  return (
    <span
      className={`${cls} rounded-full font-mono font-bold`}
      style={{ background: `${color}20`, color, border: `1px solid ${color}40` }}
    >
      {level}
    </span>
  );
}
