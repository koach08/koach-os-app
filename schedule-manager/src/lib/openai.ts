import OpenAI from "openai";

function getClient() {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error("OPENAI_API_KEY is not set");
  return new OpenAI({ apiKey });
}

export interface ExtractedEvent {
  title: string;
  date: string; // ISO date or datetime
  endDate?: string;
  category: string;
  description?: string;
  confidence: number; // 0-1
}

export async function extractDatesFromText(
  text: string
): Promise<ExtractedEvent[]> {
  const client = getClient();
  const res = await client.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [
      {
        role: "system",
        content: `あなたは文書から日程・締切情報を抽出するアシスタントです。
以下のJSON配列形式で抽出してください。
[
  {
    "title": "イベント名/締切名",
    "date": "2026-03-15T10:00:00+09:00",
    "endDate": "2026-03-15T12:00:00+09:00" (任意),
    "category": "class"|"deadline"|"research"|"growth"|"training"|"family",
    "description": "補足情報",
    "confidence": 0.0-1.0
  }
]
日付が曖昧な場合はconfidenceを低くしてください。
日本語の日付表記（令和、和暦含む）も正確に解釈してください。
今年は2026年です。`,
      },
      {
        role: "user",
        content: `以下の文書から日程・締切を全て抽出してください:\n\n${text.slice(0, 8000)}`,
      },
    ],
    response_format: { type: "json_object" },
    temperature: 0.1,
  });

  try {
    const content = res.choices[0]?.message?.content || "{}";
    const parsed = JSON.parse(content);
    return Array.isArray(parsed) ? parsed : parsed.events || [];
  } catch {
    return [];
  }
}

export async function extractDeadlinesFromEmails(
  emails: { subject: string; body: string; from: string; date: string }[]
): Promise<ExtractedEvent[]> {
  const client = getClient();
  const emailSummary = emails
    .map(
      (e, i) =>
        `--- メール ${i + 1} ---\n件名: ${e.subject}\n差出人: ${e.from}\n日付: ${e.date}\n本文:\n${e.body.slice(0, 2000)}`
    )
    .join("\n\n");

  const res = await client.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [
      {
        role: "system",
        content: `あなたはメールから締切・重要日程を抽出するアシスタントです。
大学教員の受信メールを分析し、以下のJSON配列で返してください:
[
  {
    "title": "締切名/イベント名",
    "date": "2026-03-15T17:00:00+09:00",
    "endDate": null,
    "category": "deadline"|"class"|"research",
    "description": "メールの要約（1-2文）",
    "confidence": 0.0-1.0
  }
]
締切が明確なものはconfidence高め、推測のものは低めにしてください。
今年は2026年です。`,
      },
      {
        role: "user",
        content: `以下のメールから締切・日程を抽出:\n\n${emailSummary.slice(0, 10000)}`,
      },
    ],
    response_format: { type: "json_object" },
    temperature: 0.1,
  });

  try {
    const content = res.choices[0]?.message?.content || "{}";
    const parsed = JSON.parse(content);
    return Array.isArray(parsed) ? parsed : parsed.events || [];
  } catch {
    return [];
  }
}
