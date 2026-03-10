import { NextRequest, NextResponse } from "next/server";
import OpenAI from "openai";

export async function POST(req: NextRequest) {
  try {
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) {
      return NextResponse.json(
        { error: "OPENAI_API_KEY is not set" },
        { status: 500 }
      );
    }

    const { changedTask, action, tasks } = await req.json();

    const today = new Date().toISOString().split("T")[0];

    const taskSummary = tasks
      .filter((t: { status: string }) => t.status !== "done")
      .map(
        (t: {
          id: string;
          title: string;
          category: string;
          priority: string;
          dueDate: string | null;
          dueTime: string | null;
          status: string;
          estimatedMinutes: number | null;
        }) =>
          `- [${t.id}] ${t.title} | カテゴリ: ${t.category} | 優先度: ${t.priority} | 期限: ${t.dueDate || "未設定"} ${t.dueTime || ""} | ステータス: ${t.status} | 見積: ${t.estimatedMinutes || "?"}分`
      )
      .join("\n");

    const client = new OpenAI({ apiKey });
    const res = await client.chat.completions.create({
      model: "gpt-4o-mini",
      messages: [
        {
          role: "system",
          content: `あなたは大学教員のスケジュール最適化アシスタントです。
タスクの変更に基づき、他のタスクのリスケジュール提案をしてください。

ルール:
- 優先順位: 家族 > 学生 > 研究 > プラットフォーム > 収益 > 個人成長
- 裁量労働制なので時間は柔軟だが、締切は厳守
- トレーニングは毎日のルーティンとして維持（朝/昼/夜の短時間セッション）
- 会議・授業は動かせない
- 締切が近いタスクは前倒し推奨
- 今日の日付: ${today}

以下のJSON配列形式で返してください:
{
  "suggestions": [
    {
      "taskId": "task_xxx",
      "newDueDate": "2026-03-15",
      "newDueTime": "14:00",
      "reason": "理由の説明"
    }
  ],
  "summary": "全体的なアドバイス（1-2文）"
}

変更が不要な場合は空配列を返してください。`,
        },
        {
          role: "user",
          content: `以下の変更がありました:
タスク「${changedTask.title}」が${action === "completed" ? "完了" : action === "rescheduled" ? "日程変更" : "削除"}されました。
${action === "rescheduled" ? `新しい期限: ${changedTask.dueDate} ${changedTask.dueTime || ""}` : ""}

現在のタスク一覧（未完了）:
${taskSummary}

他のタスクのリスケジュール提案をお願いします。`,
        },
      ],
      response_format: { type: "json_object" },
      temperature: 0.3,
    });

    const content = res.choices[0]?.message?.content || "{}";
    const parsed = JSON.parse(content);

    return NextResponse.json({
      suggestions: parsed.suggestions || [],
      summary: parsed.summary || "",
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { error: "Reschedule failed", details: message },
      { status: 500 }
    );
  }
}
