"use client";

import { useRef, useEffect, useState } from "react";
import { MessageBubble } from "./MessageBubble";
import { TypingIndicator } from "./TypingIndicator";
import type { ChatMessage, MessageMetadata } from "@/lib/types";
import type { AttachedFile } from "./InputBar";

interface Props {
  messages: ChatMessage[];
  streamingText: string;
  streamingMeta: MessageMetadata | null;
  isLoading: boolean;
  onSend?: (text: string, files?: AttachedFile[]) => void;
  onEdit?: (messageId: string, newContent: string) => void;
  onDelete?: (messageId: string) => void;
}

export function ChatArea({ messages, streamingText, streamingMeta, isLoading, onSend, onEdit, onDelete }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [briefing, setBriefing] = useState<string | null>(null);
  const [briefingLoading, setBriefingLoading] = useState(true);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  // Fetch dynamic suggestions and briefing on mount
  useEffect(() => {
    fetch("/api/suggestions")
      .then((r) => r.json())
      .then((data) => {
        if (data.suggestions?.length > 0) setSuggestions(data.suggestions);
      })
      .catch(() => {
        setSuggestions([
          "今週何を優先すべき？",
          "最近の判断を振り返ろう",
          "考えを整理したい",
          "新しいアイデアを議論しよう",
        ]);
      });

    fetch("/api/calendar/briefing")
      .then((r) => r.json())
      .then((data) => {
        if (data.briefing) setBriefing(data.briefing);
      })
      .catch(() => {})
      .finally(() => setBriefingLoading(false));
  }, []);

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center overflow-y-auto">
        <div className="text-center max-w-lg py-8">
          <h1 className="text-3xl font-bold mb-1" style={{ color: "var(--color-text)" }}>
            Koach OS
          </h1>
          <p style={{ color: "var(--color-text-muted)" }} className="text-sm mb-6">
            Your Alfred — always at your service.
          </p>

          {/* Daily Briefing */}
          {briefingLoading ? (
            <div className="mb-6 p-4 rounded-xl text-sm text-left" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
              <span style={{ color: "var(--color-text-muted)" }}>Preparing your briefing...</span>
            </div>
          ) : briefing ? (
            <div className="mb-6 p-4 rounded-xl text-sm text-left whitespace-pre-wrap" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}>
              {briefing}
            </div>
          ) : null}

          <div
            className="grid grid-cols-2 gap-3 text-sm"
            style={{ color: "var(--color-text-muted)" }}
          >
            {suggestions.map((prompt) => (
              <button
                key={prompt}
                onClick={() => onSend?.(prompt)}
                className="p-3 rounded-lg cursor-pointer transition-colors text-left hover:brightness-125"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="max-w-3xl mx-auto space-y-6">
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            onEdit={onEdit}
            onDelete={onDelete}
          />
        ))}
        {streamingText && (
          <TypingIndicator text={streamingText} metadata={streamingMeta} />
        )}
        {isLoading && !streamingText && (
          <div className="flex gap-2 items-center" style={{ color: "var(--color-text-muted)" }}>
            <div className="flex gap-1">
              <span className="w-2 h-2 rounded-full animate-bounce" style={{ background: "var(--color-accent)", animationDelay: "0ms" }} />
              <span className="w-2 h-2 rounded-full animate-bounce" style={{ background: "var(--color-accent)", animationDelay: "150ms" }} />
              <span className="w-2 h-2 rounded-full animate-bounce" style={{ background: "var(--color-accent)", animationDelay: "300ms" }} />
            </div>
            <span className="text-sm">Thinking...</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
