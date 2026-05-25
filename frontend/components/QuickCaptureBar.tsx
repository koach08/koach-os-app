"use client";

import { useEffect, useRef, useState } from "react";

type Classified = {
  kind: "memo" | "backlog" | "decision" | "failure";
  title: string;
  body: string;
  category: string;
  urgency: "high" | "medium" | "low";
};

type Result = {
  kind: string;
  title: string;
  ok: boolean;
};

const KIND_LABEL: Record<string, string> = {
  memo: "🪧 memo",
  backlog: "📋 backlog",
  decision: "🧭 decision",
  failure: "🪨 failure",
};

export function QuickCaptureBar({ onSaved }: { onSaved?: () => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState<"recording" | "transcribing" | "classifying" | null>(null);
  const [lastResult, setLastResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // textarea auto-grow
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [text]);

  // result toast fade
  useEffect(() => {
    if (!lastResult) return;
    const t = setTimeout(() => setLastResult(null), 3500);
    return () => clearTimeout(t);
  }, [lastResult]);

  // global Cmd+Shift+M to start/stop recording
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "m") {
        e.preventDefault();
        busy === "recording" ? stopRec() : startRec();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busy]);

  const saveCaptured = async (content: string, classified?: Classified) => {
    setBusy("classifying");
    setError(null);
    try {
      const r = await fetch("/api/voice/capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          classified
            ? { text: content, ...classified }
            : { text: content },
        ),
      });
      if (!r.ok) throw new Error(`save ${r.status}`);
      const d = await r.json();
      setLastResult({
        kind: d.kind,
        title: d.saved?.title || d.saved?.what || (d.saved?.content ?? "").split("\n")[0] || content.slice(0, 40),
        ok: true,
      });
      setText("");
      onSaved?.();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const sendTyped = async () => {
    const t = text.trim();
    if (!t || busy) return;
    await saveCaptured(t);
  };

  const startRec = async () => {
    if (busy) return;
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4";
      const mr = new MediaRecorder(stream, { mimeType: mime });
      chunksRef.current = [];
      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: mime });
        await transcribeAndSave(blob, mime);
      };
      mr.start();
      mediaRef.current = mr;
      setBusy("recording");
    } catch (e) {
      setError("マイクが使えません: " + (e as Error).message);
    }
  };

  const stopRec = () => {
    if (mediaRef.current && mediaRef.current.state !== "inactive") {
      mediaRef.current.stop();
    }
  };

  const transcribeAndSave = async (blob: Blob, mime: string) => {
    setBusy("transcribing");
    try {
      const ext = mime.includes("mp4") ? "mp4" : "webm";
      const fd = new FormData();
      fd.append("file", blob, `voice.${ext}`);
      const r = await fetch("/api/voice/transcribe", { method: "POST", body: fd });
      if (!r.ok) throw new Error(`whisper ${r.status}`);
      const { text: transcript } = await r.json();
      if (!transcript) {
        setError("聞き取れませんでした");
        setBusy(null);
        return;
      }
      await saveCaptured(transcript);
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
    }
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 px-4 pb-4 md:pb-6 pointer-events-none">
      <div className="max-w-3xl mx-auto pointer-events-auto">
        {/* Result toast */}
        {lastResult && (
          <div
            className="mb-2 px-3 py-2 rounded-xl text-xs flex items-center gap-2 mx-auto w-fit"
            style={{
              background: "rgba(16, 185, 129, 0.12)",
              border: "1px solid rgba(16, 185, 129, 0.3)",
              color: "#10b981",
              backdropFilter: "blur(8px)",
            }}
          >
            <span>✓</span>
            <span>{KIND_LABEL[lastResult.kind] || lastResult.kind}</span>
            <span style={{ color: "var(--color-text)" }}>{lastResult.title}</span>
          </div>
        )}
        {error && (
          <div
            className="mb-2 px-3 py-2 rounded-xl text-xs mx-auto w-fit"
            style={{ background: "rgba(239, 68, 68, 0.12)", border: "1px solid rgba(239, 68, 68, 0.3)", color: "#ef4444", backdropFilter: "blur(8px)" }}
          >
            {error}
          </div>
        )}

        <div
          className="rounded-2xl flex items-end gap-2 p-2"
          style={{
            background: "rgba(20, 20, 22, 0.9)",
            border: "1px solid var(--color-border)",
            boxShadow: "0 10px 40px rgba(0,0,0,0.4)",
            backdropFilter: "blur(12px)",
          }}
        >
          <textarea
            ref={inputRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                sendTyped();
              }
            }}
            placeholder={busy === "recording" ? "録音中..." : busy === "transcribing" ? "文字起こし中..." : busy === "classifying" ? "保存中..." : "メモを書く / Enter で保存 / Shift+Enter 改行"}
            disabled={busy === "recording" || busy === "transcribing"}
            rows={1}
            className="flex-1 px-3 py-2 text-sm resize-none bg-transparent outline-none disabled:opacity-50"
            style={{ color: "var(--color-text)", maxHeight: "160px", minHeight: "36px" }}
          />

          <button
            onClick={busy === "recording" ? stopRec : startRec}
            disabled={busy === "transcribing" || busy === "classifying"}
            title={busy === "recording" ? "録音停止" : "録音開始 (Cmd+Shift+M)"}
            className="shrink-0 w-9 h-9 rounded-xl flex items-center justify-center disabled:opacity-50"
            style={{
              background:
                busy === "recording" ? "#ef4444" : "var(--color-surface-hover)",
              color: busy === "recording" ? "white" : "var(--color-text)",
              animation: busy === "recording" ? "pulse 1.5s infinite" : "none",
            }}
          >
            {busy === "recording" ? "■" : "🎤"}
          </button>

          <button
            onClick={sendTyped}
            disabled={!text.trim() || busy === "recording" || busy === "transcribing" || busy === "classifying"}
            title="保存 (Enter)"
            className="shrink-0 w-9 h-9 rounded-xl flex items-center justify-center disabled:opacity-30"
            style={{
              background: text.trim() ? "var(--color-accent)" : "var(--color-surface-hover)",
              color: text.trim() ? "white" : "var(--color-text-muted)",
            }}
          >
            {busy === "classifying" ? "…" : "↑"}
          </button>
        </div>

        <div className="mt-1.5 text-[10px] text-center" style={{ color: "var(--color-text-muted)" }}>
          AI が memo / backlog / decision / failure に自動振り分け
        </div>
      </div>
    </div>
  );
}
