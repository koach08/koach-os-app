"use client";

import { useEffect, useState } from "react";

type EventType = "meeting" | "committee" | "deadline" | "default";

type Proposal = {
  title: string;
  start_iso: string;
  end_iso: string;
  description: string;
  location: string;
  confidence: "high" | "medium" | "low";
  event_type: EventType;
  recurrence?: string;
  source_email_id: string;
  source_subject: string;
};

const EVENT_TYPE_META: Record<EventType, { label: string; emoji: string; reminder: string; color: string }> = {
  meeting: { label: "会議", emoji: "👥", reminder: "30分前 / 1日前", color: "#3b82f6" },
  committee: { label: "委員会", emoji: "🏛", reminder: "1時間前 / 1日前 / 1日前メール", color: "#a855f7" },
  deadline: { label: "締切", emoji: "⏰", reminder: "1日前 / 3日前 / 1週間前メール", color: "#ef4444" },
  default: { label: "予定", emoji: "📅", reminder: "15分前", color: "#71717a" },
};

type ExtractResponse = {
  proposals: Proposal[];
  emails_scanned: number;
  engine_used: string;
  model_used: string;
};

type StatusResponse = {
  configured: boolean;
};

const CONFIDENCE_COLORS: Record<string, { bg: string; text: string }> = {
  high: { bg: "rgba(34, 197, 94, 0.12)", text: "#22c55e" },
  medium: { bg: "rgba(234, 179, 8, 0.12)", text: "#eab308" },
  low: { bg: "rgba(239, 68, 68, 0.12)", text: "#ef4444" },
};

function formatDateTime(iso: string): string {
  if (!iso) return "—";
  if (iso.length <= 10) {
    return new Date(iso).toLocaleDateString("ja-JP", {
      month: "long",
      day: "numeric",
      weekday: "short",
    }) + " (終日)";
  }
  return new Date(iso).toLocaleString("ja-JP", {
    month: "long",
    day: "numeric",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function GmailSyncPage() {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [meta, setMeta] = useState<{ scanned: number; engine: string; model: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Record<number, { ok: boolean; link?: string; err?: string }>>({});
  const [days, setDays] = useState(3);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [mode, setMode] = useState<"gmail" | "pdf" | "excel" | "manual">("gmail");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [pdfMeta, setPdfMeta] = useState<{ filename: string; pageCount: number } | null>(null);
  const [xlsxFile, setXlsxFile] = useState<File | null>(null);
  const [xlsxMeta, setXlsxMeta] = useState<{ filename: string; sheetCount: number } | null>(null);
  const [manual, setManual] = useState({
    title: "",
    date: new Date().toISOString().slice(0, 10),
    startTime: "09:00",
    endTime: "10:00",
    allDay: false,
    location: "",
    description: "",
    event_type: "default" as EventType,
    recurrence: "" as "" | "weekly",
    recurrenceUntil: "",
  });
  const [manualStatus, setManualStatus] = useState<null | { ok: boolean; msg: string; link?: string }>(null);

  // Direct Railway URL (env-driven). Avoids Vercel proxy 30s timeout.
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "";

  useEffect(() => {
    fetch(`${apiBase}/api/gmail/status`)
      .then((r) => r.json() as Promise<StatusResponse>)
      .then((d) => setConfigured(d.configured))
      .catch(() => setConfigured(false));
  }, [apiBase]);

  const handleExtract = async () => {
    setLoading(true);
    setError(null);
    setProposals([]);
    setCreated({});
    setProgress(null);
    try {
      const limit = days <= 7 ? 20 : days <= 30 ? 50 : days <= 90 ? 100 : 200;

      // Short range: one-shot endpoint
      if (days <= 14) {
        const res = await fetch(`${apiBase}/api/gmail/extract-events`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ days, limit, engine: "gemini" }),
        });
        if (!res.ok) throw new Error((await res.text()) || `HTTP ${res.status}`);
        const data = (await res.json()) as ExtractResponse;
        setProposals(data.proposals);
        setMeta({ scanned: data.emails_scanned, engine: data.engine_used, model: data.model_used });
        return;
      }

      // Long range: fetch each account slot separately in parallel to avoid Railway proxy timeout
      const slotsRes = await fetch(`${apiBase}/api/gmail/slots`);
      const { slots } = (await slotsRes.json()) as { slots: number[] };
      const perSlotLimit = Math.ceil(limit / Math.max(slots.length, 1));
      const slotResults = await Promise.all(
        slots.map(async (s) => {
          const r = await fetch(
            `${apiBase}/api/gmail/recent?days=${days}&limit=${perSlotLimit}&slot=${s}`
          );
          if (!r.ok) return [];
          const d = (await r.json()) as { emails: any[] };
          return d.emails || [];
        })
      );
      const emails = slotResults.flat();
      if (!emails || emails.length === 0) {
        setMeta({ scanned: 0, engine: "gemini", model: "—" });
        return;
      }

      const CHUNK = 15;
      const chunks: any[][] = [];
      for (let i = 0; i < emails.length; i += CHUNK) chunks.push(emails.slice(i, i + CHUNK));
      setProgress({ done: 0, total: chunks.length });

      const all: Proposal[] = [];
      let doneCount = 0;
      let lastEngine = "gemini";
      let lastModel = "—";
      // Run chunks with limited concurrency (3 parallel) to avoid hammering Gemini quotas
      const CONCURRENCY = 3;
      const queue = [...chunks];
      const runners = Array.from({ length: Math.min(CONCURRENCY, chunks.length) }, async () => {
        while (queue.length > 0) {
          const batch = queue.shift();
          if (!batch) break;
          try {
            const r = await fetch(`${apiBase}/api/gmail/extract-events-from-emails`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ emails: batch, engine: "gemini" }),
            });
            if (r.ok) {
              const d = (await r.json()) as ExtractResponse;
              all.push(...d.proposals);
              lastEngine = d.engine_used;
              lastModel = d.model_used;
            }
          } catch {
            // skip failed batch; surface aggregate later
          } finally {
            doneCount += 1;
            setProgress({ done: doneCount, total: chunks.length });
          }
        }
      });
      await Promise.all(runners);

      // Dedupe by (title, start_iso)
      const seen = new Set<string>();
      const deduped = all.filter((p) => {
        const k = `${p.title}|${p.start_iso}`;
        if (seen.has(k)) return false;
        seen.add(k);
        return true;
      });

      setProposals(deduped);
      setMeta({ scanned: emails.length, engine: lastEngine, model: lastModel });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
      setProgress(null);
    }
  };

  const handleExtractExcel = async () => {
    if (!xlsxFile) {
      setError("Excel ファイルを選んでください");
      return;
    }
    setLoading(true);
    setError(null);
    setProposals([]);
    setCreated({});
    setXlsxMeta(null);
    try {
      const fd = new FormData();
      fd.append("file", xlsxFile);
      const res = await fetch(`${apiBase}/api/calendar/extract-events-from-excel?engine=gemini`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) throw new Error((await res.text()) || `HTTP ${res.status}`);
      const data = await res.json();
      setProposals(data.proposals || []);
      setXlsxMeta({ filename: data.filename, sheetCount: data.sheet_count });
      setMeta({ scanned: data.sheet_count || 0, engine: data.engine_used || "gemini", model: data.model_used || "—" });
      if (data.parse_error && (data.proposals || []).length === 0) setError(data.parse_error);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleManualSubmit = async () => {
    setManualStatus(null);
    if (!manual.title.trim()) {
      setManualStatus({ ok: false, msg: "タイトルを入力してください" });
      return;
    }
    setLoading(true);
    try {
      const start_iso = manual.allDay
        ? manual.date
        : `${manual.date}T${manual.startTime}:00+09:00`;
      const end_iso = manual.allDay
        ? manual.date
        : `${manual.date}T${manual.endTime}:00+09:00`;
      let recurrence = "";
      if (manual.recurrence === "weekly") {
        if (manual.recurrenceUntil) {
          const untilDate = manual.recurrenceUntil.replace(/-/g, "");
          recurrence = `FREQ=WEEKLY;UNTIL=${untilDate}T235959Z`;
        } else {
          recurrence = "FREQ=WEEKLY";
        }
      }
      const res = await fetch(`${apiBase}/api/calendar/create-event`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: manual.title,
          start_iso,
          end_iso,
          description: manual.description,
          location: manual.location,
          event_type: manual.event_type,
          recurrence,
        }),
      });
      if (!res.ok) throw new Error((await res.text()) || `HTTP ${res.status}`);
      const data = await res.json();
      setManualStatus({ ok: true, msg: "Calendar に追加しました", link: data.html_link });
      setManual((m) => ({ ...m, title: "", description: "", location: "" }));
    } catch (e) {
      setManualStatus({ ok: false, msg: e instanceof Error ? e.message : String(e) });
    } finally {
      setLoading(false);
    }
  };

  const handleExtractPdf = async () => {
    if (!pdfFile) {
      setError("PDF ファイルを選んでください");
      return;
    }
    setLoading(true);
    setError(null);
    setProposals([]);
    setCreated({});
    setPdfMeta(null);
    try {
      const fd = new FormData();
      fd.append("file", pdfFile);
      const res = await fetch(`${apiBase}/api/calendar/extract-events-from-pdf?engine=gemini`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) throw new Error((await res.text()) || `HTTP ${res.status}`);
      const data = await res.json();
      setProposals(data.proposals || []);
      setPdfMeta({ filename: data.filename, pageCount: data.page_count });
      setMeta({ scanned: data.page_count || 0, engine: data.engine_used || "gemini", model: data.model_used || "—" });
      if (data.parse_error && (data.proposals || []).length === 0) {
        setError(data.parse_error);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleAddToCalendar = async (idx: number, p: Proposal) => {
    try {
      const res = await fetch(`${apiBase}/api/calendar/create-event`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: p.title,
          start_iso: p.start_iso,
          end_iso: p.end_iso,
          description: p.description,
          location: p.location,
          event_type: p.event_type,
          recurrence: p.recurrence || "",
        }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setCreated((prev) => ({ ...prev, [idx]: { ok: true, link: data.html_link } }));
    } catch (e) {
      setCreated((prev) => ({
        ...prev,
        [idx]: { ok: false, err: e instanceof Error ? e.message : String(e) },
      }));
    }
  };

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Hero */}
      <div
        className="px-8 pt-12 pb-10 relative overflow-hidden"
        style={{
          background:
            "radial-gradient(ellipse at top left, rgba(168, 85, 247, 0.15), transparent 60%), radial-gradient(ellipse at top right, rgba(59, 130, 246, 0.10), transparent 50%)",
        }}
      >
        <div className="max-w-5xl mx-auto">
          <p
            className="text-xs uppercase tracking-widest mb-2"
            style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}
          >
            INBOX → CALENDAR
          </p>
          <h1
            className="text-4xl font-bold tracking-tight"
            style={{
              background: "linear-gradient(135deg, #fafafa 0%, #c084fc 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            メールから予定を吸い出す
          </h1>
          <p className="mt-3 text-sm max-w-xl" style={{ color: "var(--color-text-muted)" }}>
            Gemini が直近の Gmail を読んで、Calendar に追加すべき予定を提案します。承認したものだけ Calendar に書き込まれます。
          </p>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-5xl mx-auto space-y-6">
          {configured === false && (
            <div
              className="rounded-2xl p-6"
              style={{
                background: "rgba(234, 179, 8, 0.08)",
                border: "1px solid #eab308",
              }}
            >
              <h2 className="font-semibold mb-2 flex items-center gap-2">
                <span>⚠️</span>
                <span>Google 連携が未設定です</span>
              </h2>
              <p className="text-sm mb-3" style={{ color: "var(--color-text-muted)" }}>
                ローカルで <code className="px-1.5 py-0.5 rounded" style={{ background: "var(--color-surface)" }}>python scripts/setup_gcal.py</code> を実行してください。
                生成された <code className="px-1.5 py-0.5 rounded" style={{ background: "var(--color-surface)" }}>token.json</code> の内容を Railway env var <code className="px-1.5 py-0.5 rounded" style={{ background: "var(--color-surface)" }}>GOOGLE_TOKEN_JSON</code> に設定。
              </p>
            </div>
          )}

          {configured && (
            <>
              {/* Controls */}
              <div
                className="rounded-2xl p-6"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
              >
                {/* Mode tabs */}
                <div className="flex gap-2 mb-5 flex-wrap">
                  {([
                    ["gmail", "📧 Gmail"],
                    ["pdf", "📄 PDF"],
                    ["excel", "📊 Excel (時間割)"],
                    ["manual", "✍ 手動入力"],
                  ] as const).map(([m, label]) => (
                    <button
                      key={m}
                      onClick={() => {
                        setMode(m);
                        setProposals([]);
                        setError(null);
                        setMeta(null);
                        setPdfMeta(null);
                        setXlsxMeta(null);
                        setManualStatus(null);
                      }}
                      disabled={loading}
                      className="px-4 py-1.5 rounded-full text-sm font-medium transition-all"
                      style={{
                        background: mode === m ? "var(--color-accent)" : "transparent",
                        color: mode === m ? "white" : "var(--color-text-muted)",
                        border: `1px solid ${mode === m ? "var(--color-accent)" : "var(--color-border)"}`,
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                {mode === "pdf" && (
                  <div className="flex items-center gap-3 flex-wrap">
                    <input
                      type="file"
                      accept="application/pdf"
                      onChange={(e) => setPdfFile(e.target.files?.[0] ?? null)}
                      disabled={loading}
                      className="text-sm"
                      style={{ color: "var(--color-text-muted)" }}
                    />
                    <button
                      onClick={handleExtractPdf}
                      disabled={loading || !pdfFile}
                      className="ml-auto px-5 py-2 rounded-full text-sm font-medium transition-all disabled:opacity-50 hover:scale-[1.02]"
                      style={{
                        background: "var(--color-accent)",
                        color: "white",
                        boxShadow: "0 4px 14px rgba(59, 130, 246, 0.35)",
                      }}
                    >
                      {loading ? "解析中..." : "PDF を解析"}
                    </button>
                    {pdfMeta && (
                      <div className="w-full mt-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
                        {pdfMeta.filename} ({pdfMeta.pageCount} ページ)
                      </div>
                    )}
                  </div>
                )}

                {mode === "excel" && (
                  <div className="flex items-center gap-3 flex-wrap">
                    <input
                      type="file"
                      accept=".xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                      onChange={(e) => setXlsxFile(e.target.files?.[0] ?? null)}
                      disabled={loading}
                      className="text-sm"
                      style={{ color: "var(--color-text-muted)" }}
                    />
                    <button
                      onClick={handleExtractExcel}
                      disabled={loading || !xlsxFile}
                      className="ml-auto px-5 py-2 rounded-full text-sm font-medium transition-all disabled:opacity-50 hover:scale-[1.02]"
                      style={{
                        background: "var(--color-accent)",
                        color: "white",
                        boxShadow: "0 4px 14px rgba(59, 130, 246, 0.35)",
                      }}
                    >
                      {loading ? "解析中..." : "Excel を解析"}
                    </button>
                    {xlsxMeta && (
                      <div className="w-full mt-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
                        {xlsxMeta.filename} ({xlsxMeta.sheetCount} シート)
                      </div>
                    )}
                    <div className="w-full text-xs" style={{ color: "var(--color-text-muted)" }}>
                      時間割は週次繰り返し（学期末まで）として登録されます
                    </div>
                  </div>
                )}

                {mode === "manual" && (
                  <div className="space-y-3">
                    <input
                      type="text"
                      placeholder="タイトル（例: ゼミ、健診、書類提出）"
                      value={manual.title}
                      onChange={(e) => setManual({ ...manual, title: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg text-sm"
                      style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                    />
                    <div className="flex gap-2 flex-wrap items-center">
                      <input
                        type="date"
                        value={manual.date}
                        onChange={(e) => setManual({ ...manual, date: e.target.value })}
                        className="px-3 py-2 rounded-lg text-sm"
                        style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                      />
                      <label className="flex items-center gap-1.5 text-sm" style={{ color: "var(--color-text-muted)" }}>
                        <input
                          type="checkbox"
                          checked={manual.allDay}
                          onChange={(e) => setManual({ ...manual, allDay: e.target.checked })}
                        />
                        終日
                      </label>
                      {!manual.allDay && (
                        <>
                          <input
                            type="time"
                            value={manual.startTime}
                            onChange={(e) => setManual({ ...manual, startTime: e.target.value })}
                            className="px-3 py-2 rounded-lg text-sm"
                            style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                          />
                          <span className="text-sm" style={{ color: "var(--color-text-muted)" }}>〜</span>
                          <input
                            type="time"
                            value={manual.endTime}
                            onChange={(e) => setManual({ ...manual, endTime: e.target.value })}
                            className="px-3 py-2 rounded-lg text-sm"
                            style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                          />
                        </>
                      )}
                    </div>
                    <div className="flex gap-2 flex-wrap items-center">
                      <select
                        value={manual.event_type}
                        onChange={(e) => setManual({ ...manual, event_type: e.target.value as EventType })}
                        className="px-3 py-2 rounded-lg text-sm"
                        style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                      >
                        <option value="default">📅 予定（15分前）</option>
                        <option value="meeting">👥 会議（30分前 / 1日前）</option>
                        <option value="committee">🏛 委員会（1時間前 / 1日前メール）</option>
                        <option value="deadline">⏰ 締切（1日前 / 3日前 / 1週間前メール）</option>
                      </select>
                      <select
                        value={manual.recurrence}
                        onChange={(e) => setManual({ ...manual, recurrence: e.target.value as "" | "weekly" })}
                        className="px-3 py-2 rounded-lg text-sm"
                        style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                      >
                        <option value="">繰り返しなし</option>
                        <option value="weekly">毎週</option>
                      </select>
                      {manual.recurrence === "weekly" && (
                        <input
                          type="date"
                          value={manual.recurrenceUntil}
                          onChange={(e) => setManual({ ...manual, recurrenceUntil: e.target.value })}
                          placeholder="終了日（省略可）"
                          className="px-3 py-2 rounded-lg text-sm"
                          style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                        />
                      )}
                    </div>
                    <input
                      type="text"
                      placeholder="場所（任意）"
                      value={manual.location}
                      onChange={(e) => setManual({ ...manual, location: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg text-sm"
                      style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                    />
                    <textarea
                      placeholder="メモ（任意）"
                      value={manual.description}
                      onChange={(e) => setManual({ ...manual, description: e.target.value })}
                      rows={2}
                      className="w-full px-3 py-2 rounded-lg text-sm resize-none"
                      style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                    />
                    <div className="flex items-center gap-3">
                      <button
                        onClick={handleManualSubmit}
                        disabled={loading || !manual.title.trim()}
                        className="px-5 py-2 rounded-full text-sm font-medium transition-all disabled:opacity-50 hover:scale-[1.02]"
                        style={{
                          background: "var(--color-accent)",
                          color: "white",
                          boxShadow: "0 4px 14px rgba(59, 130, 246, 0.35)",
                        }}
                      >
                        {loading ? "追加中..." : "Calendar に追加"}
                      </button>
                      {manualStatus && (
                        <span
                          className="text-sm"
                          style={{ color: manualStatus.ok ? "var(--color-green)" : "var(--color-red)" }}
                        >
                          {manualStatus.ok ? "✓ " : "✗ "}{manualStatus.msg}
                          {manualStatus.link && (
                            <a href={manualStatus.link} target="_blank" rel="noreferrer" className="ml-2 underline">
                              Calendarで見る
                            </a>
                          )}
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {mode === "gmail" && (
                <div className="flex items-center gap-3 flex-wrap">
                  <label className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                    過去
                  </label>
                  <select
                    value={days}
                    onChange={(e) => setDays(Number(e.target.value))}
                    disabled={loading}
                    className="px-3 py-1.5 rounded-lg text-sm"
                    style={{
                      background: "var(--color-background)",
                      border: "1px solid var(--color-border)",
                      color: "var(--color-text)",
                    }}
                  >
                    <option value={1}>1日</option>
                    <option value={3}>3日</option>
                    <option value={7}>7日</option>
                    <option value={14}>14日</option>
                    <option value={30}>30日 (1ヶ月)</option>
                    <option value={60}>60日 (2ヶ月)</option>
                    <option value={90}>90日 (3ヶ月)</option>
                    <option value={180}>180日 (半年)</option>
                    <option value={365}>365日 (1年)</option>
                  </select>
                  <span className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                    のメールを解析
                  </span>
                  <button
                    onClick={handleExtract}
                    disabled={loading}
                    className="ml-auto px-5 py-2 rounded-full text-sm font-medium transition-all disabled:opacity-50 hover:scale-[1.02]"
                    style={{
                      background: "var(--color-accent)",
                      color: "white",
                      boxShadow: "0 4px 14px rgba(59, 130, 246, 0.35)",
                    }}
                  >
                    {loading
                      ? progress
                        ? `解析中... ${progress.done}/${progress.total} batch`
                        : "解析中..."
                      : "予定を抽出"}
                  </button>
                </div>
                )}
                {meta && !loading && (
                  <div className="mt-3 text-xs" style={{ color: "var(--color-text-muted)" }}>
                    {mode === "pdf"
                      ? `PDF: ${meta.scanned} ページ / ${meta.engine} (${meta.model})`
                      : `${meta.scanned} 件のメール解析 / ${meta.engine} (${meta.model})`}
                  </div>
                )}
              </div>

              {error && (
                <div
                  className="rounded-2xl p-4 text-sm"
                  style={{
                    background: "rgba(239, 68, 68, 0.08)",
                    border: "1px solid var(--color-red)",
                    color: "var(--color-red)",
                  }}
                >
                  {error}
                </div>
              )}

              {/* Proposals */}
              {proposals.length === 0 && meta && !loading && (
                <div
                  className="rounded-2xl p-10 text-center"
                  style={{ background: "var(--color-surface)", border: "1px dashed var(--color-border-light)" }}
                >
                  <p className="text-3xl mb-2">📭</p>
                  <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                    解析の結果、Calendar に追加すべき予定は見つかりませんでした
                  </p>
                </div>
              )}

              {proposals.length > 0 && (
                <div className="space-y-3">
                  <h2 className="text-sm font-semibold" style={{ color: "var(--color-text-muted)" }}>
                    {proposals.length} 件の予定候補
                  </h2>
                  {proposals.map((p, i) => {
                    const status = created[i];
                    const conf = CONFIDENCE_COLORS[p.confidence] ?? CONFIDENCE_COLORS.medium;
                    return (
                      <div
                        key={i}
                        className="rounded-2xl p-5 transition-all"
                        style={{
                          background: "var(--color-surface)",
                          border: status?.ok
                            ? "1px solid var(--color-green)"
                            : "1px solid var(--color-border)",
                          opacity: status?.ok ? 0.75 : 1,
                        }}
                      >
                        <div className="flex items-start justify-between gap-4 mb-3">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                              <span
                                className="text-[10px] font-medium px-2 py-0.5 rounded-full inline-flex items-center gap-1"
                                style={{
                                  background: `${EVENT_TYPE_META[p.event_type ?? "default"]?.color ?? "#71717a"}20`,
                                  color: EVENT_TYPE_META[p.event_type ?? "default"]?.color ?? "#71717a",
                                }}
                              >
                                <span>{EVENT_TYPE_META[p.event_type ?? "default"]?.emoji}</span>
                                <span>{EVENT_TYPE_META[p.event_type ?? "default"]?.label}</span>
                              </span>
                              <span
                                className="text-[10px] font-mono px-2 py-0.5 rounded-full uppercase"
                                style={{ background: conf.bg, color: conf.text }}
                              >
                                {p.confidence}
                              </span>
                              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                                {formatDateTime(p.start_iso)}
                              </span>
                              {p.recurrence && (
                                <span
                                  className="text-[10px] font-medium px-2 py-0.5 rounded-full"
                                  style={{ background: "rgba(168, 85, 247, 0.12)", color: "#a855f7" }}
                                >
                                  🔁 繰り返し
                                </span>
                              )}
                            </div>
                            <h3 className="font-semibold text-base">{p.title}</h3>
                            {p.location && (
                              <div className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                                📍 {p.location}
                              </div>
                            )}
                            {p.description && (
                              <p className="text-sm mt-2" style={{ color: "var(--color-text-muted)" }}>
                                {p.description}
                              </p>
                            )}
                            <div className="flex items-center gap-3 text-[11px] mt-2" style={{ color: "var(--color-text-muted)" }}>
                              <span className="italic">出典: {p.source_subject || "(unknown)"}</span>
                              <span>•</span>
                              <span>🔔 {EVENT_TYPE_META[p.event_type ?? "default"]?.reminder}</span>
                            </div>
                          </div>
                          <div className="shrink-0">
                            {status?.ok ? (
                              <a
                                href={status.link}
                                target="_blank"
                                rel="noopener"
                                className="text-xs px-3 py-1.5 rounded-full inline-block"
                                style={{
                                  background: "var(--color-green)",
                                  color: "white",
                                }}
                              >
                                ✓ 追加済み
                              </a>
                            ) : (
                              <button
                                onClick={() => handleAddToCalendar(i, p)}
                                className="text-xs px-3 py-1.5 rounded-full transition-all hover:scale-[1.05]"
                                style={{
                                  background: "var(--color-accent)",
                                  color: "white",
                                }}
                              >
                                Calendar に追加
                              </button>
                            )}
                          </div>
                        </div>
                        {status?.err && (
                          <div className="text-xs mt-2" style={{ color: "var(--color-red)" }}>
                            失敗: {status.err}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
