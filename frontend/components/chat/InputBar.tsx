"use client";

import { useState, useRef, useEffect } from "react";

interface AttachedFile {
  name: string;
  size: number;
  type: string;
  content?: string; // base64 or extracted text
}

interface Props {
  onSend: (text: string, files?: AttachedFile[]) => void;
  isLoading: boolean;
}

export type { AttachedFile };

export function InputBar({ onSend, isLoading }: Props) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState<AttachedFile[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + "px";
    }
  }, [text]);

  const handleSubmit = () => {
    if ((!text.trim() && files.length === 0) || isLoading) return;
    onSend(text.trim(), files.length > 0 ? files : undefined);
    setText("");
    setFiles([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // IME変換中（日本語入力の確定Enter等）は送信しない
    if (e.nativeEvent.isComposing || e.keyCode === 229) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (!selectedFiles) return;

    const newFiles: AttachedFile[] = [];
    for (const file of Array.from(selectedFiles)) {
      const isText = file.type.startsWith("text/") ||
        file.name.endsWith(".md") || file.name.endsWith(".json") ||
        file.name.endsWith(".csv") || file.name.endsWith(".yaml") ||
        file.name.endsWith(".yml") || file.name.endsWith(".py") ||
        file.name.endsWith(".js") || file.name.endsWith(".ts") ||
        file.name.endsWith(".tsx");

      let content: string | undefined;
      if (isText) {
        content = await file.text();
      } else {
        // Convert to base64 for binary files (PDF, images, etc.)
        const buffer = await file.arrayBuffer();
        content = btoa(String.fromCharCode(...new Uint8Array(buffer)));
      }

      newFiles.push({
        name: file.name,
        size: file.size,
        type: file.type || "application/octet-stream",
        content,
      });
    }
    setFiles((prev) => [...prev, ...newFiles]);
    e.target.value = "";
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });

        // Send to Whisper API via backend
        const formData = new FormData();
        formData.append("audio", blob, "recording.webm");
        try {
          const res = await fetch("/api/voice/transcribe", { method: "POST", body: formData });
          if (res.ok) {
            const data = await res.json();
            if (data.text) {
              setText((prev) => prev + (prev ? " " : "") + data.text);
            }
          }
        } catch {
          // fallback: ignore transcription errors
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);
      timerRef.current = setInterval(() => setRecordingTime((t) => t + 1), 1000);
    } catch {
      alert("マイクへのアクセスが許可されていません。");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="p-4" style={{ borderTop: "1px solid var(--color-border)" }}>
      {/* Attached files preview */}
      {files.length > 0 && (
        <div className="max-w-3xl mx-auto mb-2 flex flex-wrap gap-2">
          {files.map((file, i) => (
            <div
              key={i}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            >
              <span>📎</span>
              <span className="max-w-[200px] truncate">{file.name}</span>
              <span style={{ color: "var(--color-text-muted)" }}>
                {(file.size / 1024).toFixed(0)}KB
              </span>
              <button
                onClick={() => removeFile(i)}
                className="ml-1 hover:opacity-70"
                style={{ color: "var(--color-text-muted)" }}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      <div
        className="max-w-3xl mx-auto flex items-end gap-2 rounded-2xl p-3"
        style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
      >
        {/* File attach button */}
        <button
          onClick={() => fileInputRef.current?.click()}
          className="p-2 rounded-xl transition-colors hover:bg-[var(--color-surface-hover)]"
          title="ファイルを添付"
          disabled={isLoading}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: "var(--color-text-muted)" }}>
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
          </svg>
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleFileSelect}
          accept=".txt,.md,.pdf,.csv,.json,.yaml,.yml,.py,.js,.ts,.tsx,.doc,.docx,.png,.jpg,.jpeg,.webp"
        />

        {/* Text input */}
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message Koach OS..."
          rows={1}
          className="flex-1 bg-transparent resize-none outline-none text-base"
          style={{ color: "var(--color-text)", maxHeight: "200px" }}
          disabled={isLoading}
        />

        {/* Voice input button */}
        <button
          onClick={isRecording ? stopRecording : startRecording}
          className="p-2 rounded-xl transition-colors"
          style={{
            background: isRecording ? "#ef4444" : "transparent",
            color: isRecording ? "white" : "var(--color-text-muted)",
          }}
          title={isRecording ? "録音停止" : "音声入力"}
          disabled={isLoading}
        >
          {isRecording ? (
            <span className="text-xs font-mono font-bold">{formatTime(recordingTime)}</span>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
              <path d="M19 10v2a7 7 0 01-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          )}
        </button>

        {/* Send button */}
        <button
          onClick={handleSubmit}
          disabled={(!text.trim() && files.length === 0) || isLoading}
          className="p-2 rounded-xl transition-colors disabled:opacity-30"
          style={{ background: "var(--color-accent)" }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
            <path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13" />
          </svg>
        </button>
      </div>
      <p className="text-center text-xs mt-2" style={{ color: "var(--color-text-muted)" }}>
        Koach OS v2 — Opus 4.8 + GPT-5.5 · Shift+Enter for new line
      </p>
    </div>
  );
}
