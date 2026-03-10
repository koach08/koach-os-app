import type { ExtractedEvent } from "./openai";

export function generateICS(events: ExtractedEvent[]): string {
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Schedule Manager//JP",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
  ];

  for (const event of events) {
    const startDate = new Date(event.date);
    const endDate = event.endDate
      ? new Date(event.endDate)
      : new Date(startDate.getTime() + 60 * 60 * 1000); // default 1h

    lines.push("BEGIN:VEVENT");
    lines.push(`DTSTART:${formatICSDate(startDate)}`);
    lines.push(`DTEND:${formatICSDate(endDate)}`);
    lines.push(`SUMMARY:${escapeICS(event.title)}`);
    if (event.description) {
      lines.push(`DESCRIPTION:${escapeICS(event.description)}`);
    }
    lines.push(`UID:${crypto.randomUUID()}@schedule-manager`);
    lines.push("END:VEVENT");
  }

  lines.push("END:VCALENDAR");
  return lines.join("\r\n");
}

function formatICSDate(date: Date): string {
  return date
    .toISOString()
    .replace(/[-:]/g, "")
    .replace(/\.\d{3}/, "");
}

function escapeICS(text: string): string {
  return text
    .replace(/\\/g, "\\\\")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,")
    .replace(/\n/g, "\\n");
}
