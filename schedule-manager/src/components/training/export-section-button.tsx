"use client";

import { useState } from "react";
import { useSession, signIn } from "next-auth/react";
import { format } from "date-fns";
import { toast } from "sonner";
import type { Section } from "@/types/training";
import { Button } from "@/components/ui/button";
import { CalendarPlus, Loader2, LogIn } from "lucide-react";

interface ExportSectionButtonProps {
  section: Section;
  phaseId: number;
  phaseColor: string;
}

export function ExportSectionButton({
  section,
  phaseId,
  phaseColor,
}: ExportSectionButtonProps) {
  const { data: session } = useSession();
  const [exporting, setExporting] = useState(false);

  // Estimate duration from section name
  const getDuration = (): number => {
    const name = section.name;
    const match = name.match(/(\d+)分/);
    if (match) return parseInt(match[1]);
    if (name.includes("朝")) return 7;
    if (name.includes("昼")) return 7;
    if (name.includes("夜")) return 10;
    if (name.includes("ブレイキン")) return 60;
    if (name.includes("アクロバット")) return 60;
    if (name.includes("筋力") || name.includes("筋トレ")) return 45;
    if (name.includes("有酸素")) return 30;
    return 30;
  };

  // Estimate start time from section name
  const getDefaultTime = (): string => {
    const name = section.name;
    if (name.includes("朝")) return "06:30";
    if (name.includes("昼")) return "12:15";
    if (name.includes("夜")) return "22:00";
    return "18:00";
  };

  const handleExport = async () => {
    if (!session?.accessToken) {
      signIn("google");
      return;
    }

    setExporting(true);
    try {
      const today = format(new Date(), "yyyy-MM-dd");
      const startTime = getDefaultTime();
      const duration = getDuration();

      const [h, m] = startTime.split(":").map(Number);
      const startDate = new Date();
      startDate.setHours(h, m, 0, 0);
      const endDate = new Date(startDate.getTime() + duration * 60000);

      const description = section.exercises
        .map((ex) => `${ex.name} ${ex.reps}`)
        .join("\n");

      const event = {
        summary: `${section.name}（Phase ${phaseId}）`,
        description,
        start: { dateTime: `${today}T${startTime}:00+09:00` },
        end: {
          dateTime: `${today}T${format(endDate, "HH:mm")}:00+09:00`,
        },
        colorId: "6",
        reminders: {
          useDefault: false,
          overrides: [{ method: "popup", minutes: 5 }],
        },
      };

      const res = await fetch("/api/calendar/training", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: [event] }),
      });

      if (res.ok) {
        toast.success(`「${section.name}」をGCalに登録しました`);
      } else {
        throw new Error("Failed");
      }
    } catch {
      toast.error("登録に失敗しました");
    } finally {
      setExporting(false);
    }
  };

  return (
    <button
      onClick={handleExport}
      disabled={exporting}
      className="inline-flex items-center gap-1 rounded border px-2 py-1 text-[10px] font-medium transition-colors hover:opacity-80"
      style={{
        borderColor: `${phaseColor}44`,
        color: phaseColor,
        background: `${phaseColor}08`,
      }}
    >
      {exporting ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : (
        <CalendarPlus className="h-3 w-3" />
      )}
      GCal
    </button>
  );
}
