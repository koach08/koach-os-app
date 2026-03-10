"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { LevelBadge } from "@/components/sidebar/LevelBadge";
import type { ChatMessage } from "@/lib/types";

interface Props {
  message: ChatMessage;
  onEdit?: (messageId: string, newContent: string) => void;
  onDelete?: (messageId: string) => void;
}

export function MessageBubble({ message, onEdit, onDelete }: Props) {
  const isUser = message.role === "user";
  const meta = message.metadata;
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(message.content);
  const [showActions, setShowActions] = useState(false);
  const editRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (isEditing && editRef.current) {
      editRef.current.focus();
      editRef.current.style.height = "auto";
      editRef.current.style.height = editRef.current.scrollHeight + "px";
    }
  }, [isEditing]);

  const handleSaveEdit = () => {
    if (editText.trim() && editText !== message.content) {
      onEdit?.(message.id, editText.trim());
    }
    setIsEditing(false);
  };

  const handleCancelEdit = () => {
    setEditText(message.content);
    setIsEditing(false);
  };

  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (e.nativeEvent.isComposing || e.keyCode === 229) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSaveEdit();
    }
    if (e.key === "Escape") {
      handleCancelEdit();
    }
  };

  return (
    <div
      className={`group flex ${isUser ? "justify-end" : "justify-start"}`}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      <div className="relative">
        <div
          className={`max-w-[85%] rounded-2xl px-5 py-3 ${isUser ? "rounded-br-md" : "rounded-bl-md"}`}
          style={{
            background: isUser ? "var(--color-accent)" : "var(--color-surface)",
            border: isUser ? "none" : "1px solid var(--color-border)",
          }}
        >
          {!isUser && meta && (
            <div className="flex items-center gap-2 mb-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
              <span
                className="px-2 py-0.5 rounded-full font-mono"
                style={{ background: "var(--color-background)", border: "1px solid var(--color-border)" }}
              >
                {meta.engine === "claude" ? "Claude" : "GPT"} · {meta.model.split("-").slice(0, 3).join("-")}
              </span>
              <LevelBadge level={meta.level} size="sm" />
              {meta.biases.length > 0 && (
                <span className="px-2 py-0.5 rounded-full" style={{ background: "#7c3aed20", color: "#a78bfa" }}>
                  {meta.biases.length} bias
                </span>
              )}
            </div>
          )}

          {/* File attachments */}
          {isUser && message.files && message.files.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2">
              {message.files.map((f, i) => (
                <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs" style={{ background: "rgba(255,255,255,0.15)" }}>
                  📎 {f.name}
                </span>
              ))}
            </div>
          )}

          {isEditing ? (
            <div>
              <textarea
                ref={editRef}
                value={editText}
                onChange={(e) => {
                  setEditText(e.target.value);
                  e.target.style.height = "auto";
                  e.target.style.height = e.target.scrollHeight + "px";
                }}
                onKeyDown={handleEditKeyDown}
                className="w-full bg-transparent resize-none outline-none text-base"
                style={{ color: isUser ? "white" : "var(--color-text)", minHeight: "40px" }}
              />
              <div className="flex gap-2 mt-2 text-xs">
                <button
                  onClick={handleSaveEdit}
                  className="px-3 py-1 rounded-md font-medium"
                  style={{ background: "rgba(255,255,255,0.2)" }}
                >
                  Save
                </button>
                <button
                  onClick={handleCancelEdit}
                  className="px-3 py-1 rounded-md"
                  style={{ background: "rgba(255,255,255,0.1)" }}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>

        {/* Action buttons (hover) */}
        {showActions && !isEditing && (
          <div
            className={`absolute top-0 flex gap-1 ${isUser ? "left-0 -translate-x-full pr-2" : "right-0 translate-x-full pl-2"}`}
          >
            {isUser && onEdit && (
              <button
                onClick={() => setIsEditing(true)}
                className="p-1.5 rounded-lg transition-colors hover:bg-[var(--color-surface-hover)]"
                style={{ color: "var(--color-text-muted)" }}
                title="Edit"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
              </button>
            )}
            {onDelete && (
              <button
                onClick={() => onDelete(message.id)}
                className="p-1.5 rounded-lg transition-colors hover:bg-[var(--color-surface-hover)]"
                style={{ color: "var(--color-text-muted)" }}
                title="Delete"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                </svg>
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
