"use client";

import { useState } from "react";
import { useSession, signIn } from "next-auth/react";
import { format } from "date-fns";
import { ja } from "date-fns/locale";
import { toast } from "sonner";
import { CATEGORIES } from "@/lib/categories";
import type { ExtractedEvent } from "@/lib/openai";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  ScanSearch,
  Loader2,
  CalendarPlus,
  LogIn,
  Mail,
  Search,
} from "lucide-react";

const PRESET_QUERIES = [
  { label: "締切", query: "締切 OR deadline OR 〆切 OR 提出" },
  { label: "会議", query: "会議 OR ミーティング OR meeting" },
  { label: "学会", query: "学会 OR conference OR 研究会" },
  { label: "申請", query: "申請 OR 科研費 OR KAKENHI" },
];

interface EmailSummary {
  id: string;
  subject: string;
  from: string;
  date: string;
  snippet: string;
}

export default function ScanPage() {
  const { data: session } = useSession();
  const [query, setQuery] = useState("締切 OR deadline OR 〆切");
  const [scanning, setScanning] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [emails, setEmails] = useState<EmailSummary[]>([]);
  const [events, setEvents] = useState<(ExtractedEvent & { selected: boolean })[]>([]);

  const handleScan = async () => {
    if (!session?.accessToken || !query.trim()) return;
    setScanning(true);
    setEmails([]);
    setEvents([]);

    try {
      const res = await fetch("/api/gmail/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, maxResults: 15 }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.details || err.error);
      }

      const data = await res.json();
      setEmails(data.emails || []);
      setEvents(
        (data.events || []).map((e: ExtractedEvent) => ({
          ...e,
          selected: e.confidence >= 0.5,
        }))
      );

      if (data.events.length === 0) {
        toast.info("締切情報が見つかりませんでした");
      } else {
        toast.success(
          `${data.emailCount}件のメールから${data.events.length}件の締切を検出`
        );
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unknown error";
      toast.error(`エラー: ${message}`);
    } finally {
      setScanning(false);
    }
  };

  const toggleEvent = (idx: number) => {
    setEvents((prev) =>
      prev.map((e, i) => (i === idx ? { ...e, selected: !e.selected } : e))
    );
  };

  const selectedEvents = events.filter((e) => e.selected);

  const handleRegister = async () => {
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
          colorId: "11", // red for deadlines
          reminders: {
            useDefault: false,
            overrides: [
              { method: "popup", minutes: 60 * 24 }, // 1 day before
              { method: "popup", minutes: 60 }, // 1 hour before
            ],
          },
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

  if (!session?.accessToken) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center px-4">
        <ScanSearch className="mb-4 h-12 w-12 text-muted-foreground" />
        <h1 className="text-lg font-bold">メールスキャン</h1>
        <p className="mb-4 mt-2 text-center text-xs text-muted-foreground">
          GmailからAIが締切・重要日程を自動検出
        </p>
        <Button onClick={() => signIn("google")} variant="outline" className="gap-2">
          <LogIn className="h-4 w-4" />
          Googleでログイン
        </Button>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-4 py-6">
      <div className="mx-auto max-w-lg">
        <h1 className="mb-1 text-xl font-black">📧 メールスキャン</h1>
        <p className="mb-4 text-xs text-muted-foreground">
          Gmail から AI が締切・日程を抽出 → Google Calendar に登録
        </p>

        {/* Search bar */}
        <div className="mb-3 flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="検索キーワード..."
            className="flex-1 rounded-md border border-border bg-card px-3 py-2 text-sm"
            onKeyDown={(e) => e.key === "Enter" && handleScan()}
          />
          <Button
            onClick={handleScan}
            disabled={scanning}
            className="gap-1.5 bg-[var(--color-cat-deadline)] text-white hover:bg-[var(--color-cat-deadline)]/80"
          >
            {scanning ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Search className="h-4 w-4" />
            )}
          </Button>
        </div>

        {/* Preset queries */}
        <div className="mb-4 flex flex-wrap gap-1.5">
          {PRESET_QUERIES.map((p) => (
            <button
              key={p.label}
              onClick={() => {
                setQuery(p.query);
              }}
              className={`rounded-md border px-2.5 py-1 text-[10px] font-bold transition-colors ${
                query === p.query
                  ? "border-[var(--color-cat-deadline)] text-[var(--color-cat-deadline)]"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Scanned emails */}
        {emails.length > 0 && (
          <div className="mb-4">
            <h3 className="mb-2 flex items-center gap-1.5 text-xs font-bold text-muted-foreground">
              <Mail className="h-3.5 w-3.5" />
              スキャン済みメール ({emails.length})
            </h3>
            <div className="max-h-40 space-y-1 overflow-y-auto rounded-xl border border-border bg-card p-2">
              {emails.map((email) => (
                <div key={email.id} className="rounded-md px-2 py-1.5">
                  <p className="truncate text-[11px] font-medium">
                    {email.subject}
                  </p>
                  <p className="truncate text-[9px] text-muted-foreground">
                    {email.from} — {email.date}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Extracted events */}
        {events.length > 0 && (
          <>
            <h3 className="mb-2 text-sm font-bold">
              検出された締切 ({selectedEvents.length}/{events.length}件選択)
            </h3>
            <div className="mb-4 space-y-2">
              {events.map((event, i) => {
                const cat = CATEGORIES.find((c) => c.id === event.category);
                return (
                  <div
                    key={i}
                    className={`rounded-lg border bg-card px-3 py-2.5 transition-opacity ${
                      event.selected
                        ? "border-border"
                        : "border-border/50 opacity-50"
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
                          <span className="text-xs font-bold">
                            {event.title}
                          </span>
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
                          {format(
                            new Date(event.date),
                            "yyyy/M/d（E） HH:mm",
                            { locale: ja }
                          )}
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
                                  : "var(--color-cat-training)",
                            }}
                          />
                          <span className="text-[8px] text-muted-foreground">
                            {Math.round(event.confidence * 100)}%
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <Button
              onClick={handleRegister}
              disabled={registering || selectedEvents.length === 0}
              className="w-full gap-1.5 bg-[var(--color-cat-deadline)] text-white hover:bg-[var(--color-cat-deadline)]/80"
            >
              {registering ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <CalendarPlus className="h-4 w-4" />
              )}
              GCalに登録 ({selectedEvents.length}件)
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
