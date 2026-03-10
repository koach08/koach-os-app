import { NextRequest, NextResponse } from "next/server";
import { parseDocument } from "@/lib/document-parser";
import { extractDatesFromText } from "@/lib/openai";

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const file = formData.get("file") as File | null;

    if (!file) {
      return NextResponse.json({ error: "No file provided" }, { status: 400 });
    }

    const buffer = Buffer.from(await file.arrayBuffer());
    const text = await parseDocument(buffer, file.type);

    if (!text.trim()) {
      return NextResponse.json(
        { error: "Could not extract text from file" },
        { status: 400 }
      );
    }

    const events = await extractDatesFromText(text);

    return NextResponse.json({
      filename: file.name,
      textLength: text.length,
      events,
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { error: "Failed to parse document", details: message },
      { status: 500 }
    );
  }
}
