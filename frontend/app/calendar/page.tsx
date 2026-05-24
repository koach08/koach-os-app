"use client";

import { useEffect, useMemo, useState } from "react";

type Event = {
  id: string;
  title: string;
  start_iso: string;
  end_iso: string;
  all_day: boolean;
  location: string;
  description: string;
  html_link: string;
  event_type: "meeting" | "committee" | "deadline" | "default";
  calendar_id?: string;
  slot?: number;
};

const TYPE_COLOR: Record<string, string> = {
  meeting: "#3b82f6",
  committee: "#a855f7",
  deadline: "#ef4444",
  default: "#71717a",
};

function toYMD(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function formatTime(iso: string): string {
  if (!iso) return "";
  if (iso.length <= 10) return "終日";
  return new Date(iso).toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" });
}

function eventDateKey(ev: Event): string {
  if (!ev.start_iso) return "";
  return ev.start_iso.slice(0, 10);
}

export default function CalendarPage() {
  const [view, setView] = useState<"month" | "agenda">("month");
  const [cursor, setCursor] = useState(new Date());
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Event | null>(null);
  const [editing, setEditing] = useState<Event | null>(null);
  const [savingEdit, setSavingEdit] = useState(false);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [account, setAccount] = useState<{ calendar_id: string; summary: string; timezone: string } | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "";

  // Range for month view: first of current month back to start-of-week through end-of-month + remaining cells
  const { rangeStart, rangeEnd, gridDays } = useMemo(() => {
    const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const last = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0);
    // Start grid at the Sunday before/on the 1st
    const gridStart = new Date(first);
    gridStart.setDate(first.getDate() - first.getDay());
    // 6 weeks = 42 cells
    const gridEnd = new Date(gridStart);
    gridEnd.setDate(gridStart.getDate() + 42);
    const days: Date[] = [];
    for (let i = 0; i < 42; i++) {
      const d = new Date(gridStart);
      d.setDate(gridStart.getDate() + i);
      days.push(d);
    }
    return { rangeStart: toYMD(gridStart), rangeEnd: toYMD(gridEnd), gridDays: days, _firstOfMonth: first, _lastOfMonth: last };
  }, [cursor]);

  useEffect(() => {
    fetch(`${apiBase}/api/calendar/account`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setAccount(d))
      .catch(() => {});
  }, [apiBase]);

  useEffect(() => {
    let abort = false;
    setLoading(true);
    setError(null);
    fetch(`${apiBase}/api/calendar/range?start=${rangeStart}&end=${rangeEnd}`)
      .then(async (r) => {
        if (!r.ok) {
          let body: { detail?: string } | null = null;
          try {
            body = await r.json();
          } catch {}
          const detail = body?.detail ?? `HTTP ${r.status}`;
          throw new Error(detail);
        }
        return r.json();
      })
      .then((d) => {
        if (!abort) setEvents(d.events ?? []);
      })
      .catch((e) => {
        if (!abort) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!abort) setLoading(false);
      });
    return () => {
      abort = true;
    };
  }, [apiBase, rangeStart, rangeEnd]);

  const tokenExpired = error?.includes("GOOGLE_TOKEN_EXPIRED");

  const eventsByDay = useMemo(() => {
    const m: Record<string, Event[]> = {};
    for (const ev of events) {
      const key = eventDateKey(ev);
      if (!key) continue;
      if (!m[key]) m[key] = [];
      m[key].push(ev);
    }
    return m;
  }, [events]);

  const monthLabel = cursor.toLocaleDateString("ja-JP", { year: "numeric", month: "long" });
  const today = toYMD(new Date());

  const handleDelete = async (ev: Event) => {
    if (!confirm(`「${ev.title}」を Google Calendar から削除しますか？`)) return;
    const params = new URLSearchParams();
    if (ev.calendar_id) params.set("calendar_id", ev.calendar_id);
    if (ev.slot) params.set("slot", String(ev.slot));
    const url = `${apiBase}/api/calendar/event/${ev.id}` + (params.toString() ? `?${params}` : "");
    try {
      const r = await fetch(url, { method: "DELETE" });
      if (!r.ok) throw new Error(await r.text());
      setEvents((prev) => prev.filter((e) => e.id !== ev.id));
      setSelected(null);
    } catch (e) {
      alert(`削除失敗: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const handleSaveEdit = async (orig: Event, patch: Partial<Event>) => {
    setSavingEdit(true);
    try {
      const body: Record<string, unknown> = {
        calendar_id: orig.calendar_id ?? "primary",
        slot: orig.slot ?? 1,
      };
      if (patch.title !== undefined) body.title = patch.title;
      if (patch.location !== undefined) body.location = patch.location;
      if (patch.description !== undefined) body.description = patch.description;
      if (patch.start_iso !== undefined) body.start_iso = patch.start_iso;
      if (patch.end_iso !== undefined) body.end_iso = patch.end_iso;
      if (patch.all_day !== undefined) body.all_day = patch.all_day;
      const r = await fetch(`${apiBase}/api/calendar/event/${orig.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const t = await r.text();
        throw new Error(t);
      }
      // 楽観的更新
      setEvents((prev) =>
        prev.map((e) => (e.id === orig.id ? { ...e, ...patch } as Event : e))
      );
      setSelected((s) => (s && s.id === orig.id ? ({ ...s, ...patch } as Event) : s));
      setEditing(null);
    } catch (e) {
      alert(`保存失敗: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSavingEdit(false);
    }
  };

  const dayKey = selectedDay;
  const dayEvents = dayKey ? eventsByDay[dayKey] ?? [] : [];

  // Agenda: group events by date (only future-ish window — use current range)
  const agendaGroups = useMemo(() => {
    const groups: { date: string; items: Event[] }[] = [];
    const keys = Object.keys(eventsByDay).sort();
    for (const k of keys) groups.push({ date: k, items: eventsByDay[k] });
    return groups;
  }, [eventsByDay]);

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Hero */}
      <div
        className="px-8 pt-12 pb-8"
        style={{
          background:
            "radial-gradient(ellipse at top left, rgba(168, 85, 247, 0.15), transparent 60%), radial-gradient(ellipse at top right, rgba(59, 130, 246, 0.10), transparent 50%)",
        }}
      >
        <div className="max-w-6xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            GOOGLE CALENDAR {account && (<span className="lowercase normal-case tracking-normal opacity-80">· {account.calendar_id || account.summary}</span>)}
          </p>
          <div className="flex items-end justify-between flex-wrap gap-3">
            <h1
              className="text-4xl font-bold tracking-tight"
              style={{
                background: "linear-gradient(135deg, #fafafa 0%, #c084fc 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              {monthLabel}
            </h1>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}
                className="px-3 py-1.5 rounded-lg text-sm"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
              >
                ← 前月
              </button>
              <button
                onClick={() => setCursor(new Date())}
                className="px-3 py-1.5 rounded-lg text-sm"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
              >
                今月
              </button>
              <button
                onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}
                className="px-3 py-1.5 rounded-lg text-sm"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
              >
                次月 →
              </button>
              <div className="ml-3 flex gap-1">
                {(["month", "agenda"] as const).map((v) => (
                  <button
                    key={v}
                    onClick={() => setView(v)}
                    className="px-3 py-1.5 rounded-lg text-sm"
                    style={{
                      background: view === v ? "var(--color-accent)" : "var(--color-surface)",
                      color: view === v ? "white" : "var(--color-text)",
                      border: `1px solid ${view === v ? "var(--color-accent)" : "var(--color-border)"}`,
                    }}
                  >
                    {v === "month" ? "🗓 月" : "📋 一覧"}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-6xl mx-auto">
          {error && tokenExpired && (
            <div
              className="rounded-2xl p-4 mb-4"
              style={{ background: "rgba(245, 158, 11, 0.08)", border: "1px solid rgba(245, 158, 11, 0.4)" }}
            >
              <div className="font-semibold mb-1" style={{ color: "#f59e0b" }}>
                Google OAuth トークンが失効しました
              </div>
              <div className="text-sm mb-2" style={{ color: "var(--color-text)" }}>
                Test users mode は 7 日でトークンが切れます。ローカルで再認証してください:
              </div>
              <pre className="text-xs p-2 rounded mb-2" style={{ background: "var(--color-background)", color: "var(--color-text-muted)" }}>
{`python3 scripts/setup_gcal.py
base64 -i token.json | pbcopy
# Railway env の GOOGLE_TOKEN_JSON_B64 に貼り直し`}
              </pre>
            </div>
          )}
          {error && !tokenExpired && (
            <div
              className="rounded-2xl p-4 text-sm mb-4"
              style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid var(--color-red)", color: "var(--color-red)" }}
            >
              {error}
            </div>
          )}
          {loading && (
            <div className="text-sm mb-3" style={{ color: "var(--color-text-muted)" }}>
              読み込み中…
            </div>
          )}

          {view === "month" && (
            <div className="rounded-2xl overflow-hidden" style={{ border: "1px solid var(--color-border)" }}>
              {/* Weekday header */}
              <div className="grid grid-cols-7" style={{ background: "var(--color-surface)" }}>
                {["日", "月", "火", "水", "木", "金", "土"].map((w, i) => (
                  <div
                    key={w}
                    className="text-center text-xs py-2"
                    style={{
                      color: i === 0 ? "#ef4444" : i === 6 ? "#3b82f6" : "var(--color-text-muted)",
                      borderRight: i < 6 ? "1px solid var(--color-border)" : "none",
                    }}
                  >
                    {w}
                  </div>
                ))}
              </div>
              {/* Day grid */}
              <div className="grid grid-cols-7" style={{ background: "var(--color-background)" }}>
                {gridDays.map((d, idx) => {
                  const key = toYMD(d);
                  const inMonth = d.getMonth() === cursor.getMonth();
                  const isToday = key === today;
                  const dayEvents = eventsByDay[key] ?? [];
                  return (
                    <div
                      key={key}
                      onClick={() => setSelectedDay(key)}
                      className="min-h-[88px] p-1.5 cursor-pointer transition-colors"
                      style={{
                        background: selectedDay === key ? "var(--color-surface-hover)" : "transparent",
                        borderRight: idx % 7 !== 6 ? "1px solid var(--color-border)" : "none",
                        borderTop: "1px solid var(--color-border)",
                        opacity: inMonth ? 1 : 0.35,
                      }}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span
                          className="text-xs font-mono"
                          style={{
                            color: isToday
                              ? "white"
                              : d.getDay() === 0
                              ? "#ef4444"
                              : d.getDay() === 6
                              ? "#3b82f6"
                              : "var(--color-text)",
                            background: isToday ? "var(--color-accent)" : "transparent",
                            padding: isToday ? "0 6px" : "0",
                            borderRadius: "9999px",
                          }}
                        >
                          {d.getDate()}
                        </span>
                      </div>
                      <div className="space-y-0.5">
                        {dayEvents.slice(0, 3).map((ev) => (
                          <div
                            key={ev.id}
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelected(ev);
                            }}
                            className="text-[10px] px-1.5 py-0.5 rounded truncate cursor-pointer hover:opacity-80"
                            style={{
                              background: `${TYPE_COLOR[ev.event_type]}25`,
                              color: TYPE_COLOR[ev.event_type],
                              borderLeft: `2px solid ${TYPE_COLOR[ev.event_type]}`,
                            }}
                            title={ev.title}
                          >
                            {!ev.all_day && (
                              <span className="opacity-70 mr-1 font-mono">{formatTime(ev.start_iso)}</span>
                            )}
                            {ev.title}
                          </div>
                        ))}
                        {dayEvents.length > 3 && (
                          <div className="text-[10px]" style={{ color: "var(--color-text-muted)" }}>
                            +{dayEvents.length - 3}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {view === "agenda" && (
            <div className="space-y-4">
              {agendaGroups.length === 0 && !loading && (
                <div
                  className="rounded-2xl p-8 text-center"
                  style={{ background: "var(--color-surface)", border: "1px dashed var(--color-border)" }}
                >
                  <p className="text-3xl mb-2">📭</p>
                  <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                    この期間に予定はありません
                  </p>
                </div>
              )}
              {agendaGroups.map((g) => {
                const d = new Date(g.date);
                const label = d.toLocaleDateString("ja-JP", { month: "long", day: "numeric", weekday: "short" });
                return (
                  <div key={g.date}>
                    <div className="text-sm font-semibold mb-2" style={{ color: "var(--color-text-muted)" }}>
                      {label} {g.date === today && <span style={{ color: "var(--color-accent)" }}>· 今日</span>}
                    </div>
                    <div className="space-y-2">
                      {g.items.map((ev) => (
                        <div
                          key={ev.id}
                          onClick={() => setSelected(ev)}
                          className="rounded-xl p-3 cursor-pointer transition-all hover:scale-[1.005]"
                          style={{
                            background: "var(--color-surface)",
                            border: "1px solid var(--color-border)",
                            borderLeft: `4px solid ${TYPE_COLOR[ev.event_type]}`,
                          }}
                        >
                          <div className="flex items-center gap-3">
                            <span className="text-xs font-mono shrink-0" style={{ color: "var(--color-text-muted)", minWidth: "3rem" }}>
                              {formatTime(ev.start_iso)}
                            </span>
                            <span className="flex-1 text-sm">{ev.title}</span>
                            {ev.location && (
                              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                                📍 {ev.location}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Day events panel (month mode) */}
          {view === "month" && selectedDay && (eventsByDay[selectedDay] ?? []).length > 0 && (
            <div
              className="mt-4 rounded-2xl p-4"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            >
              <div className="text-sm font-semibold mb-2">{selectedDay} の予定</div>
              <div className="space-y-2">
                {(eventsByDay[selectedDay] ?? []).map((ev) => (
                  <div
                    key={ev.id}
                    onClick={() => setSelected(ev)}
                    className="rounded-lg p-2.5 cursor-pointer"
                    style={{
                      background: "var(--color-background)",
                      borderLeft: `4px solid ${TYPE_COLOR[ev.event_type]}`,
                    }}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-mono" style={{ color: "var(--color-text-muted)", minWidth: "3rem" }}>
                        {formatTime(ev.start_iso)}
                      </span>
                      <span className="flex-1 text-sm">{ev.title}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Edit modal */}
      {editing && (
        <EditEventModal
          event={editing}
          saving={savingEdit}
          onClose={() => setEditing(null)}
          onSave={(patch) => handleSaveEdit(editing, patch)}
        />
      )}

      {/* Detail modal */}
      {selected && (
        <div
          onClick={() => setSelected(null)}
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.6)" }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="rounded-2xl p-6 max-w-md w-full"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
          >
            <div className="flex items-start justify-between gap-3 mb-3">
              <h3 className="font-semibold text-lg">{selected.title}</h3>
              <button onClick={() => setSelected(null)} className="text-xl" style={{ color: "var(--color-text-muted)" }}>
                ×
              </button>
            </div>
            <div className="text-sm space-y-2" style={{ color: "var(--color-text-muted)" }}>
              <div>
                🕐 {selected.start_iso.slice(0, 10)} {formatTime(selected.start_iso)} 〜 {formatTime(selected.end_iso)}
              </div>
              {selected.location && <div>📍 {selected.location}</div>}
              {selected.description && (
                <pre className="whitespace-pre-wrap text-xs mt-2 p-2 rounded" style={{ background: "var(--color-background)" }}>
                  {selected.description}
                </pre>
              )}
              <div>
                <span
                  className="inline-block px-2 py-0.5 rounded-full text-[10px]"
                  style={{
                    background: `${TYPE_COLOR[selected.event_type]}25`,
                    color: TYPE_COLOR[selected.event_type],
                  }}
                >
                  {selected.event_type}
                </span>
              </div>
            </div>
            <div className="flex gap-2 mt-5">
              <button
                onClick={() => setEditing(selected)}
                className="flex-1 px-3 py-2 rounded-lg text-sm font-medium"
                style={{ background: "var(--color-accent)", color: "white" }}
              >
                編集
              </button>
              {selected.html_link && (
                <a
                  href={selected.html_link}
                  target="_blank"
                  rel="noreferrer"
                  className="px-3 py-2 rounded-lg text-sm"
                  style={{ background: "var(--color-surface-hover)", color: "var(--color-text)" }}
                >
                  GCal
                </a>
              )}
              <button
                onClick={() => handleDelete(selected)}
                className="px-3 py-2 rounded-lg text-sm"
                style={{ background: "rgba(239, 68, 68, 0.12)", color: "var(--color-red)", border: "1px solid var(--color-red)" }}
              >
                削除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function toLocalInput(iso: string, allDay: boolean): string {
  if (!iso) return "";
  if (allDay) return iso.slice(0, 10);
  // datetime-local 用に YYYY-MM-DDTHH:MM (秒なし、TZ なし)
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromLocalInput(local: string, allDay: boolean): string {
  if (!local) return "";
  if (allDay) return local.slice(0, 10);
  // ローカル時刻 → +09:00 オフセット付き ISO
  const [datePart, timePart] = local.split("T");
  const tz = -new Date().getTimezoneOffset();
  const sign = tz >= 0 ? "+" : "-";
  const pad = (n: number) => String(Math.floor(Math.abs(n))).padStart(2, "0");
  const offset = `${sign}${pad(tz / 60)}:${pad(tz % 60)}`;
  return `${datePart}T${timePart}:00${offset}`;
}

function EditEventModal({
  event,
  saving,
  onClose,
  onSave,
}: {
  event: Event;
  saving: boolean;
  onClose: () => void;
  onSave: (patch: Partial<Event>) => void;
}) {
  const [title, setTitle] = useState(event.title);
  const [location, setLocation] = useState(event.location || "");
  const [description, setDescription] = useState(event.description || "");
  const [allDay, setAllDay] = useState(event.all_day);
  const [start, setStart] = useState(toLocalInput(event.start_iso, event.all_day));
  const [end, setEnd] = useState(toLocalInput(event.end_iso, event.all_day));

  const submit = () => {
    const patch: Partial<Event> = {};
    if (title !== event.title) patch.title = title;
    if (location !== (event.location || "")) patch.location = location;
    if (description !== (event.description || "")) patch.description = description;
    if (allDay !== event.all_day) patch.all_day = allDay;
    const newStart = fromLocalInput(start, allDay);
    const newEnd = fromLocalInput(end, allDay);
    if (newStart && newStart !== event.start_iso) patch.start_iso = newStart;
    if (newEnd && newEnd !== event.end_iso) patch.end_iso = newEnd;
    if (Object.keys(patch).length === 0) {
      onClose();
      return;
    }
    onSave(patch);
  };

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.6)" }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="rounded-2xl p-6 max-w-md w-full space-y-3"
        style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
      >
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">予定を編集</h3>
          <button onClick={onClose} className="text-xl" style={{ color: "var(--color-text-muted)" }}>
            ×
          </button>
        </div>

        <div>
          <label className="block text-[10px] mb-1 uppercase" style={{ color: "var(--color-text-muted)" }}>
            タイトル
          </label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-3 py-2 rounded text-sm"
            style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
          />
        </div>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={allDay}
            onChange={(e) => {
              const v = e.target.checked;
              setAllDay(v);
              setStart(toLocalInput(start ? fromLocalInput(start, false) : event.start_iso, v));
              setEnd(toLocalInput(end ? fromLocalInput(end, false) : event.end_iso, v));
            }}
          />
          終日
        </label>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-[10px] mb-1 uppercase" style={{ color: "var(--color-text-muted)" }}>
              開始
            </label>
            <input
              type={allDay ? "date" : "datetime-local"}
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="w-full px-3 py-2 rounded text-sm"
              style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
            />
          </div>
          <div>
            <label className="block text-[10px] mb-1 uppercase" style={{ color: "var(--color-text-muted)" }}>
              終了
            </label>
            <input
              type={allDay ? "date" : "datetime-local"}
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="w-full px-3 py-2 rounded text-sm"
              style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
            />
          </div>
        </div>

        <div>
          <label className="block text-[10px] mb-1 uppercase" style={{ color: "var(--color-text-muted)" }}>
            場所
          </label>
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="w-full px-3 py-2 rounded text-sm"
            style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
          />
        </div>

        <div>
          <label className="block text-[10px] mb-1 uppercase" style={{ color: "var(--color-text-muted)" }}>
            メモ
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 rounded text-sm"
            style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
          />
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="px-4 py-2 rounded-full text-sm" style={{ color: "var(--color-text-muted)" }}>
            キャンセル
          </button>
          <button
            onClick={submit}
            disabled={saving}
            className="px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50"
            style={{ background: "var(--color-accent)", color: "white" }}
          >
            {saving ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
