"use client";

import { useRef, useState } from "react";

type Classified = {
  kind: "memo" | "backlog" | "decision" | "failure";
  title: string;
  body: string;
  category: string;
  urgency: "high" | "medium" | "low";
};

const KIND_META: Record<string, { emoji: string; label: string }> = {
  memo: { emoji: "🪧", label: "メモ" },
  backlog: { emoji: "📋", label: "バックログ" },
  decision: { emoji: "🧭", label: "決定" },
  failure: { emoji: "🪨", label: "失敗ログ" },
};

export function VoiceCapture({ onSaved }: { onSaved?: () => void }) {
  const [open, setOpen] = useState(false);
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [text, setText] = useState("");
  const [classified, setClassified] = useState<Classified | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const reset = () => {
    setText("");
    setClassified(null);
    setSaved(false);
    setError(null);
  };

  const close = () => {
    setOpen(false);
    setTimeout(reset, 300);
  };

  const startRec = async () => {
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
        await uploadAndClassify(blob, mime);
      };
      mr.start();
      mediaRef.current = mr;
      setRecording(true);
    } catch (e) {
      setError("マイク使用が拒否されました: " + (e as Error).message);
    }
  };

  const stopRec = () => {
    if (mediaRef.current && mediaRef.current.state !== "inactive") {
      mediaRef.current.stop();
    }
    setRecording(false);
  };

  const uploadAndClassify = async (blob: Blob, mime: string) => {
    setProcessing(true);
    setError(null);
    try {
      const ext = mime.includes("mp4") ? "mp4" : "webm";
      const fd = new FormData();
      fd.append("file", blob, `voice.${ext}`);
      const tres = await fetch("/api/voice/transcribe", { method: "POST", body: fd });
      if (!tres.ok) throw new Error("transcribe " + tres.status);
      const { text: transcript } = await tres.json();
      setText(transcript);
      if (!transcript) {
        setError("音声から文字起こしできませんでした");
        return;
      }
      const cres = await fetch("/api/voice/classify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: transcript }),
      });
      if (cres.ok) {
        setClassified(await cres.json());
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setProcessing(false);
    }
  };

  const save = async () => {
    if (!classified) return;
    setError(null);
    try {
      const r = await fetch("/api/voice/capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, ...classified }),
      });
      if (!r.ok) throw new Error("save " + r.status);
      setSaved(true);
      onSaved?.();
      setTimeout(close, 1200);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        title="音声で捕捉"
        className="w-11 h-11 rounded-full flex items-center justify-center transition-all hover:scale-105"
        style={{
          background: "var(--color-accent)",
          color: "white",
          boxShadow: "0 4px 14px rgba(59, 130, 246, 0.35)",
        }}
      >
        🎤
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-end md:items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.6)" }}
          onClick={close}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="rounded-3xl p-6 w-full max-w-lg space-y-4"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
          >
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">音声で捕捉</h3>
              <button onClick={close} className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                閉じる
              </button>
            </div>

            {!text && !processing && (
              <div className="text-center py-6">
                <button
                  onClick={recording ? stopRec : startRec}
                  className="w-24 h-24 rounded-full text-3xl transition-all"
                  style={{
                    background: recording ? "#ef4444" : "var(--color-accent)",
                    color: "white",
                    boxShadow: recording
                      ? "0 0 0 8px rgba(239, 68, 68, 0.15)"
                      : "0 4px 20px rgba(59, 130, 246, 0.35)",
                    animation: recording ? "pulse 1.5s infinite" : "none",
                  }}
                >
                  {recording ? "■" : "🎤"}
                </button>
                <p className="mt-4 text-sm" style={{ color: "var(--color-text-muted)" }}>
                  {recording ? "録音中。タップで停止" : "タップで録音開始"}
                </p>
              </div>
            )}

            {processing && (
              <div className="text-center py-8">
                <div className="text-sm">文字起こし + 分類中...</div>
              </div>
            )}

            {text && !processing && (
              <>
                <div>
                  <label className="block text-[10px] mb-1 uppercase" style={{ color: "var(--color-text-muted)" }}>
                    文字起こし
                  </label>
                  <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    rows={3}
                    className="w-full px-3 py-2 rounded text-sm"
                    style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                  />
                </div>

                {classified && (
                  <>
                    <div>
                      <label className="block text-[10px] mb-1 uppercase" style={{ color: "var(--color-text-muted)" }}>
                        宛先
                      </label>
                      <div className="flex flex-wrap gap-2">
                        {(["memo", "backlog", "decision", "failure"] as const).map((k) => (
                          <button
                            key={k}
                            onClick={() => setClassified({ ...classified, kind: k })}
                            className="px-3 py-1.5 rounded-full text-xs"
                            style={{
                              background: classified.kind === k ? "var(--color-text)" : "transparent",
                              color: classified.kind === k ? "var(--color-background)" : "var(--color-text-muted)",
                              border: "1px solid var(--color-border)",
                            }}
                          >
                            {KIND_META[k].emoji} {KIND_META[k].label}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-[10px] mb-1 uppercase" style={{ color: "var(--color-text-muted)" }}>
                          タイトル
                        </label>
                        <input
                          value={classified.title}
                          onChange={(e) => setClassified({ ...classified, title: e.target.value })}
                          className="w-full px-3 py-2 rounded text-sm"
                          style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] mb-1 uppercase" style={{ color: "var(--color-text-muted)" }}>
                          カテゴリ
                        </label>
                        <input
                          value={classified.category}
                          onChange={(e) => setClassified({ ...classified, category: e.target.value })}
                          className="w-full px-3 py-2 rounded text-sm"
                          style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                        />
                      </div>
                    </div>
                  </>
                )}
                {error && (
                  <div className="text-xs" style={{ color: "var(--color-red)" }}>
                    {error}
                  </div>
                )}
                <div className="flex justify-between items-center">
                  <button
                    onClick={() => {
                      reset();
                      startRec();
                    }}
                    className="text-xs"
                    style={{ color: "var(--color-text-muted)" }}
                  >
                    もう一度録音
                  </button>
                  <div className="flex gap-2">
                    <button
                      onClick={save}
                      disabled={!classified || saved}
                      className="px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50"
                      style={{ background: "var(--color-accent)", color: "white" }}
                    >
                      {saved ? "✓ 保存" : "保存"}
                    </button>
                  </div>
                </div>
              </>
            )}

            {error && !text && (
              <div className="text-sm" style={{ color: "var(--color-red)" }}>
                {error}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
