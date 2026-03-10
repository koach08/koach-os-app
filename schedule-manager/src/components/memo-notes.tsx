"use client";

import { useState, useEffect } from "react";
import { Pin, X, StickyNote } from "lucide-react";
import type { Memo } from "@/types/task";

const STORAGE_KEY = "schedule-manager-memos";

const MEMO_COLORS = {
  yellow: { bg: "bg-yellow-100 dark:bg-yellow-900/40", border: "border-yellow-300 dark:border-yellow-700", dot: "bg-yellow-400" },
  blue: { bg: "bg-blue-100 dark:bg-blue-900/40", border: "border-blue-300 dark:border-blue-700", dot: "bg-blue-400" },
  green: { bg: "bg-green-100 dark:bg-green-900/40", border: "border-green-300 dark:border-green-700", dot: "bg-green-400" },
  pink: { bg: "bg-pink-100 dark:bg-pink-900/40", border: "border-pink-300 dark:border-pink-700", dot: "bg-pink-400" },
} as const;

function loadMemos(): Memo[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveMemos(memos: Memo[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(memos));
}

export function MemoNotes() {
  const [memos, setMemos] = useState<Memo[]>([]);
  const [input, setInput] = useState("");
  const [selectedColor, setSelectedColor] = useState<Memo["color"]>("yellow");

  useEffect(() => {
    setMemos(loadMemos());
  }, []);

  const updateMemos = (next: Memo[]) => {
    setMemos(next);
    saveMemos(next);
  };

  const addMemo = () => {
    const text = input.trim();
    if (!text) return;
    const memo: Memo = {
      id: `memo_${Date.now()}`,
      content: text,
      color: selectedColor,
      pinned: false,
      createdAt: new Date().toISOString(),
    };
    updateMemos([memo, ...memos]);
    setInput("");
  };

  const deleteMemo = (id: string) => {
    updateMemos(memos.filter((m) => m.id !== id));
  };

  const togglePin = (id: string) => {
    updateMemos(
      memos.map((m) => (m.id === id ? { ...m, pinned: !m.pinned } : m))
    );
  };

  const sorted = [...memos].sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
  });

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <h3 className="mb-3 flex items-center gap-1.5 text-sm font-bold">
        <StickyNote className="h-4 w-4 text-yellow-500" />
        メモ付箋
      </h3>

      {/* Input */}
      <div className="mb-3 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addMemo()}
          placeholder="メモを入力..."
          className="flex-1 rounded-lg border border-border bg-background px-3 py-1.5 text-xs outline-none focus:border-yellow-500"
        />
        <button
          onClick={addMemo}
          disabled={!input.trim()}
          className="rounded-lg bg-yellow-500 px-3 py-1.5 text-xs font-bold text-black transition-opacity disabled:opacity-40"
        >
          追加
        </button>
      </div>

      {/* Color picker */}
      <div className="mb-3 flex items-center gap-1.5">
        <span className="text-[10px] text-muted-foreground">色:</span>
        {(Object.keys(MEMO_COLORS) as Memo["color"][]).map((color) => (
          <button
            key={color}
            onClick={() => setSelectedColor(color)}
            className={`h-4 w-4 rounded-full ${MEMO_COLORS[color].dot} transition-transform ${
              selectedColor === color ? "scale-125 ring-2 ring-white/50" : ""
            }`}
          />
        ))}
      </div>

      {/* Memos list */}
      {sorted.length === 0 ? (
        <p className="text-[11px] text-muted-foreground">メモはまだありません</p>
      ) : (
        <div className="space-y-1.5">
          {sorted.map((memo) => {
            const style = MEMO_COLORS[memo.color];
            return (
              <div
                key={memo.id}
                className={`group relative rounded-lg border ${style.border} ${style.bg} px-3 py-2`}
              >
                <p className="pr-10 text-[11px] leading-relaxed text-foreground">
                  {memo.content}
                </p>
                <div className="absolute right-1.5 top-1.5 flex gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                  <button
                    onClick={() => togglePin(memo.id)}
                    className={`rounded p-0.5 hover:bg-black/10 ${
                      memo.pinned ? "opacity-100" : ""
                    }`}
                    title={memo.pinned ? "ピン解除" : "ピン留め"}
                  >
                    <Pin
                      className={`h-3 w-3 ${
                        memo.pinned
                          ? "fill-current text-foreground"
                          : "text-muted-foreground"
                      }`}
                    />
                  </button>
                  <button
                    onClick={() => deleteMemo(memo.id)}
                    className="rounded p-0.5 hover:bg-black/10"
                    title="削除"
                  >
                    <X className="h-3 w-3 text-muted-foreground" />
                  </button>
                </div>
                {memo.pinned && (
                  <Pin className="absolute right-2 top-2 h-3 w-3 fill-current text-foreground group-hover:hidden" />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
