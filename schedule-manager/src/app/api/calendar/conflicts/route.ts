import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { checkConflicts } from "@/lib/google-calendar";

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session?.accessToken) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  try {
    const { events } = await req.json();
    if (!Array.isArray(events)) {
      return NextResponse.json(
        { error: "events array required" },
        { status: 400 }
      );
    }

    const conflicts = [];
    for (const event of events) {
      const existing = await checkConflicts(
        session.accessToken,
        event.start.dateTime,
        event.end.dateTime
      );
      if (existing.length > 0) {
        conflicts.push({
          proposed: event,
          conflictsWith: existing.map((e) => ({
            summary: e.summary,
            start: e.start?.dateTime,
            end: e.end?.dateTime,
          })),
        });
      }
    }

    return NextResponse.json({ conflicts, hasConflicts: conflicts.length > 0 });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { error: "Failed to check conflicts", details: message },
      { status: 500 }
    );
  }
}
