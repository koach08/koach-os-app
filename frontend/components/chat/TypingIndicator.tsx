"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { LevelBadge } from "@/components/sidebar/LevelBadge";
import type { MessageMetadata } from "@/lib/types";

interface Props {
  text: string;
  metadata: MessageMetadata | null;
}

export function TypingIndicator({ text, metadata }: Props) {
  return (
    <div className="flex justify-start">
      <div
        className="max-w-[85%] rounded-2xl rounded-bl-md px-5 py-3"
        style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
      >
        {metadata && (
          <div className="flex items-center gap-2 mb-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
            <span
              className="px-2 py-0.5 rounded-full font-mono"
              style={{ background: "var(--color-background)", border: "1px solid var(--color-border)" }}
            >
              {metadata.engine === "claude" ? "Claude" : "GPT"} · {metadata.model.split("-").slice(0, 3).join("-")}
            </span>
            <LevelBadge level={metadata.level} size="sm" />
          </div>
        )}
        <div className="prose typing-cursor">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
