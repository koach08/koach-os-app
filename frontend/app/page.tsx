"use client";

import { useState, useCallback } from "react";
import { ChatArea } from "@/components/chat/ChatArea";
import { InputBar, type AttachedFile } from "@/components/chat/InputBar";
import { streamChat } from "@/lib/api";
import type { ChatMessage, MessageMetadata } from "@/lib/types";

const ENGINES: { value: string | null; label: string; emoji: string; hint: string }[] = [
  { value: null, label: "Auto", emoji: "✨", hint: "内容に応じて自動選択" },
  { value: "claude", label: "Claude", emoji: "🧠", hint: "思考・戦略" },
  { value: "gpt", label: "GPT", emoji: "🤖", hint: "実行・コード" },
  { value: "grok", label: "Grok", emoji: "🌀", hint: "推論・代替" },
  { value: "gemini", label: "Gemini", emoji: "✨", hint: "長文・解析" },
  { value: "venice", label: "Venice", emoji: "🎭", hint: "制約なし" },
  { value: "perplexity", label: "Perplexity", emoji: "🔍", hint: "Web検索" },
  { value: "groq", label: "Groq", emoji: "⚡", hint: "爆速" },
];

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [streamingMeta, setStreamingMeta] = useState<MessageMetadata | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [engineOverride, setEngineOverride] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (text: string, history: ChatMessage[], files?: AttachedFile[]) => {
      // Build message content with file context
      let fullMessage = text;
      if (files && files.length > 0) {
        const fileContents = files.map((f) => {
          if (f.content && !f.type.startsWith("image/")) {
            return `\n--- File: ${f.name} ---\n${f.content}\n--- End of ${f.name} ---`;
          }
          return `\n[Attached: ${f.name} (${(f.size / 1024).toFixed(0)}KB)]`;
        });
        fullMessage = text + "\n" + fileContents.join("\n");
      }

      setIsLoading(true);
      setStreamingText("");
      setStreamingMeta(null);

      let fullText = "";
      let meta: MessageMetadata | null = null;

      await streamChat(
        {
          message: fullMessage,
          domain: "personal",
          history: history.map((m) => ({ role: m.role, content: m.content })),
          engine_override: engineOverride,
        },
        {
          onMetadata: (m) => {
            meta = m;
            setStreamingMeta(m);
          },
          onText: (chunk) => {
            fullText += chunk;
            setStreamingText(fullText);
          },
          onDone: () => {
            setMessages((prev) => [
              ...prev,
              {
                id: `ai-${Date.now()}`,
                role: "assistant",
                content: fullText,
                metadata: meta || undefined,
                timestamp: new Date().toISOString(),
              },
            ]);
            setStreamingText("");
            setStreamingMeta(null);
            setIsLoading(false);
          },
          onError: (err) => {
            setMessages((prev) => [
              ...prev,
              {
                id: `err-${Date.now()}`,
                role: "assistant",
                content: `Error: ${err}`,
                timestamp: new Date().toISOString(),
              },
            ]);
            setStreamingText("");
            setIsLoading(false);
          },
        }
      );
    },
    [engineOverride]
  );

  const handleSend = useCallback(
    async (text: string, files?: AttachedFile[]) => {
      if (!text.trim() && (!files || files.length === 0)) return;
      if (isLoading) return;

      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: text,
        files: files?.map((f) => ({ name: f.name, size: f.size, type: f.type })),
        timestamp: new Date().toISOString(),
      };
      const newMessages = [...messages, userMsg];
      setMessages(newMessages);

      await sendMessage(text, messages, files);
    },
    [messages, isLoading, sendMessage]
  );

  const handleEdit = useCallback(
    async (messageId: string, newContent: string) => {
      // Find the message index
      const idx = messages.findIndex((m) => m.id === messageId);
      if (idx === -1) return;

      // Keep messages up to and including the edited one, remove everything after
      const updatedMessages = messages.slice(0, idx);
      const editedMsg: ChatMessage = {
        ...messages[idx],
        content: newContent,
      };
      updatedMessages.push(editedMsg);
      setMessages(updatedMessages);

      // If it's a user message, re-send to get a new AI response
      if (editedMsg.role === "user") {
        const historyBefore = updatedMessages.slice(0, -1);
        await sendMessage(newContent, historyBefore);
      }
    },
    [messages, sendMessage]
  );

  const handleDelete = useCallback(
    (messageId: string) => {
      const idx = messages.findIndex((m) => m.id === messageId);
      if (idx === -1) return;
      // Remove this message and all subsequent messages
      setMessages(messages.slice(0, idx));
    },
    [messages]
  );

  return (
    <div className="flex flex-col h-full">
      {/* Engine selector bar */}
      <div
        className="px-4 py-2.5 flex items-center gap-2 overflow-x-auto"
        style={{
          background: "var(--color-surface)",
          borderBottom: "1px solid var(--color-border)",
        }}
      >
        <span
          className="text-[10px] uppercase tracking-wider shrink-0"
          style={{ color: "var(--color-text-muted)", letterSpacing: "0.15em" }}
        >
          Engine
        </span>
        <div className="flex gap-1.5">
          {ENGINES.map((e) => {
            const active = engineOverride === e.value;
            return (
              <button
                key={e.value ?? "auto"}
                onClick={() => setEngineOverride(e.value)}
                disabled={isLoading}
                title={e.hint}
                className="px-3 py-1 rounded-full text-xs whitespace-nowrap transition-all disabled:opacity-50"
                style={{
                  background: active ? "var(--color-text)" : "transparent",
                  color: active ? "var(--color-background)" : "var(--color-text-muted)",
                  border: active
                    ? "1px solid var(--color-text)"
                    : "1px solid var(--color-border)",
                  fontWeight: active ? 600 : 400,
                }}
              >
                <span className="mr-1">{e.emoji}</span>
                {e.label}
              </button>
            );
          })}
        </div>
      </div>

      <ChatArea
        messages={messages}
        streamingText={streamingText}
        streamingMeta={streamingMeta}
        isLoading={isLoading}
        onSend={handleSend}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />
      <InputBar onSend={handleSend} isLoading={isLoading} />
    </div>
  );
}
