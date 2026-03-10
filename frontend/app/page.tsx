"use client";

import { useState, useCallback } from "react";
import { ChatArea } from "@/components/chat/ChatArea";
import { InputBar, type AttachedFile } from "@/components/chat/InputBar";
import { streamChat } from "@/lib/api";
import type { ChatMessage, MessageMetadata } from "@/lib/types";

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [streamingMeta, setStreamingMeta] = useState<MessageMetadata | null>(null);
  const [isLoading, setIsLoading] = useState(false);

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
    []
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
