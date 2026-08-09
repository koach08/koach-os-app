"use client";

import { useCallback, useEffect, useState } from "react";

type ReflectRes = {
  shaded_count: number;
  consistent_with_adhd: boolean;
  band: string;
  summary?: string | null;
  strengths: string[];
  challenges: string[];
  strategies: string[];
  disclaimer: string;
  engine_used: string;
};

const SCALE = ["全くない", "めったにない", "時々", "頻繁", "非常に頻繁"];
const FALLBACK_Q = [
  "物事の難しい部分が終わったあと、詰めの仕上げをやり遂げるのに苦労する",
  "計画性を要する作業で、順序立てて進めるのが難しい",
  "約束や締切、やるべき用事を忘れる",
  "じっくり考える必要がある課題を、取りかかるのを避けたり後回しにする",
  "長時間座っていると、手足をそわそわ・もぞもぞ動かす",
  "エンジンで動かされているように過度に活動的で、じっとしていられない",
];

export default function SelfCheckPage() {
  const [questions, setQuestions] = useState<string[]>(FALLBACK_Q);
  const [scores, setScores] = useState<number[]>(Array(6).fill(-1));
  const [notes, setNotes] = useState("");
  const [result, setResult] = useState<ReflectRes | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [consulting, setConsulting] = useState(false);

  useEffect(() => {
    fetch("/api/assist/adhd-questions")
      .then((r) => r.json())
      .then((d: { questions: string[] }) => d.questions?.length && setQuestions(d.questions))
      .catch(() => {});
    // 前回結果があれば復元
    try {
      const saved = localStorage.getItem("self_check_result");
      if (saved) setResult(JSON.parse(saved));
    } catch {}
  }, []);

  const allAnswered = scores.every((s) => s >= 0);

  const submit = useCallback(() => {
    setLoading(true);
    setError(null);
    fetch("/api/assist/adhd-reflect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scores: scores.map((s) => (s < 0 ? 0 : s)), notes }),
    })
      .then((r) => r.json())
      .then((d: ReflectRes) => {
        setResult(d);
        try {
          localStorage.setItem("self_check_result", JSON.stringify(d));
        } catch {}
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [scores, notes]);

  const consult = useCallback(() => {
    setConsulting(true);
    setError(null);
    setAnswer(null);
    const profile = result
      ? `傾向: ${result.band}（該当${result.shaded_count}/6）\n${result.summary ?? ""}\n対策: ${result.strategies.join(" / ")}`
      : "";
    fetch("/api/assist/adhd-consult", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, profile }),
    })
      .then((r) => r.json())
      .then((d: { answer: string }) => setAnswer(d.answer))
      .catch((e: Error) => setError(e.message))
      .finally(() => setConsulting(false));
  }, [question, result]);

  const card = {
    background: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    color: "var(--color-text)",
  } as const;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="px-8 pt-10 pb-6" style={{ background: "radial-gradient(ellipse at top right, rgba(139, 92, 246, 0.12), transparent 50%)" }}>
        <div className="max-w-3xl mx-auto">
          <h1 className="text-4xl font-bold tracking-tight" style={{ background: "linear-gradient(90deg, #fafafa 0%, #a1a1aa 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            自己理解と相談
          </h1>
          <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>
            過去6か月を思い出して、当てはまる度合いを選んでください。傾向を掴んだ上で「今すべきこと」を相談できます
          </p>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-3xl mx-auto space-y-4">
          {/* 設問 */}
          <div className="rounded-2xl p-5 space-y-4" style={card}>
            {questions.map((q, i) => (
              <div key={i}>
                <div className="text-sm mb-2">
                  <span style={{ color: "var(--color-text-muted)" }}>{i + 1}. </span>
                  {q}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {SCALE.map((label, s) => (
                    <button
                      key={s}
                      onClick={() => setScores((prev) => prev.map((v, idx) => (idx === i ? s : v)))}
                      className="px-3 py-1.5 rounded-full text-xs transition-all"
                      style={{
                        background: scores[i] === s ? "var(--color-accent)" : "transparent",
                        border: "1px solid var(--color-border)",
                        color: scores[i] === s ? "white" : "var(--color-text-muted)",
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="補足（任意）: 特に困っている場面、逆に集中できる場面など"
              rows={2}
              className="w-full px-4 py-2 rounded-xl text-sm outline-none resize-none"
              style={card}
            />
            <button
              onClick={submit}
              disabled={!allAnswered || loading}
              className="px-5 py-2 rounded-full text-sm font-medium disabled:opacity-40 transition-all hover:scale-[1.02]"
              style={{ background: "var(--color-text)", color: "var(--color-background)" }}
            >
              {loading ? "見立て中..." : allAnswered ? "結果を見る" : "全部の項目を選んでください"}
            </button>
          </div>

          {error && (
            <div className="rounded-2xl p-3 text-sm" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid var(--color-red)", color: "var(--color-red)" }}>
              {error}
            </div>
          )}

          {/* 結果 */}
          {result && (
            <div className="space-y-3">
              <div className="rounded-2xl p-5" style={{ background: result.consistent_with_adhd ? "rgba(139,92,246,0.08)" : "var(--color-surface)", border: `1px solid ${result.consistent_with_adhd ? "#8b5cf6" : "var(--color-border)"}` }}>
                <div className="text-[11px] font-medium mb-1" style={{ color: "var(--color-text-muted)" }}>
                  見立て（該当 {result.shaded_count}/6）
                </div>
                <div className="text-lg font-bold">{result.band}</div>
                {result.summary && <div className="text-sm mt-2 leading-relaxed">{result.summary}</div>}
              </div>

              {result.strengths.length > 0 && (
                <div className="rounded-2xl p-5" style={card}>
                  <div className="text-[11px] font-medium mb-2" style={{ color: "var(--color-green, #10b981)" }}>強みに変わる場面</div>
                  <ul className="space-y-1.5 text-sm">{result.strengths.map((s, i) => <li key={i} className="flex gap-2"><span>+</span><span>{s}</span></li>)}</ul>
                </div>
              )}

              {result.challenges.length > 0 && (
                <div className="rounded-2xl p-5" style={card}>
                  <div className="text-[11px] font-medium mb-2" style={{ color: "var(--color-text-muted)" }}>詰まりやすい場面</div>
                  <ul className="space-y-1.5 text-sm">{result.challenges.map((s, i) => <li key={i} className="flex gap-2"><span>·</span><span>{s}</span></li>)}</ul>
                </div>
              )}

              {result.strategies.length > 0 && (
                <div className="rounded-2xl p-5" style={{ background: "rgba(59,130,246,0.06)", border: "1px solid var(--color-accent)" }}>
                  <div className="text-[11px] font-medium mb-2" style={{ color: "var(--color-accent)" }}>負担を減らす具体策</div>
                  <ol className="space-y-1.5 text-sm">{result.strategies.map((s, i) => <li key={i} className="flex gap-2"><span className="font-bold">{i + 1}.</span><span>{s}</span></li>)}</ol>
                </div>
              )}

              <p className="text-[11px] leading-relaxed px-1" style={{ color: "var(--color-text-muted)" }}>
                ⚠ {result.disclaimer}
              </p>
            </div>
          )}

          {/* 相談 */}
          <div className="rounded-2xl p-5 space-y-3" style={card}>
            <div className="text-[11px] font-medium" style={{ color: "var(--color-text-muted)" }}>
              この傾向を踏まえて相談する（今の予定・メール・タスクも一緒に見ます）
            </div>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="例: いろいろ溜まってて動けない。今、何から手を付ければいい?"
              rows={2}
              className="w-full px-4 py-2 rounded-xl text-sm outline-none resize-none"
              style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
            />
            <button
              onClick={consult}
              disabled={consulting}
              className="px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50"
              style={{ background: "var(--color-accent)", color: "white" }}
            >
              {consulting ? "考え中..." : "相談する"}
            </button>
            {answer && (
              <div className="rounded-xl p-4 text-sm whitespace-pre-wrap leading-relaxed" style={{ background: "var(--color-background)", border: "1px solid var(--color-border)" }}>
                {answer}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
