import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { listEvents } from "@/lib/google-calendar";

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session?.accessToken) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const { searchParams } = new URL(req.url);
  const timeMin =
    searchParams.get("timeMin") || new Date().toISOString();
  const timeMax =
    searchParams.get("timeMax") ||
    new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();

  try {
    const events = await listEvents(session.accessToken, timeMin, timeMax);
    return NextResponse.json({ events });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { error: "Failed to fetch events", details: message },
      { status: 500 }
    );
  }
}
