"use client";

import { useCallback, useEffect, useState } from "react";

// 早く片付けるべき順の1件
type OrderItem = {
  rank?: number;
  kind?: string;
  title: string;
  why?: string;
  is_email?: boolean;
  payoff?: "money" | "progress" | "obligation" | "none" | string;
  minutes?: number;
};

type OrderRes = {
  generated_at: string;
  engine_used: string;
  items: OrderItem[];
  counts: Record<string, number>;
  error?: string | null;
};

type PlanRes = {
  title: string;
  is_email: boolean;
  first_step?: string | null;
  steps: string[];
  minutes?: number | null;
  watch_out?: string | null;
  profit_angle?: string | null;
  email_draft?: string | null;
  engine_used: string;
  error?: string | null;
};

type Slot = { date: string; start_iso: string; end_iso: string; minutes: number };

type ScheduleRes = {
  ok: boolean;
  start_iso: string;
  end_iso: string;
  minutes: number;
  event: { id?: string; html_link?: string | null; summary?: string };
};

const PAYOFF: Record<string, { label: string; color: string }> = {
  money: { label: "💰 利益", color: "var(--color-green, #10b981)" },
  progress: { label: "➡ 前進", color: "var(--color-accent, #3b82f6)" },
  obligation: { label: "🧾 義務", color: "var(--color-text-muted)" },
  none: { label: "", color: "var(--color-text-muted)" },
};

export default function FlowPage() {
  const [order, setOrder] = useState<OrderRes | null>(null);
  const [orderLoading, setOrderLoading] = useState(false);
  const [plan, setPlan] = useState<PlanRes | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [panic, setPanic] = useState(false);
  const [manual, setManual] = useState("");
  const [business, setBusiness] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [scheduling, setScheduling] = useState(false);
  const [scheduled, setScheduled] = useState<ScheduleRes | null>(null);

  // ビジネス相談モードは端末に覚えておく（毎回 OFF から始めるのが既定）
  useEffect(() => {
    setBusiness(localStorage.getItem("flow_business") === "1");
  }, []);
  const toggleBusiness = (v: boolean) => {
    setBusiness(v);
    localStorage.setItem("flow_business", v ? "1" : "0");
  };

  const fmtSlot = (iso: string) => {
    const d = new Date(iso);
    const w = ["日", "月", "火", "水", "木", "金", "土"][d.getDay()];
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    return `${d.getMonth() + 1}/${d.getDate()}(${w}) ${hh}:${mm}`;
  };

  const scheduleBlock = useCallback(
    (startIso?: string) => {
      if (!plan) return;
      setScheduling(true);
      setError(null);
      setScheduled(null);
      fetch("/api/assist/schedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: plan.title,
          minutes: plan.minutes || 30,
          steps: plan.steps,
          first_step: plan.first_step,
          start_iso: startIso ?? null,
        }),
      })
        .then(async (r) => {
          if (!r.ok) {
            const e = await r.json().catch(() => ({ detail: `API error: ${r.status}` }));
            throw new Error(e.detail || `API error: ${r.status}`);
          }
          return r.json();
        })
        .then(setScheduled)
        .catch((e: Error) => setError(e.message))
        .finally(() => setScheduling(false));
    },
    [plan],
  );

  const loadOrder = useCallback(() => {
    setOrderLoading(true);
    setError(null);
    fetch(`/api/assist/order?business=${business}`)
      .then((r) => r.json())
      .then(setOrder)
      .catch((e: Error) => setError(e.message))
      .finally(() => setOrderLoading(false));
  }, [business]);

  const makePlan = useCallback(
    (item: { title: string; kind?: string; is_email?: boolean; context?: string }) => {
      if (!item.title.trim()) return;
      setSelected(item.title);
      setPlan(null);
      setPlanLoading(true);
      setError(null);
      setCopied(false);
      setScheduled(null);
      setSlots([]);
      fetch("/api/assist/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: item.title,
          kind: item.kind ?? "auto",
          is_email: item.is_email ?? null,
          context: item.context ?? "",
          business,
        }),
      })
        .then((r) => r.json())
        .then((d: PlanRes) => {
          setPlan(d);
          const m = d.minutes || 30;
          fetch(`/api/assist/slots?minutes=${m}&days_ahead=3`)
            .then((r) => r.json())
            .then((s: { slots: Slot[] }) => setSlots(s.slots || []))
            .catch(() => setSlots([]));
        })
        .catch((e: Error) => setError(e.message))
        .finally(() => setPlanLoading(false));
    },
    [business],
  );

  const card = {
    background: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    color: "var(--color-text)",
  } as const;

  return (
    <div className="flex-1 overflow-y-auto">
      <div
        className="px-8 pt-10 pb-6"
        style={{ background: "radial-gradient(ellipse at top right, rgba(16, 185, 129, 0.12), transparent 50%)" }}
      >
        <div className="max-w-3xl mx-auto">
          <h1
            className="text-4xl font-bold tracking-tight"
            style={{ background: "linear-gradient(90deg, #fafafa 0%, #a1a1aa 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}
          >
            順番ナビ
          </h1>
          <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>
            重なって散らからないために。考える負担を減らして、まず片付ける順を並べ、選んだ1件を「そのまま動ける手順」に分解します。詰まったら一歩だけ表示。ここを片付けて、本当にやりたい事に集中するための道具です
          </p>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-3xl mx-auto space-y-4">
          {/* コントロール */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={loadOrder}
              disabled={orderLoading}
              className="px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50 transition-all hover:scale-[1.02]"
              style={{ background: "var(--color-text)", color: "var(--color-background)" }}
            >
              {orderLoading ? "並べ中..." : "片付ける順を出す"}
            </button>
            <label className="flex items-center gap-2 text-xs cursor-pointer" style={{ color: "var(--color-text-muted)" }}>
              <input type="checkbox" checked={panic} onChange={(e) => setPanic(e.target.checked)} />
              パニックモード（一歩だけ表示）
            </label>
            <label className="flex items-center gap-2 text-xs cursor-pointer" style={{ color: business ? "var(--color-green, #10b981)" : "var(--color-text-muted)" }}>
              <input type="checkbox" checked={business} onChange={(e) => toggleBusiness(e.target.checked)} />
              💰 ビジネス相談モード（利益の視点を足す）
            </label>
            {order && (
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                メール{order.counts.pending_emails} / backlog{order.counts.open_backlog} / 期限切れ{order.counts.overdue_tasks} · {order.engine_used}
              </span>
            )}
          </div>

          {/* 手動入力: リストに無いものを直接分解 */}
          <div className="flex gap-2">
            <input
              value={manual}
              onChange={(e) => setManual(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && makePlan({ title: manual })}
              placeholder="やることを直接入れて分解（例: 〇〇先生に日程調整メール）"
              className="flex-1 px-4 py-2 rounded-full text-sm outline-none"
              style={{ ...card }}
            />
            <button
              onClick={() => makePlan({ title: manual })}
              disabled={!manual.trim() || planLoading}
              className="px-4 py-2 rounded-full text-sm font-medium disabled:opacity-40"
              style={{ background: "var(--color-accent)", color: "white" }}
            >
              手順に
            </button>
          </div>

          {error && (
            <div className="rounded-2xl p-3 text-sm" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid var(--color-red)", color: "var(--color-red)" }}>
              {error}
            </div>
          )}

          {/* 早く片付けるべき順 */}
          {order && order.items.length > 0 && !panic && (
            <div className="space-y-2">
              <p className="text-xs font-medium" style={{ color: "var(--color-text-muted)" }}>
                早く片付けるべき順（クリックで手順に分解）
              </p>
              {order.items.map((it, i) => {
                const payoff = it.payoff === "money" && !business ? "none" : it.payoff ?? "none";
                const po = PAYOFF[payoff] ?? PAYOFF.none;
                const active = selected === it.title;
                return (
                  <button
                    key={i}
                    onClick={() => makePlan({ title: it.title, kind: it.kind, is_email: it.is_email })}
                    className="w-full text-left rounded-2xl p-4 transition-all hover:scale-[1.01]"
                    style={{ ...card, borderColor: active ? "var(--color-accent)" : "var(--color-border)" }}
                  >
                    <div className="flex items-start gap-3">
                      <span
                        className="shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
                        style={{ background: "var(--color-accent)", color: "white" }}
                      >
                        {it.rank ?? i + 1}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium">{it.title}</div>
                        {it.why && (
                          <div className="text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>
                            {it.why}
                          </div>
                        )}
                        <div className="flex items-center gap-2 mt-1.5 text-[11px]" style={{ color: "var(--color-text-muted)" }}>
                          {po.label && <span style={{ color: po.color }}>{po.label}</span>}
                          {it.minutes ? <span>≈{it.minutes}分</span> : null}
                          {it.is_email && <span>✉ メール</span>}
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {/* 手順 */}
          {planLoading && (
            <div className="rounded-2xl p-5 text-sm" style={{ ...card, color: "var(--color-text-muted)" }}>
              手順に分解中...
            </div>
          )}

          {plan && !planLoading && (
            <div className="space-y-3">
              {selected && (
                <p className="text-xs font-medium" style={{ color: "var(--color-text-muted)" }}>
                  {plan.title}
                  {plan.minutes ? ` · ≈${plan.minutes}分` : ""} · {plan.engine_used}
                </p>
              )}

              {/* 詰まった時の一歩 (パニックモードではこれだけ) */}
              {plan.first_step && (
                <div
                  className="rounded-2xl p-5"
                  style={{ background: "rgba(16,185,129,0.08)", border: "1px solid var(--color-green, #10b981)" }}
                >
                  <div className="text-[11px] font-medium mb-1" style={{ color: "var(--color-green, #10b981)" }}>
                    動けない時は、これだけ
                  </div>
                  <div className={panic ? "text-xl font-bold leading-relaxed" : "text-base font-medium leading-relaxed"}>
                    {plan.first_step}
                  </div>
                </div>
              )}

              {!panic && (
                <>
                  {/* 最短手順 */}
                  {plan.steps.length > 0 && (
                    <div className="rounded-2xl p-5" style={card}>
                      <div className="text-[11px] font-medium mb-2" style={{ color: "var(--color-text-muted)" }}>
                        最短手順
                      </div>
                      <ol className="space-y-2">
                        {plan.steps.map((s, i) => (
                          <li key={i} className="flex gap-3 text-sm leading-relaxed">
                            <span
                              className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold mt-0.5"
                              style={{ background: "var(--color-border)", color: "var(--color-text)" }}
                            >
                              {i + 1}
                            </span>
                            <span>{s}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  )}

                  {/* カレンダーに集中ブロックとして確保 */}
                  <div className="rounded-2xl p-5" style={card}>
                    <div className="text-[11px] font-medium mb-2" style={{ color: "var(--color-text-muted)" }}>
                      カレンダーに入れる（{plan.minutes || 30}分の集中ブロック・手順つき）
                    </div>
                    {scheduled ? (
                      <div className="text-sm leading-relaxed" style={{ color: "var(--color-green, #10b981)" }}>
                        ✓ {fmtSlot(scheduled.start_iso)} に確保しました（{scheduled.minutes}分）
                        {scheduled.event.html_link && (
                          <>
                            {" · "}
                            <a href={scheduled.event.html_link} target="_blank" rel="noreferrer" className="underline">
                              カレンダーで開く
                            </a>
                          </>
                        )}
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <div className="flex flex-wrap gap-2">
                          <button
                            onClick={() => scheduleBlock()}
                            disabled={scheduling}
                            className="px-4 py-2 rounded-full text-sm font-medium disabled:opacity-50"
                            style={{ background: "var(--color-green, #10b981)", color: "white" }}
                          >
                            {scheduling ? "確保中..." : "次の空きに入れる"}
                          </button>
                          {slots.map((s) => (
                            <button
                              key={s.start_iso}
                              onClick={() => scheduleBlock(s.start_iso)}
                              disabled={scheduling}
                              className="px-3 py-2 rounded-full text-xs disabled:opacity-50"
                              style={{ background: "var(--color-surface-hover, rgba(255,255,255,0.06))", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                            >
                              {fmtSlot(s.start_iso)}
                            </button>
                          ))}
                        </div>
                        {slots.length === 0 && (
                          <p className="text-[11px]" style={{ color: "var(--color-text-muted)" }}>
                            空き候補を読み込み中、または直近に空きが見つかりません（「次の空きに入れる」は3日先まで探します）
                          </p>
                        )}
                      </div>
                    )}
                  </div>

                  {/* 利益への効き */}
                  {plan.profit_angle && (
                    <div className="rounded-2xl p-4 text-sm leading-relaxed" style={{ background: "rgba(59,130,246,0.06)", border: "1px solid var(--color-accent)" }}>
                      <span className="font-medium" style={{ color: "var(--color-accent)" }}>💰 これが効く先: </span>
                      {plan.profit_angle}
                    </div>
                  )}

                  {/* 注意 */}
                  {plan.watch_out && (
                    <div className="rounded-2xl p-4 text-sm leading-relaxed" style={{ ...card, color: "var(--color-text-muted)" }}>
                      <span className="font-medium">⚠ 詰まりやすい所: </span>
                      {plan.watch_out}
                    </div>
                  )}

                  {/* メール文面案 */}
                  {plan.email_draft && (
                    <div className="rounded-2xl p-5" style={card}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="text-[11px] font-medium" style={{ color: "var(--color-text-muted)" }}>
                          そのまま送れる文面案
                        </div>
                        <button
                          onClick={() => {
                            navigator.clipboard?.writeText(plan.email_draft ?? "");
                            setCopied(true);
                            setTimeout(() => setCopied(false), 1500);
                          }}
                          className="text-[11px] px-3 py-1 rounded-full"
                          style={{ background: "var(--color-accent)", color: "white" }}
                        >
                          {copied ? "コピーしました" : "コピー"}
                        </button>
                      </div>
                      <div className="text-sm whitespace-pre-wrap leading-relaxed">{plan.email_draft}</div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
