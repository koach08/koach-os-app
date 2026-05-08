"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  analyzeText,
  analyzeBatch,
  analyzeUrl,
  analyzeGDrive,
  fetchStyleGuide,
  fetchSampleCount,
  regenerateStyleGuide,
} from "@/lib/api";

const GENRES = [
  { value: "academic", label: "Academic / 学術" },
  { value: "sns", label: "SNS" },
  { value: "business", label: "Business / ビジネス" },
  { value: "general", label: "General / 一般" },
];

type InputMode = "text" | "file" | "url" | "gdrive";

const INPUT_MODES: { value: InputMode; label: string; icon: string }[] = [
  { value: "text", label: "Text", icon: "📝" },
  { value: "file", label: "Files", icon: "📄" },
  { value: "url", label: "URL", icon: "🔗" },
  { value: "gdrive", label: "Drive", icon: "📁" },
];

const ACCEPTED_FILES = ".txt,.md,.pdf,.docx,.doc";

interface BatchResult {
  total: number;
  analyzed: number;
  failed: number;
  results: { file: string; id: string; extracted_length: number; voice_summary: string }[];
  errors: { file: string; error: string }[];
}

export default function AnalyzePage() {
  // Input state
  const [mode, setMode] = useState<InputMode>("text");
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [url, setUrl] = useState("");
  const [gdriveUrl, setGdriveUrl] = useState("");
  const [context, setContext] = useState("");
  const [genre, setGenre] = useState("general");
  const fileRef = useRef<HTMLInputElement>(null);

  // Output state
  const [analyzing, setAnalyzing] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [singleResult, setSingleResult] = useState<Record<string, unknown> | null>(null);
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null);
  const [styleGuide, setStyleGuide] = useState("");
  const [sampleCount, setSampleCount] = useState<{ total: number; by_genre: Record<string, number> } | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const loadStyleGuide = useCallback(async () => {
    try {
      const [guide, counts] = await Promise.all([fetchStyleGuide(), fetchSampleCount()]);
      if (guide.exists) setStyleGuide(guide.content);
      setSampleCount(counts);
    } catch {
      // not available yet
    }
  }, []);

  useEffect(() => {
    loadStyleGuide();
  }, [loadStyleGuide]);

  const canAnalyze = () => {
    if (analyzing) return false;
    if (mode === "text") return text.trim().length >= 50;
    if (mode === "file") return files.length > 0;
    if (mode === "url") return url.trim().length > 10;
    if (mode === "gdrive") return gdriveUrl.trim().length > 10;
    return false;
  };

  const handleAnalyze = async () => {
    setError("");
    setAnalyzing(true);
    setSingleResult(null);
    setBatchResult(null);

    try {
      if (mode === "text") {
        if (text.trim().length < 50) { setError("50文字以上入力してください"); return; }
        const res = await analyzeText(text, context, genre);
        setSingleResult(res);
      } else if (mode === "file") {
        if (files.length === 0) { setError("ファイルを選択してください"); return; }
        const res = await analyzeBatch(files, context, genre);
        setBatchResult(res);
      } else if (mode === "url") {
        if (!url.trim()) { setError("URLを入力してください"); return; }
        const res = await analyzeUrl(url, genre);
        setSingleResult(res);
      } else if (mode === "gdrive") {
        if (!gdriveUrl.trim()) { setError("Google DriveのURLを入力してください"); return; }
        const res = await analyzeGDrive(gdriveUrl, genre);
        setSingleResult(res);
      }
      await loadStyleGuide();
    } catch (err) {
      setError(String(err));
    } finally {
      setAnalyzing(false);
    }
  };

  const handleRegenerate = async () => {
    setRegenerating(true);
    setError("");
    try {
      const res = await regenerateStyleGuide();
      setStyleGuide(res.content);
      const counts = await fetchSampleCount();
      setSampleCount(counts);
    } catch (err) {
      setError(String(err));
    } finally {
      setRegenerating(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(styleGuide);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([styleGuide], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "koach_style_guide.md";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const dropped = Array.from(e.dataTransfer.files);
    if (dropped.length > 0) setFiles((prev) => [...prev, ...dropped]);
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold mb-1">Writing Style Analyzer</h1>
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              テキスト・ファイル・SNS・Google Driveから文体を分析してスタイルガイドを生成
            </p>
          </div>
          {sampleCount && sampleCount.total > 0 && (
            <div
              className="text-right px-4 py-2 rounded-lg"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            >
              <div className="text-lg font-bold" style={{ color: "var(--color-accent)" }}>
                {sampleCount.total}
              </div>
              <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                samples
              </div>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* ─── Left: Input ─── */}
          <div className="space-y-4">
            {/* Mode Tabs */}
            <div className="flex gap-1 p-1 rounded-lg" style={{ background: "var(--color-surface)" }}>
              {INPUT_MODES.map((m) => (
                <button
                  key={m.value}
                  onClick={() => setMode(m.value)}
                  className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-sm transition-colors"
                  style={{
                    background: mode === m.value ? "var(--color-accent)" : "transparent",
                    color: mode === m.value ? "white" : "var(--color-text-muted)",
                  }}
                >
                  <span>{m.icon}</span>
                  <span>{m.label}</span>
                </button>
              ))}
            </div>

            {/* Input Area */}
            <div
              className="rounded-xl p-4"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            >
              {/* TEXT MODE */}
              {mode === "text" && (
                <>
                  <label className="block text-sm font-medium mb-2">Text / テキスト</label>
                  <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="SNS投稿、論文の一節、メール文面など..."
                    rows={10}
                    className="w-full px-3 py-2 rounded-lg text-sm resize-none"
                    style={{
                      background: "var(--color-background)",
                      border: "1px solid var(--color-border)",
                      color: "var(--color-text)",
                    }}
                  />
                  <div className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                    {text.length} chars {text.length > 0 && text.length < 50 && " (min 50)"}
                  </div>
                </>
              )}

              {/* FILE MODE — Batch */}
              {mode === "file" && (
                <>
                  <label className="block text-sm font-medium mb-2">
                    Files / ファイル一括アップロード
                  </label>
                  <div
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={handleFileDrop}
                    onClick={() => fileRef.current?.click()}
                    className="flex flex-col items-center justify-center gap-2 cursor-pointer rounded-lg transition-colors"
                    style={{
                      background: "var(--color-background)",
                      border: "2px dashed var(--color-border)",
                      padding: "32px 20px",
                    }}
                  >
                    <span className="text-3xl">📂</span>
                    <span className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                      Click or drag files here (multiple OK)
                    </span>
                    <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                      PDF, Word (.docx), .txt, .md
                    </span>
                  </div>
                  <input
                    ref={fileRef}
                    type="file"
                    accept={ACCEPTED_FILES}
                    multiple
                    className="hidden"
                    onChange={(e) => {
                      const newFiles = Array.from(e.target.files || []);
                      if (newFiles.length > 0) setFiles((prev) => [...prev, ...newFiles]);
                    }}
                  />

                  {/* File List */}
                  {files.length > 0 && (
                    <div className="mt-3 space-y-1">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium" style={{ color: "var(--color-text-muted)" }}>
                          {files.length} file{files.length > 1 ? "s" : ""} selected
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setFiles([]);
                            if (fileRef.current) fileRef.current.value = "";
                          }}
                          className="text-xs px-2 py-0.5 rounded"
                          style={{ color: "#ef4444" }}
                        >
                          Clear all
                        </button>
                      </div>
                      <div className="max-h-[200px] overflow-y-auto space-y-1">
                        {files.map((f, i) => (
                          <div
                            key={`${f.name}-${i}`}
                            className="flex items-center justify-between px-3 py-1.5 rounded-lg text-xs"
                            style={{ background: "var(--color-background)", border: "1px solid var(--color-border)" }}
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <span>
                                {f.name.endsWith(".pdf") ? "📕" : f.name.endsWith(".docx") || f.name.endsWith(".doc") ? "📘" : "📄"}
                              </span>
                              <span className="truncate">{f.name}</span>
                              <span style={{ color: "var(--color-text-muted)" }}>
                                {(f.size / 1024).toFixed(0)} KB
                              </span>
                            </div>
                            <button
                              onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                              className="ml-2 px-1"
                              style={{ color: "var(--color-text-muted)" }}
                            >
                              x
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* URL MODE */}
              {mode === "url" && (
                <>
                  <label className="block text-sm font-medium mb-2">SNS / Web URL</label>
                  <input
                    type="url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://x.com/username/status/... or blog URL"
                    className="w-full px-3 py-2 rounded-lg text-sm"
                    style={{
                      background: "var(--color-background)",
                      border: "1px solid var(--color-border)",
                      color: "var(--color-text)",
                    }}
                  />
                  <div className="flex flex-wrap gap-2 mt-3">
                    {["X (Twitter)", "note", "Bluesky", "LinkedIn", "Blog"].map((p) => (
                      <span
                        key={p}
                        className="text-xs px-2 py-1 rounded-full"
                        style={{ background: "var(--color-background)", color: "var(--color-text-muted)", border: "1px solid var(--color-border)" }}
                      >
                        {p}
                      </span>
                    ))}
                  </div>
                  <p className="text-xs mt-3" style={{ color: "var(--color-text-muted)" }}>
                    公開ページのテキストをfetchして分析。認証が必要なページは取得不可。
                  </p>
                </>
              )}

              {/* GOOGLE DRIVE MODE */}
              {mode === "gdrive" && (
                <>
                  <label className="block text-sm font-medium mb-2">Google Drive Shared Link</label>
                  <input
                    type="url"
                    value={gdriveUrl}
                    onChange={(e) => setGdriveUrl(e.target.value)}
                    placeholder="https://drive.google.com/file/d/... or docs.google.com/document/d/..."
                    className="w-full px-3 py-2 rounded-lg text-sm"
                    style={{
                      background: "var(--color-background)",
                      border: "1px solid var(--color-border)",
                      color: "var(--color-text)",
                    }}
                  />
                  <div className="flex flex-wrap gap-2 mt-3">
                    {["Google Docs", "PDF on Drive", "Word on Drive"].map((p) => (
                      <span
                        key={p}
                        className="text-xs px-2 py-1 rounded-full"
                        style={{ background: "var(--color-background)", color: "var(--color-text-muted)", border: "1px solid var(--color-border)" }}
                      >
                        {p}
                      </span>
                    ))}
                  </div>
                  <div
                    className="mt-3 px-3 py-2 rounded-lg text-xs"
                    style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}
                  >
                    <p className="font-medium mb-1">How to share / 共有方法:</p>
                    <p>1. Google Driveでファイルを右クリック →「共有」</p>
                    <p>2.「リンクを知っている全員」に変更</p>
                    <p>3. リンクをコピーして上に貼り付け</p>
                  </div>
                </>
              )}
            </div>

            {/* Genre + Context */}
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="block text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>
                  Genre / ジャンル
                </label>
                <select
                  value={genre}
                  onChange={(e) => setGenre(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                >
                  {GENRES.map((g) => (
                    <option key={g.value} value={g.value}>{g.label}</option>
                  ))}
                </select>
              </div>
              <div className="flex-1">
                <label className="block text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>
                  Context / コンテキスト
                </label>
                <input
                  type="text"
                  value={context}
                  onChange={(e) => setContext(e.target.value)}
                  placeholder="e.g., JSLA paper, Twitter thread..."
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                />
              </div>
            </div>

            {/* Analyze Button */}
            <button
              onClick={handleAnalyze}
              disabled={!canAnalyze()}
              className="w-full py-3 rounded-lg text-sm font-medium transition-colors"
              style={{
                background: analyzing ? "var(--color-border)" : "var(--color-accent)",
                color: "white",
                opacity: canAnalyze() ? 1 : 0.5,
                cursor: canAnalyze() ? "pointer" : "not-allowed",
              }}
            >
              {analyzing
                ? mode === "file"
                  ? `Analyzing ${files.length} files... / ${files.length}ファイル分析中...`
                  : mode === "gdrive"
                    ? "Downloading & Analyzing... / ダウンロード・分析中..."
                    : "Analyzing... / 分析中..."
                : mode === "file"
                  ? `Analyze ${files.length} file${files.length !== 1 ? "s" : ""} / 一括分析`
                  : mode === "gdrive"
                    ? "Fetch from Drive & Analyze"
                    : mode === "url"
                      ? "Fetch & Analyze / 取得して分析"
                      : "Analyze / 分析する"}
            </button>

            {/* Error */}
            {error && (
              <div className="text-sm px-3 py-2 rounded-lg" style={{ background: "#ef444420", color: "#ef4444" }}>
                {error}
              </div>
            )}

            {/* Single Analysis Result */}
            {singleResult && (
              <div
                className="rounded-xl p-4"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
              >
                <div className="flex items-center gap-2 mb-3">
                  <h3 className="text-sm font-medium">Analysis Result / 分析結果</h3>
                  {Boolean(singleResult.platform) && (
                    <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "var(--color-accent)", color: "white" }}>
                      {String(singleResult.platform)}
                    </span>
                  )}
                  {singleResult.source === "gdrive" && (
                    <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "#10b981", color: "white" }}>
                      Google Drive
                    </span>
                  )}
                  {Boolean(singleResult.extracted_length) && (
                    <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                      {String(singleResult.extracted_length)} chars
                    </span>
                  )}
                </div>
                {Boolean(singleResult.analysis) && typeof singleResult.analysis === "object" && (
                  <div className="space-y-3">
                    {Object.entries(singleResult.analysis as Record<string, string>).map(([key, value]) => (
                      <div key={key}>
                        <div className="text-xs font-medium mb-1" style={{ color: "var(--color-accent)" }}>
                          {key.replace(/_/g, " ")}
                        </div>
                        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>{value}</p>
                      </div>
                    ))}
                  </div>
                )}
                <p className="text-xs mt-3" style={{ color: "var(--color-text-muted)" }}>
                  Saved to voice_profile.jsonl
                </p>
              </div>
            )}

            {/* Batch Result */}
            {batchResult && (
              <div
                className="rounded-xl p-4"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
              >
                <h3 className="text-sm font-medium mb-3">Batch Result / 一括分析結果</h3>
                <div className="flex gap-4 mb-3">
                  <div className="text-center">
                    <div className="text-lg font-bold" style={{ color: "#10b981" }}>{batchResult.analyzed}</div>
                    <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>analyzed</div>
                  </div>
                  {batchResult.failed > 0 && (
                    <div className="text-center">
                      <div className="text-lg font-bold" style={{ color: "#ef4444" }}>{batchResult.failed}</div>
                      <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>failed</div>
                    </div>
                  )}
                  <div className="text-center">
                    <div className="text-lg font-bold" style={{ color: "var(--color-text-muted)" }}>{batchResult.total}</div>
                    <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>total</div>
                  </div>
                </div>

                {/* Success list */}
                {batchResult.results.length > 0 && (
                  <div className="space-y-1 mb-2">
                    {batchResult.results.map((r) => (
                      <div
                        key={r.id}
                        className="flex items-center gap-2 px-2 py-1.5 rounded text-xs"
                        style={{ background: "var(--color-background)" }}
                      >
                        <span style={{ color: "#10b981" }}>OK</span>
                        <span className="truncate flex-1">{r.file}</span>
                        <span style={{ color: "var(--color-text-muted)" }}>{r.extracted_length} chars</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Error list */}
                {batchResult.errors.length > 0 && (
                  <div className="space-y-1">
                    {batchResult.errors.map((e, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-2 px-2 py-1.5 rounded text-xs"
                        style={{ background: "#ef444410" }}
                      >
                        <span style={{ color: "#ef4444" }}>NG</span>
                        <span className="truncate">{e.file}</span>
                        <span className="text-xs truncate" style={{ color: "#ef4444" }}>{e.error}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ─── Right: Style Guide ─── */}
          <div className="space-y-4">
            <div
              className="rounded-xl p-4"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            >
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium">Style Guide / スタイルガイド</h3>
                <div className="flex gap-2">
                  {styleGuide && (
                    <>
                      <button
                        onClick={handleCopy}
                        className="px-3 py-1 rounded-lg text-xs transition-colors"
                        style={{ background: "var(--color-background)", border: "1px solid var(--color-border)" }}
                      >
                        {copied ? "Copied!" : "Copy"}
                      </button>
                      <button
                        onClick={handleDownload}
                        className="px-3 py-1 rounded-lg text-xs transition-colors"
                        style={{ background: "var(--color-background)", border: "1px solid var(--color-border)" }}
                      >
                        Download
                      </button>
                    </>
                  )}
                  <button
                    onClick={handleRegenerate}
                    disabled={regenerating}
                    className="px-3 py-1 rounded-lg text-xs transition-colors"
                    style={{ background: "var(--color-accent)", color: "white" }}
                  >
                    {regenerating ? "Generating..." : "Regenerate"}
                  </button>
                </div>
              </div>

              {/* Sample Count by Genre */}
              {sampleCount && sampleCount.total > 0 && (
                <div className="flex flex-wrap gap-2 mb-3">
                  {Object.entries(sampleCount.by_genre).map(([g, count]) => (
                    <span
                      key={g}
                      className="text-xs px-2 py-0.5 rounded-full"
                      style={{ background: "var(--color-background)", color: "var(--color-text-muted)", border: "1px solid var(--color-border)" }}
                    >
                      {g}: {count}
                    </span>
                  ))}
                </div>
              )}

              {styleGuide ? (
                <div
                  className="prose prose-invert prose-sm max-w-none overflow-y-auto"
                  style={{
                    maxHeight: "calc(100vh - 320px)",
                    background: "var(--color-background)",
                    padding: "16px",
                    borderRadius: "8px",
                    border: "1px solid var(--color-border)",
                    fontSize: "13px",
                    lineHeight: "1.6",
                    whiteSpace: "pre-wrap",
                    fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                  }}
                >
                  {styleGuide}
                </div>
              ) : (
                <div
                  className="flex items-center justify-center"
                  style={{
                    minHeight: "300px",
                    background: "var(--color-background)",
                    borderRadius: "8px",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text-muted)",
                  }}
                >
                  <div className="text-center px-6">
                    <p className="text-sm mb-2">No style guide yet</p>
                    <p className="text-xs mb-4">
                      Analyze text samples, then click &quot;Regenerate&quot;
                    </p>
                    <p className="text-xs">
                      論文PDF一括アップロード → SNSリンク → Regenerateで
                      <br />
                      あなたの文体を学習したスタイルガイドが生成されます
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
