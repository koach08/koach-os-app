"use client";

import { useState, useCallback } from "react";
import { useSession, signIn } from "next-auth/react";
import { useDropzone } from "react-dropzone";
import { format } from "date-fns";
import { ja } from "date-fns/locale";
import { toast } from "sonner";
import { CATEGORIES } from "@/lib/categories";
import type { ExtractedEvent } from "@/lib/openai";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  FileUp,
  Upload,
  Loader2,
  CalendarPlus,
  Download,
  LogIn,
  Trash2,
} from "lucide-react";

export default function ImportPage() {
  const { data: session } = useSession();
  const [events, setEvents] = useState<(ExtractedEvent & { selected: boolean })[]>([]);
  const [loading, setLoading] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [filename, setFilename] = useState("");

  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0];
    if (!file) return;

    setLoading(true);
    setFilename(file.name);
    setEvents([]);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/documents/parse", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.details || err.error || "Parse failed");
      }

      const data = await res.json();
      setEvents(
        (data.events || []).map((e: ExtractedEvent) => ({
          ...e,
          selected: e.confidence >= 0.5,
        }))
      );

      if (data.events.length === 0) {
        toast.info("日程情報が見つかりませんでした");
      } else {
        toast.success(`${data.events.length}件の日程を抽出しました`);
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unknown error";
      toast.error(`エラー: ${message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "text/plain": [".txt"],
      "text/csv": [".csv"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    },
    maxFiles: 1,
    maxSize: 10 * 1024 * 1024, // 10MB
  });

  const toggleEvent = (idx: number) => {
    setEvents((prev) =>
      prev.map((e, i) => (i === idx ? { ...e, selected: !e.selected } : e))
    );
  };

  const selectedEvents = events.filter((e) => e.selected);

  const handleRegisterToGCal = async () => {
    if (!session?.accessToken || selectedEvents.length === 0) return;
    setRegistering(true);

    try {
      const calEvents = selectedEvents.map((e) => {
        const start = new Date(e.date);
        const end = e.endDate
          ? new Date(e.endDate)
          : new Date(start.getTime() + 60 * 60 * 1000);

        return {
          summary: e.title,
          description: e.description || "",
          start: { dateTime: start.toISOString() },
          end: { dateTime: end.toISOString() },
          colorId:
            CATEGORIES.find((c) => c.id === e.category)
              ? String(CATEGORIES.findIndex((c) => c.id === e.category) + 1)
              : "1",
        };
      });

      const res = await fetch("/api/calendar/training", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: calEvents }),
      });

      if (res.ok) {
        const data = await res.json();
        toast.success(`${data.created}件をGoogle Calendarに登録しました`);
      } else {
        throw new Error("Registration failed");
      }
    } catch {
      toast.error("カレンダー登録に失敗しました");
    } finally {
      setRegistering(false);
    }
  };

  const handleDownloadICS = () => {
    const lines = [
      "BEGIN:VCALENDAR",
      "VERSION:2.0",
      "PRODID:-//Schedule Manager//JP",
    ];
    for (const event of selectedEvents) {
      const start = new Date(event.date);
      const end = event.endDate
        ? new Date(event.endDate)
        : new Date(start.getTime() + 3600000);
      const fmt = (d: Date) =>
        d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
      lines.push("BEGIN:VEVENT");
      lines.push(`DTSTART:${fmt(start)}`);
      lines.push(`DTEND:${fmt(end)}`);
      lines.push(`SUMMARY:${event.title}`);
      if (event.description) lines.push(`DESCRIPTION:${event.description}`);
      lines.push(`UID:${crypto.randomUUID()}@schedule-manager`);
      lines.push("END:VEVENT");
    }
    lines.push("END:VCALENDAR");

    const blob = new Blob([lines.join("\r\n")], { type: "text/calendar" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `events-${format(new Date(), "yyyyMMdd")}.ics`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen px-4 py-6">
      <div className="mx-auto max-w-lg">
        <h1 className="mb-1 text-xl font-black">📄 文書インポート</h1>
        <p className="mb-4 text-xs text-muted-foreground">
          PDF/Excel/Word → AI が日程を抽出 → Google Calendar に登録
        </p>

        {/* Dropzone */}
        <div
          {...getRootProps()}
          className={`mb-4 flex cursor-pointer flex-col items-center gap-3 rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
            isDragActive
              ? "border-[var(--color-cat-research)] bg-[var(--color-cat-research)]/5"
              : "border-border hover:border-muted-foreground"
          }`}
        >
          <input {...getInputProps()} />
          {loading ? (
            <>
              <Loader2 className="h-8 w-8 animate-spin text-[var(--color-cat-research)]" />
              <p className="text-sm font-bold">解析中...</p>
              <p className="text-[10px] text-muted-foreground">{filename}</p>
            </>
          ) : (
            <>
              <Upload className="h-8 w-8 text-muted-foreground" />
              <p className="text-sm font-bold">
                ファイルをドロップまたはクリック
              </p>
              <p className="text-[10px] text-muted-foreground">
                PDF, Excel (.xlsx), Word (.docx), テキスト — 最大10MB
              </p>
            </>
          )}
        </div>

        {/* Results */}
        {events.length > 0 && (
          <>
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-bold">
                抽出結果 ({selectedEvents.length}/{events.length}件選択)
              </h3>
              <button
                onClick={() => setEvents([])}
                className="text-[10px] text-muted-foreground hover:text-foreground"
              >
                <Trash2 className="inline h-3 w-3" /> クリア
              </button>
            </div>

            <div className="mb-4 space-y-2">
              {events.map((event, i) => {
                const cat = CATEGORIES.find((c) => c.id === event.category);
                return (
                  <div
                    key={i}
                    className={`rounded-lg border bg-card px-3 py-2.5 transition-opacity ${
                      event.selected ? "border-border" : "border-border/50 opacity-50"
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <Checkbox
                        checked={event.selected}
                        onCheckedChange={() => toggleEvent(i)}
                        className="mt-0.5"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold">{event.title}</span>
                          {cat && (
                            <span
                              className="rounded px-1.5 py-0.5 text-[9px] font-bold"
                              style={{
                                color: cat.color,
                                background: `${cat.color}15`,
                              }}
                            >
                              {cat.label}
                            </span>
                          )}
                        </div>
                        <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                          {format(new Date(event.date), "yyyy/M/d（E） HH:mm", {
                            locale: ja,
                          })}
                          {event.endDate &&
                            ` ~ ${format(new Date(event.endDate), "HH:mm")}`}
                        </p>
                        {event.description && (
                          <p className="mt-0.5 text-[10px] text-muted-foreground">
                            {event.description}
                          </p>
                        )}
                        <div className="mt-1 flex items-center gap-1">
                          <div
                            className="h-1 rounded-full"
                            style={{
                              width: `${event.confidence * 100}%`,
                              maxWidth: 60,
                              background:
                                event.confidence >= 0.7
                                  ? "var(--color-cat-growth)"
                                  : event.confidence >= 0.4
                                  ? "var(--color-cat-training)"
                                  : "var(--color-cat-deadline)",
                            }}
                          />
                          <span className="text-[8px] text-muted-foreground">
                            確信度 {Math.round(event.confidence * 100)}%
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Actions */}
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                className="flex-1 gap-1.5 text-xs"
                onClick={handleDownloadICS}
                disabled={selectedEvents.length === 0}
              >
                <Download className="h-3.5 w-3.5" />
                ICSダウンロード
              </Button>
              {session?.accessToken ? (
                <Button
                  size="sm"
                  className="flex-1 gap-1.5 bg-[var(--color-cat-research)] text-xs text-white hover:bg-[var(--color-cat-research)]/80"
                  onClick={handleRegisterToGCal}
                  disabled={registering || selectedEvents.length === 0}
                >
                  {registering ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <CalendarPlus className="h-3.5 w-3.5" />
                  )}
                  GCal登録 ({selectedEvents.length})
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="outline"
                  className="flex-1 gap-1.5 text-xs"
                  onClick={() => signIn("google")}
                >
                  <LogIn className="h-3.5 w-3.5" />
                  ログインして登録
                </Button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
