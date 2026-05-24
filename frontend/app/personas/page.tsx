"use client";

import { useEffect, useState } from "react";

type Persona = {
  id: string;
  name: string;
  emoji: string;
  color: string;
  engine: string;
  system_prompt: string;
  system_uses_style_profile?: boolean;
};

type Answer = {
  persona_id: string;
  name: string;
  emoji: string;
  color: string;
  engine_used: string;
  model_used: string;
  answer: string;
};

export default function PersonasPage() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [question, setQuestion] = useState("");
  const [context, setContext] = useState("");
  const [answers, setAnswers] = useState<Answer[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [styleChars, setStyleChars] = useState(0);
  const [showStyleEditor, setShowStyleEditor] = useState(false);
  const [styleContent, setStyleContent] = useState("");
  const [savingStyle, setSavingStyle] = useState(false);
  const [learning, setLearning] = useState(false);

  const load = async () => {
    const d = await fetch("/api/personas").then((r) => r.json());
    setPersonas(d.personas ?? []);
    setStyleChars(d.style_profile_chars ?? 0);
    if (selected.size === 0) {
      setSelected(new Set((d.personas ?? []).map((p: Persona) => p.id)));
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const togglePersona = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const ask = async () => {
    if (!question.trim() || selected.size === 0) return;
    setLoading(true);
    setError(null);
    setAnswers([]);
    try {
      const r = await fetch("/api/persona-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          persona_ids: Array.from(selected),
          context,
        }),
      });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      setAnswers(d.answers ?? []);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const openStyleEditor = async () => {
    const d = await fetch("/api/personas/style-profile").then((r) => r.json());
    setStyleContent(d.content ?? "");
    setShowStyleEditor(true);
  };

  const saveStyle = async () => {
    setSavingStyle(true);
    try {
      await fetch("/api/personas/style-profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: styleContent }),
      });
      setStyleChars(styleContent.length);
      setShowStyleEditor(false);
    } finally {
      setSavingStyle(false);
    }
  };

  const learnStyle = async () => {
    setLearning(true);
    try {
      const r = await fetch("/api/personas/style-profile/learn", { method: "POST" });
      if (r.ok) {
        const d = await r.json();
        setStyleChars(d.total_chars ?? 0);
        alert(`スタイル更新: +${d.added_chars} 字\n${d.preview}`);
      }
    } finally {
      setLearning(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div
        className="px-8 pt-12 pb-8"
        style={{
          background:
            "radial-gradient(ellipse at top left, rgba(168, 85, 247, 0.12), transparent 60%), radial-gradient(ellipse at top right, rgba(59, 130, 246, 0.08), transparent 50%)",
        }}
      >
        <div className="max-w-6xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            Multi-Persona Mind
          </p>
          <h1 className="text-4xl font-bold tracking-tight">複数視点で考える</h1>
          <p className="mt-3 text-sm" style={{ color: "var(--color-text-muted)" }}>
            同じ問いを 志柿本人 / 批判者 / 外部識者 / 楽観 / 懐疑 に並列で投げる。バイアスを単一視点に閉じない。
          </p>
          <div className="mt-4 flex flex-wrap gap-2 items-center">
            <button
              onClick={openStyleEditor}
              className="px-3 py-1.5 rounded-full text-xs"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}
            >
              📝 Style Profile を編集 ({styleChars} 字)
            </button>
            <button
              onClick={learnStyle}
              disabled={learning}
              className="px-3 py-1.5 rounded-full text-xs disabled:opacity-50"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}
            >
              {learning ? "学習中..." : "🧠 最近のログから学習 (追記)"}
            </button>
          </div>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-6xl mx-auto space-y-6">
          <div
            className="rounded-2xl p-5 space-y-3"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
          >
            <div>
              <label className="block text-[10px] mb-1 uppercase" style={{ color: "var(--color-text-muted)" }}>
                問い
              </label>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={3}
                placeholder="例: 「EGAKU AI を世界市場に出すなら、まず何から動くべきか」"
                className="w-full px-3 py-2 rounded text-sm"
                style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
              />
            </div>
            <details className="text-xs">
              <summary className="cursor-pointer" style={{ color: "var(--color-text-muted)" }}>
                追加コンテキスト (省略可)
              </summary>
              <textarea
                value={context}
                onChange={(e) => setContext(e.target.value)}
                rows={2}
                placeholder="現状の数字・制約・前提など"
                className="w-full mt-2 px-3 py-2 rounded text-sm"
                style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
              />
            </details>
            <div>
              <label className="block text-[10px] mb-2 uppercase" style={{ color: "var(--color-text-muted)" }}>
                投げる persona ({selected.size} / {personas.length})
              </label>
              <div className="flex flex-wrap gap-2">
                {personas.map((p) => {
                  const on = selected.has(p.id);
                  return (
                    <button
                      key={p.id}
                      onClick={() => togglePersona(p.id)}
                      className="px-3 py-1.5 rounded-full text-xs transition-all"
                      style={{
                        background: on ? p.color : "transparent",
                        color: on ? "white" : "var(--color-text-muted)",
                        border: `1px solid ${on ? p.color : "var(--color-border)"}`,
                      }}
                    >
                      {p.emoji} {p.name}
                    </button>
                  );
                })}
              </div>
            </div>
            <button
              onClick={ask}
              disabled={loading || !question.trim() || selected.size === 0}
              className="px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50"
              style={{ background: "var(--color-accent)", color: "white" }}
            >
              {loading ? `${selected.size} persona に並列で問い合わせ中...` : `${selected.size} persona に問う`}
            </button>
          </div>

          {error && (
            <div className="p-3 rounded-xl text-sm" style={{ background: "rgba(239, 68, 68, 0.08)", color: "var(--color-red)" }}>
              {error}
            </div>
          )}

          {answers.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {answers.map((a) => (
                <div
                  key={a.persona_id}
                  className="rounded-2xl p-5"
                  style={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    borderTop: `3px solid ${a.color}`,
                  }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="font-semibold text-sm flex items-center gap-2">
                      <span className="text-xl">{a.emoji}</span>
                      <span>{a.name}</span>
                    </div>
                    <span className="text-[10px] font-mono" style={{ color: "var(--color-text-muted)" }}>
                      {a.engine_used}
                    </span>
                  </div>
                  <div className="text-sm whitespace-pre-wrap leading-relaxed">{a.answer}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {showStyleEditor && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.6)" }}
          onClick={() => setShowStyleEditor(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="rounded-2xl p-6 w-full max-w-3xl max-h-[85vh] flex flex-col"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold">Shigaki Style Profile (MD)</h3>
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                {styleContent.length} 字
              </span>
            </div>
            <p className="text-xs mb-3" style={{ color: "var(--color-text-muted)" }}>
              ここに書いた内容は shigaki persona の system prompt に常時注入されます。
              ローカルの koach_style_guide_v2.md を貼り付けたり、学習で追記されたものを編集できます。
            </p>
            <textarea
              value={styleContent}
              onChange={(e) => setStyleContent(e.target.value)}
              className="flex-1 px-3 py-2 rounded text-sm font-mono"
              style={{
                background: "var(--color-background)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text)",
                minHeight: "400px",
              }}
            />
            <div className="flex justify-end gap-2 mt-3">
              <button onClick={() => setShowStyleEditor(false)} className="px-4 py-2 rounded-full text-sm" style={{ color: "var(--color-text-muted)" }}>
                キャンセル
              </button>
              <button
                onClick={saveStyle}
                disabled={savingStyle}
                className="px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50"
                style={{ background: "var(--color-accent)", color: "white" }}
              >
                {savingStyle ? "保存中..." : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
