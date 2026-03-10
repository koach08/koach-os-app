"use client";

import { useState } from "react";
import { useSession, signIn } from "next-auth/react";
import { format } from "date-fns";
import { toast } from "sonner";
import { CATEGORIES, getCategoryColorId } from "@/lib/categories";
import type { CategoryId } from "@/lib/categories";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { CalendarPlus, Loader2, LogIn, Plus } from "lucide-react";

interface EventCreatorProps {
  trigger?: React.ReactNode;
  defaultCategory?: CategoryId;
  defaultTitle?: string;
  defaultDescription?: string;
  defaultDate?: string;
  defaultStartTime?: string;
  defaultEndTime?: string;
  onCreated?: () => void;
}

export function EventCreator({
  trigger,
  defaultCategory = "class",
  defaultTitle = "",
  defaultDescription = "",
  defaultDate,
  defaultStartTime = "09:00",
  defaultEndTime = "10:00",
  onCreated,
}: EventCreatorProps) {
  const { data: session } = useSession();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);

  const today = format(new Date(), "yyyy-MM-dd");
  const [category, setCategory] = useState<CategoryId>(defaultCategory);
  const [title, setTitle] = useState(defaultTitle);
  const [description, setDescription] = useState(defaultDescription);
  const [date, setDate] = useState(defaultDate || today);
  const [startTime, setStartTime] = useState(defaultStartTime);
  const [endTime, setEndTime] = useState(defaultEndTime);
  const [isAllDay, setIsAllDay] = useState(false);

  const handleCreate = async () => {
    if (!session?.accessToken) return;
    if (!title.trim()) {
      toast.error("タイトルを入力してください");
      return;
    }

    setCreating(true);
    try {
      const startDateTime = isAllDay
        ? undefined
        : `${date}T${startTime}:00+09:00`;
      const endDateTime = isAllDay
        ? undefined
        : `${date}T${endTime}:00+09:00`;

      const event = isAllDay
        ? {
            summary: title,
            description,
            start: { date },
            end: { date },
            colorId: getCategoryColorId(category),
          }
        : {
            summary: title,
            description,
            start: { dateTime: startDateTime },
            end: { dateTime: endDateTime },
            colorId: getCategoryColorId(category),
            reminders: {
              useDefault: false,
              overrides: [{ method: "popup", minutes: 30 }],
            },
          };

      const res = await fetch("/api/calendar/training", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: [event] }),
      });

      if (res.ok) {
        toast.success("Google Calendarに登録しました");
        setOpen(false);
        resetForm();
        onCreated?.();
      } else {
        throw new Error("Failed");
      }
    } catch {
      toast.error("登録に失敗しました");
    } finally {
      setCreating(false);
    }
  };

  const resetForm = () => {
    setTitle(defaultTitle);
    setDescription(defaultDescription);
    setDate(defaultDate || today);
    setStartTime(defaultStartTime);
    setEndTime(defaultEndTime);
    setCategory(defaultCategory);
    setIsAllDay(false);
  };

  const selectedCat = CATEGORIES.find((c) => c.id === category);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button size="sm" className="gap-1.5 text-xs" variant="outline">
            <Plus className="h-3.5 w-3.5" />
            予定追加
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-md border-border bg-[#0e0e16]">
        <DialogHeader>
          <DialogTitle className="text-base font-black">
            予定を追加 → Google Calendar
          </DialogTitle>
        </DialogHeader>

        {!session?.accessToken ? (
          <div className="py-6 text-center">
            <p className="mb-3 text-xs text-muted-foreground">
              Google Calendar に登録するにはログインが必要です
            </p>
            <Button onClick={() => signIn("google")} variant="outline" className="gap-2">
              <LogIn className="h-4 w-4" />
              Googleでログイン
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Category */}
            <div>
              <label className="mb-1.5 block text-[10px] font-bold text-muted-foreground">
                カテゴリ
              </label>
              <div className="flex flex-wrap gap-1.5">
                {CATEGORIES.map((cat) => (
                  <button
                    key={cat.id}
                    onClick={() => setCategory(cat.id)}
                    className="rounded-md border px-2.5 py-1.5 text-[10px] font-bold transition-colors"
                    style={{
                      borderColor:
                        category === cat.id ? cat.color : "var(--border)",
                      background:
                        category === cat.id ? `${cat.color}15` : "transparent",
                      color:
                        category === cat.id
                          ? cat.color
                          : "var(--muted-foreground)",
                    }}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Title */}
            <div>
              <label className="mb-1 block text-[10px] font-bold text-muted-foreground">
                タイトル
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="例: 教授会、論文締切、ジムトレーニング..."
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                autoFocus
              />
            </div>

            {/* Date */}
            <div>
              <label className="mb-1 block text-[10px] font-bold text-muted-foreground">
                日付
              </label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
            </div>

            {/* All day toggle */}
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={isAllDay}
                onChange={(e) => setIsAllDay(e.target.checked)}
                className="rounded"
              />
              <span className="text-xs">終日</span>
            </label>

            {/* Time */}
            {!isAllDay && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-[10px] font-bold text-muted-foreground">
                    開始
                  </label>
                  <input
                    type="time"
                    value={startTime}
                    onChange={(e) => setStartTime(e.target.value)}
                    className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-sm"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[10px] font-bold text-muted-foreground">
                    終了
                  </label>
                  <input
                    type="time"
                    value={endTime}
                    onChange={(e) => setEndTime(e.target.value)}
                    className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-sm"
                  />
                </div>
              </div>
            )}

            {/* Description */}
            <div>
              <label className="mb-1 block text-[10px] font-bold text-muted-foreground">
                メモ（任意）
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="補足情報..."
                rows={2}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
            </div>

            {/* Submit */}
            <Button
              onClick={handleCreate}
              disabled={creating || !title.trim()}
              className="w-full gap-1.5 text-sm"
              style={{
                background: selectedCat?.color,
                color: "#fff",
              }}
            >
              {creating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <CalendarPlus className="h-4 w-4" />
              )}
              Google Calendar に登録
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
