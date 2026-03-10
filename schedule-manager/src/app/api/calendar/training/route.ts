import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { createEvents } from "@/lib/google-calendar";

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session?.accessToken) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  try {
    const { events } = await req.json();
    if (!Array.isArray(events) || events.length === 0) {
      return NextResponse.json(
        { error: "No events provided" },
        { status: 400 }
      );
    }

    const results = await createEvents(session.accessToken, events);
    return NextResponse.json({
      created: results.length,
      events: results,
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { error: "Failed to create events", details: message },
      { status: 500 }
    );
  }
}
