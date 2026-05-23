"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";

/**
 * Web Share Target endpoint.
 * iOS / Android で Safari の「共有 → Koach OS」から呼ばれる。
 * URL / title / text を組み合わせて memo or backlog に投げ込む。
 */
function ShareContent() {
  const params = useSearchParams();
  const router = useRouter();
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<"memo" | "backlog">("memo");
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const t = params.get("title") ?? "";
    const tx = params.get("text") ?? "";
    const u = params.get("url") ?? "";
    setTitle(t || u || "共有メモ");
    setText([tx, u].filter(Boolean).join("\n"));
  }, [params]);

  const save = async () => {
    setSaving(true);
    try {
      await fetch("/api/voice/capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text || title,
          kind,
          title,
          body: text,
          category: "other",
          urgency: "medium",
        }),
      });
      setDone(true);
      setTimeout(() => router.push("/daily"), 1000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-md mx-auto space-y-4">
        <h1 className="text-2xl font-bold">共有された内容</h1>
        <div>
          <label className="block text-xs mb-1 uppercase" style={{ color: "var(--color-text-muted)" }}>
            タイトル
          </label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-3 py-2 rounded text-sm"
            style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
          />
        </div>
        <div>
          <label className="block text-xs mb-1 uppercase" style={{ color: "var(--color-text-muted)" }}>
            本文 / URL
          </label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={5}
            className="w-full px-3 py-2 rounded text-sm"
            style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
          />
        </div>
        <div className="flex gap-2">
          {(["memo", "backlog"] as const).map((k) => (
            <button
              key={k}
              onClick={() => setKind(k)}
              className="px-3 py-1.5 rounded-full text-xs"
              style={{
                background: kind === k ? "var(--color-text)" : "transparent",
                color: kind === k ? "var(--color-background)" : "var(--color-text-muted)",
                border: "1px solid var(--color-border)",
              }}
            >
              {k === "memo" ? "🪧 メモ" : "📋 バックログ"}
            </button>
          ))}
        </div>
        <button
          onClick={save}
          disabled={saving || done}
          className="w-full py-3 rounded-full text-sm font-medium disabled:opacity-50"
          style={{ background: "var(--color-accent)", color: "white" }}
        >
          {done ? "✓ 保存しました" : saving ? "保存中..." : "保存"}
        </button>
      </div>
    </div>
  );
}

export default function SharePage() {
  return (
    <Suspense fallback={<div className="flex-1 p-6">読み込み中...</div>}>
      <ShareContent />
    </Suspense>
  );
}
