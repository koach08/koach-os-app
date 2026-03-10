import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { searchEmails } from "@/lib/gmail";
import { extractDeadlinesFromEmails } from "@/lib/openai";

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session?.accessToken) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  try {
    const { query, maxResults } = await req.json();

    if (!query) {
      return NextResponse.json(
        { error: "Search query required" },
        { status: 400 }
      );
    }

    const emails = await searchEmails(
      session.accessToken,
      query,
      maxResults || 15
    );

    if (emails.length === 0) {
      return NextResponse.json({ emails: [], events: [] });
    }

    const events = await extractDeadlinesFromEmails(emails);

    return NextResponse.json({
      emailCount: emails.length,
      emails: emails.map((e) => ({
        id: e.id,
        subject: e.subject,
        from: e.from,
        date: e.date,
        snippet: e.snippet,
      })),
      events,
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { error: "Failed to scan emails", details: message },
      { status: 500 }
    );
  }
}
