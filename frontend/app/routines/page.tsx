"use client";

import { useEffect, useState, useCallback } from "react";

type Routine = {
  id: string;
  name: string;
  kind: "ai" | "builtin" | "cowork";
  task: string;
  builtin_ref: string;
  cadence: string;
  at_hour: number;
  weekday: number;
  engine: string;
  delivery: string;
  enabled: boolean;
  last_run: string | null;
  last_status: string | null;
};

type Run = {
  id: string;
  routine_name: string;
  kind: string;
  trigger: string;
  status: string;
  engine_used?: string;
  result_text?: string;
  error?: string;
  started_at: string;
};

type Meta = {
  cadences: string[];
  kinds: string[];
  builtins: { ref: string; label: string }[];
  engines: string[];
};

const KIND_LABEL: Record<string, string> = {
  ai: "AI 自走",
  builtin: "組み込みジョブ",
  cowork: "Cowork 引き継ぎ",
};
const CADENCE_LABEL: Record<string, string> = {
  manual: "手動のみ",
  hourly: "毎時",
  daily: "毎日",
  weekdays: "平日",
  weekly: "毎週",
};
const WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"];

function fmt(iso: string | null): string {
  if (!iso) return "未実行";
  try {
    return new Date(iso).toLocaleString("ja-JP", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

export default function RoutinesPage() {
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  // form
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"ai" | "builtin" | "cowork">("ai");
  const [task, setTask] = useState("");
  const [builtinRef, setBuiltinRef] = useState("daily-brief");
  const [cadence, setCadence] = useState("daily");
  const [atHour, setAtHour] = useState("8");
  const [weekday, setWeekday] = useState("0");
  const [engine, setEngine] = useState("auto");
  const [delivery, setDelivery] = useState("inapp");

  const load = useCallback(() => {
    fetch("/api/routines")
      .then((r) => r.json())
      .then((d) => setRoutines(d.routines ?? []))
      .catch((e: Error) => setError(e.message));
    fetch("/api/routines/runs?limit=30")
      .then((r) => r.json())
      .then((d) => setRuns(d.runs ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetch("/api/routines/meta").then((r) => r.json()).then(setMeta).catch(() => {});
    load();
  }, [load]);

  const handleCreate = async () => {
    if (!name.trim()) return;
    if ((kind === "ai" || kind === "cowork") && !task.trim()) {
      setError("AI / Cowork ルーティンには内容が必要です");
      return;
    }
    setBusy("create");
    setError(null);
    try {
      const r = await fetch("/api/routines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          kind,
          task,
          builtin_ref: builtinRef,
          cadence,
          at_hour: parseInt(atHour, 10) || 8,
          weekday: parseInt(weekday, 10) || 0,
          engine,
          delivery,
        }),
      });
      if (!r.ok) throw new Error(await r.text());
      setName("");
      setTask("");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const TEMPLATES: Array<{ label: string; body: Record<string, unknown> }> = [
    { label: "☀ 朝のブリーフ(毎日7時・メール)", body: { name: "朝のブリーフ", kind: "builtin", builtin_ref: "daily-brief", cadence: "daily", at_hour: 7, delivery: "email", engine: "claude" } },
    { label: "🌙 夜の振り返り(毎日21時)", body: { name: "夜の振り返り", kind: "builtin", builtin_ref: "evening-brief", cadence: "daily", at_hour: 21, delivery: "inapp", engine: "claude" } },
    { label: "📊 週次レビュー(月9時・メール)", body: { name: "週次レビュー", kind: "builtin", builtin_ref: "weekly-review", cadence: "weekly", weekday: 0, at_hour: 9, delivery: "email", engine: "claude" } },
    { label: "📧 メールスキャン(毎日8時)", body: { name: "対応待ちメール スキャン", kind: "builtin", builtin_ref: "email-scan", cadence: "daily", at_hour: 8, delivery: "inapp" } },
    { label: "📈 crypto 週次レビュー(月9時)", body: { name: "crypto 週次レビュー", kind: "ai", task: "crypto-trader の直近ログを要約し、気になる点と改善案を3つ挙げて", cadence: "weekly", weekday: 0, at_hour: 9, engine: "auto", delivery: "inapp" } },
    { label: "🤝 週次メール棚卸し(Cowork引継ぎ・月)", body: { name: "週次メール棚卸し", kind: "cowork", task: "今週のメールを整理して未対応を一覧化し、返信の下書きまで作る", cadence: "weekly", weekday: 0, at_hour: 9, delivery: "email" } },
  ];

  const addTemplate = async (body: Record<string, unknown>) => {
    setBusy("create");
    setError(null);
    try {
      const r = await fetch("/api/routines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(await r.text());
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const openInClaude = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      /* clipboard 不可でも開く */
    }
    try {
      const r = await fetch("/api/ai-services");
      const d = await r.json();
      const svc = (d.services ?? []).find(
        (s: { name?: string; url?: string }) =>
          /claude|cowork/i.test(s.name ?? "") || /claude\.(ai|com)/i.test(s.url ?? "")
      );
      if (svc?.url) {
        window.open(svc.url, `koach-ai-${svc.id}`, "popup,width=1100,height=900,scrollbars=yes,resizable=yes");
        return;
      }
    } catch {
      /* fall through */
    }
    window.open("https://claude.ai/", "_blank");
  };

  const toggle = async (rt: Routine) => {
    await fetch(`/api/routines/${rt.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !rt.enabled }),
    });
    load();
  };

  const runNow = async (rt: Routine) => {
    setBusy(rt.id);
    setError(null);
    try {
      const r = await fetch(`/api/routines/${rt.id}/run`, { method: "POST" });
      if (!r.ok) throw new Error(await r.text());
      load();
      setExpanded(rt.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const remove = async (id: string) => {
    if (!confirm("このルーティンを削除しますか？")) return;
    await fetch(`/api/routines/${id}`, { method: "DELETE" });
    load();
  };

  const inputStyle = {
    background: "var(--color-background)",
    border: "1px solid var(--color-border)",
    color: "var(--color-text)",
  };
  const engines = meta?.engines ?? ["auto", "claude", "gpt", "gemini", "grok", "perplexity", "venice", "groq"];

  const latestRunFor = (rid: string) => runs.find((x) => x.routine_name && routines.find((rt) => rt.id === rid)?.name === x.routine_name);

  return (
    <div className="flex-1 overflow-y-auto">
      <div
        className="px-8 pt-10 pb-6"
        style={{ background: "radial-gradient(ellipse at top right, rgba(139, 92, 246, 0.12), transparent 50%)" }}
      >
        <div className="max-w-5xl mx-auto">
          <h1
            className="text-4xl font-bold tracking-tight"
            style={{ background: "linear-gradient(90deg, #fafafa 0%, #a1a1aa 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}
          >
            ルーティン
          </h1>
          <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>
            Cowork 風の自動タスク。一度書いて cadence を選べば自動で回る。Cowork に渡すべきものは「引き継ぎ」で指示書を用意する
          </p>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-5xl mx-auto space-y-6">
          {/* Create form */}
          <div
            className="rounded-2xl p-4 space-y-3"
            style={{ background: "rgba(139, 92, 246, 0.06)", border: "1px solid rgba(139, 92, 246, 0.35)" }}
          >
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="ルーティン名 (例: 毎週月曜 crypto 戦略レビュー)"
              className="w-full px-3 py-2 rounded-lg text-sm"
              style={inputStyle}
            />
            <div className="flex flex-wrap gap-2">
              {(["ai", "builtin", "cowork"] as const).map((k) => (
                <button
                  key={k}
                  onClick={() => setKind(k)}
                  className="px-3 py-1 rounded-full text-xs transition-all"
                  style={{
                    background: kind === k ? "var(--color-text)" : "transparent",
                    color: kind === k ? "var(--color-background)" : "var(--color-text-muted)",
                    border: "1px solid var(--color-border)",
                  }}
                >
                  {KIND_LABEL[k]}
                </button>
              ))}
            </div>

            {kind === "builtin" ? (
              <select value={builtinRef} onChange={(e) => setBuiltinRef(e.target.value)} className="w-full px-3 py-2 rounded-lg text-sm" style={inputStyle}>
                {(meta?.builtins ?? []).map((b) => (
                  <option key={b.ref} value={b.ref}>
                    {b.label}
                  </option>
                ))}
              </select>
            ) : (
              <textarea
                value={task}
                onChange={(e) => setTask(e.target.value)}
                placeholder={
                  kind === "cowork"
                    ? "Cowork にやってほしいこと (例: 今週のメールを整理して未対応を一覧化し下書きまで作る)"
                    : "AI に自走させたいこと (例: crypto-trader のログを要約し、気になる点を3つ挙げて)"
                }
                rows={3}
                className="w-full px-3 py-2 rounded-lg text-sm resize-none"
                style={inputStyle}
              />
            )}

            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <select value={cadence} onChange={(e) => setCadence(e.target.value)} className="px-3 py-2 rounded-lg text-sm" style={inputStyle}>
                {(meta?.cadences ?? ["manual", "hourly", "daily", "weekdays", "weekly"]).map((c) => (
                  <option key={c} value={c}>
                    {CADENCE_LABEL[c] ?? c}
                  </option>
                ))}
              </select>
              {cadence === "weekly" && (
                <select value={weekday} onChange={(e) => setWeekday(e.target.value)} className="px-3 py-2 rounded-lg text-sm" style={inputStyle}>
                  {WEEKDAYS.map((w, i) => (
                    <option key={i} value={i}>
                      {w}曜
                    </option>
                  ))}
                </select>
              )}
              {cadence !== "manual" && cadence !== "hourly" && (
                <select value={atHour} onChange={(e) => setAtHour(e.target.value)} className="px-3 py-2 rounded-lg text-sm" style={inputStyle}>
                  {Array.from({ length: 24 }, (_, h) => (
                    <option key={h} value={h}>
                      {h}時以降
                    </option>
                  ))}
                </select>
              )}
              {kind !== "cowork" && (
                <select value={engine} onChange={(e) => setEngine(e.target.value)} className="px-3 py-2 rounded-lg text-sm" style={inputStyle}>
                  {engines.map((en) => (
                    <option key={en} value={en}>
                      {en === "auto" ? "AI 自動選択" : en}
                    </option>
                  ))}
                </select>
              )}
              <select value={delivery} onChange={(e) => setDelivery(e.target.value)} className="px-3 py-2 rounded-lg text-sm" style={inputStyle}>
                <option value="inapp">結果はアプリ内</option>
                <option value="email">結果をメール送信</option>
              </select>
            </div>

            <div className="flex justify-end">
              <button
                onClick={handleCreate}
                disabled={!name.trim() || busy === "create"}
                className="px-5 py-1.5 rounded-full text-sm font-medium disabled:opacity-50 transition-all hover:scale-[1.02]"
                style={{ background: "var(--color-text)", color: "var(--color-background)" }}
              >
                {busy === "create" ? "..." : "ルーティン追加"}
              </button>
            </div>
          </div>

          {/* Templates */}
          <div>
            <div className="text-xs mb-2" style={{ color: "var(--color-text-muted)" }}>
              テンプレートから追加(ワンクリック):
            </div>
            <div className="flex flex-wrap gap-1.5">
              {TEMPLATES.map((t) => (
                <button
                  key={t.label}
                  onClick={() => addTemplate(t.body)}
                  disabled={busy === "create"}
                  className="px-3 py-1.5 rounded-full text-xs transition-all hover:scale-[1.02] disabled:opacity-40"
                  style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="rounded-2xl p-3 text-sm" style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid var(--color-red)", color: "var(--color-red)" }}>
              {error}
            </div>
          )}

          {/* Routine list */}
          <div className="space-y-2">
            {routines.length === 0 ? (
              <div className="rounded-2xl p-10 text-center" style={{ background: "var(--color-surface)", border: "1px dashed var(--color-border-light)" }}>
                <p className="text-3xl mb-2">🔁</p>
                <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                  まだルーティンはありません
                </p>
              </div>
            ) : (
              routines.map((rt) => {
                const lr = latestRunFor(rt.id);
                return (
                  <div key={rt.id} className="rounded-xl p-4" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", opacity: rt.enabled ? 1 : 0.55 }}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-medium">{rt.name}</span>
                          <span className="px-1.5 rounded text-[11px]" style={{ background: "rgba(139,92,246,0.15)", color: "#c4b5fd" }}>
                            {KIND_LABEL[rt.kind]}
                          </span>
                          <span className="text-[11px]" style={{ color: "var(--color-text-muted)" }}>
                            {CADENCE_LABEL[rt.cadence] ?? rt.cadence}
                            {rt.cadence === "weekly" ? ` ${WEEKDAYS[rt.weekday]}曜` : ""}
                            {rt.cadence !== "manual" && rt.cadence !== "hourly" ? ` ${rt.at_hour}時〜` : ""}
                            {rt.kind !== "cowork" ? ` · ${rt.engine === "auto" ? "AI自動" : rt.engine}` : ""}
                            {rt.delivery === "email" ? " · メール" : ""}
                          </span>
                        </div>
                        {(rt.task || rt.builtin_ref) && (
                          <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                            {rt.kind === "builtin" ? meta?.builtins.find((b) => b.ref === rt.builtin_ref)?.label ?? rt.builtin_ref : rt.task}
                          </p>
                        )}
                        <div className="text-[11px] mt-1.5" style={{ color: "var(--color-text-muted)" }}>
                          最終: {fmt(rt.last_run)}
                          {rt.last_status && ` (${rt.last_status})`}
                        </div>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <button onClick={() => toggle(rt)} className="px-2 py-0.5 rounded text-xs" style={{ border: "1px solid var(--color-border)", color: rt.enabled ? "#86efac" : "var(--color-text-muted)" }} title="有効/無効">
                          {rt.enabled ? "ON" : "OFF"}
                        </button>
                        <button onClick={() => runNow(rt)} disabled={busy === rt.id} className="px-2 py-0.5 rounded text-xs disabled:opacity-40" style={{ border: "1px solid var(--color-border)" }} title="今すぐ実行">
                          {busy === rt.id ? "..." : "▶"}
                        </button>
                        <button onClick={() => remove(rt.id)} className="px-2 py-0.5 rounded text-xs" style={{ color: "var(--color-text-muted)" }} title="削除">
                          ✕
                        </button>
                      </div>
                    </div>
                    {lr && (
                      <div className="mt-2">
                        <button onClick={() => setExpanded(expanded === rt.id ? null : rt.id)} className="text-[11px]" style={{ color: "var(--color-text-muted)" }}>
                          {expanded === rt.id ? "▼ 直近の結果を隠す" : "▶ 直近の結果を見る"}
                        </button>
                        {expanded === rt.id && (
                          <pre
                            className="mt-1 text-xs whitespace-pre-wrap p-3 rounded-lg overflow-x-auto"
                            style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                          >
                            {lr.error ? `エラー: ${lr.error}` : lr.result_text || "(結果なし)"}
                          </pre>
                        )}
                        {expanded === rt.id && rt.kind === "cowork" && lr.result_text && (
                          <button
                            onClick={() => openInClaude(lr.result_text || "")}
                            className="mt-2 px-3 py-1.5 rounded-full text-xs transition-all hover:scale-[1.02]"
                            style={{ background: "rgba(139,92,246,0.18)", border: "1px solid rgba(139,92,246,0.5)", color: "#c4b5fd" }}
                            title="指示書をコピーして Claude を開く(貼り付けて Cowork で実行)"
                          >
                            📋 コピーして Claude を開く
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* Run feed */}
          {runs.length > 0 && (
            <div>
              <h2 className="text-sm font-medium mb-2" style={{ color: "var(--color-text-muted)" }}>
                実行履歴
              </h2>
              <div className="space-y-1">
                {runs.slice(0, 15).map((r) => (
                  <div key={r.id} className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
                    <span style={{ color: r.status === "error" ? "var(--color-red)" : r.status === "prepared" ? "#c4b5fd" : "#86efac" }}>●</span>
                    <span style={{ color: "var(--color-text-muted)" }}>{fmt(r.started_at)}</span>
                    <span className="font-medium">{r.routine_name}</span>
                    <span style={{ color: "var(--color-text-muted)" }}>
                      {r.status}
                      {r.engine_used ? ` · ${r.engine_used}` : ""}
                      {r.trigger === "cron" ? " · 自動" : " · 手動"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
