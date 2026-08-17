"use client";

/**
 * 健康・コンディション — Apple Watch / Health の数値を眺める画面。
 * データの入口は iOS ショートカット + オートメーション (毎朝自動送信)。
 * ショートカットを短くするため GET /api/health-data/quick に URL で値を並べる形にした。
 * この画面は「見るだけ」が主。手入力は保険 (自動が回れば触らない)。
 * 受け皿・保存・state-hint はバックエンド実装済み
 * (backend/routers/health_intake.py + health_shortcut.py)。
 */

import { useCallback, useEffect, useState } from "react";

type HealthEntry = {
  date: string;
  sleep_hours: number | null;
  steps: number | null;
  resting_hr: number | null;
  hrv_ms: number | null;
  workout_minutes: number | null;
  energy_self: number | null;
  note?: string;
  received_at?: string;
};

type Recent = { days: number; items: HealthEntry[] };
type Hint = { hint: string; energy_band: string };

// ドメインは 1 つに寄せる (Vercel の rewrite 経由で Railway に届く)。
const QUICK_URL = "https://koach-os.vercel.app/api/health-data/quick";
const AUTO_EXPORT_URL = "https://koach-os.vercel.app/api/health-data/auto-export";

function bandColor(band: string): string {
  return band === "low" ? "#ef4444" : band === "high" ? "#10b981" : "var(--color-text-muted)";
}

function bandLabel(band: string): string {
  return band === "low" ? "低め" : band === "high" ? "高め" : band === "neutral" ? "ふつう" : "—";
}

function fmt(n: number | null | undefined, digits = 0): string {
  if (n === null || n === undefined) return "—";
  return digits > 0 ? n.toFixed(digits) : String(n);
}

function weekday(dateStr: string): string {
  // dateStr は YYYY-MM-DD。曜日をローカル計算 (UTC 正午で日付ズレ回避)。
  try {
    const d = new Date(`${dateStr}T12:00:00+09:00`);
    return ["日", "月", "火", "水", "木", "金", "土"][d.getDay()];
  } catch {
    return "";
  }
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div
      className="rounded-2xl p-4 flex flex-col gap-1"
      style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
    >
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </span>
      <span className="text-2xl font-semibold tabular-nums">{value}</span>
      {sub && (
        <span className="text-[11px]" style={{ color: "var(--color-text-muted)" }}>
          {sub}
        </span>
      )}
    </div>
  );
}

export default function HealthPage() {
  const [hint, setHint] = useState<Hint | null>(null);
  const [recent, setRecent] = useState<Recent | null>(null);
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(true);

  // 手入力 (任意・保険)
  const [showForm, setShowForm] = useState(false);
  const [sleep, setSleep] = useState("");
  const [steps, setSteps] = useState("");
  const [hr, setHr] = useState("");
  const [energy, setEnergy] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // iPhone 側の設定手順 (初回だけ開く)
  const [showSetup, setShowSetup] = useState(false);
  const [copied, setCopied] = useState("");

  const copy = (text: string, key: string) => {
    navigator.clipboard?.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(""), 2000);
  };

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      fetch("/api/health-data/state-hint")
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null),
      fetch(`/api/health-data/recent?days=${days}`)
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null),
    ])
      .then(([h, rec]) => {
        setHint(h);
        setRecent(rec);
      })
      .finally(() => setLoading(false));
  }, [days]);

  useEffect(() => {
    load();
  }, [load]);

  async function submit() {
    const body: Record<string, number> = {};
    if (sleep.trim() !== "") body.sleep_hours = parseFloat(sleep);
    if (steps.trim() !== "") body.steps = parseInt(steps, 10);
    if (hr.trim() !== "") body.resting_hr = parseInt(hr, 10);
    if (energy.trim() !== "") body.energy_self = parseInt(energy, 10);
    if (Object.keys(body).length === 0) return;
    setSaving(true);
    setSaved(false);
    try {
      const r = await fetch("/api/health-data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (r.ok) {
        setSaved(true);
        setSleep("");
        setSteps("");
        setHr("");
        setEnergy("");
        load();
        setTimeout(() => setSaved(false), 2500);
      }
    } finally {
      setSaving(false);
    }
  }

  // 新しい日を上に。中身が空の日 (送信だけされて数値ゼロ件) は並べない。
  const items = recent?.items
    ? [...recent.items]
        .filter(
          (e) =>
            e.sleep_hours != null ||
            e.steps != null ||
            e.resting_hr != null ||
            e.hrv_ms != null ||
            e.workout_minutes != null ||
            e.energy_self != null,
        )
        .reverse()
    : [];
  const today = items[0];
  const hasToday =
    today &&
    today.date === (recent?.items.slice(-1)[0]?.date ?? "") &&
    (today.sleep_hours != null || today.steps != null || today.energy_self != null);

  return (
    // AppShell が本文を overflow-hidden で包むので、各ページが自前でスクロール領域を持つ。
    // これが無いと画面下が切れてスクロールできない (iPhone で手順が読めない不具合)。
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-5 py-8 pb-16 space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <span>❤️</span> 健康・コンディション
        </h1>
        <p className="text-sm leading-relaxed" style={{ color: "var(--color-text-muted)" }}>
          Apple Watch / Health の睡眠・歩数・心拍を眺める画面です。データは iPhone のショートカットが毎朝自動で送ります。
          ここは基本「見るだけ」。疲れている日は Daily / Evening のトーンが自動でやわらぎます。
        </p>
      </header>

      {/* 今日のコンディション */}
      <section
        className="rounded-3xl p-5 space-y-3"
        style={{ background: "var(--color-surface-hover)", border: "1px solid var(--color-border)" }}
      >
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold" style={{ color: "var(--color-text-muted)" }}>
            今日のコンディション
          </span>
          {hint && (
            <span
              className="text-xs font-semibold rounded-full px-3 py-1"
              style={{ color: "#fff", background: bandColor(hint.energy_band) }}
            >
              エネルギー {bandLabel(hint.energy_band)}
            </span>
          )}
        </div>
        {hint?.hint ? (
          <p className="text-base leading-relaxed" style={{ color: bandColor(hint.energy_band) }}>
            📊 {hint.hint}
          </p>
        ) : (
          <p className="text-sm leading-relaxed" style={{ color: "var(--color-text-muted)" }}>
            今日のデータはまだありません。iPhone のショートカット (毎朝の自動送信) を仕込むと、開くだけでここに出ます。
            今すぐ試すなら下の「手で入れる」から。
          </p>
        )}
      </section>

      {/* 期間切り替え */}
      <div className="flex gap-1.5">
        {[7, 14, 30].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className="text-xs rounded-full px-3 py-1"
            style={{
              background: days === d ? "var(--color-accent)" : "var(--color-surface)",
              color: days === d ? "#fff" : "var(--color-text-muted)",
              border: "1px solid var(--color-border)",
            }}
          >
            {d}日
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          読み込み中...
        </p>
      ) : items.length === 0 ? (
        <div
          className="rounded-2xl p-5 text-sm leading-relaxed"
          style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}
        >
          まだ記録がありません。iPhone 側の自動送信を仕込むか、下の「手で入れる」で 1 件入れてみてください。
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((e) => (
            <div
              key={e.date}
              className="rounded-2xl px-4 py-3 flex items-center gap-4 flex-wrap"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            >
              <span className="text-sm font-semibold tabular-nums" style={{ minWidth: "92px" }}>
                {e.date.slice(5)} ({weekday(e.date)})
              </span>
              <span className="text-sm tabular-nums" style={{ color: "var(--color-text-muted)" }}>
                😴 {fmt(e.sleep_hours, 1)}h
              </span>
              <span className="text-sm tabular-nums" style={{ color: "var(--color-text-muted)" }}>
                👟 {e.steps != null ? e.steps.toLocaleString() : "—"}
              </span>
              <span className="text-sm tabular-nums" style={{ color: "var(--color-text-muted)" }}>
                💓 {fmt(e.resting_hr)}
              </span>
              {e.workout_minutes != null && e.workout_minutes > 0 && (
                <span className="text-sm tabular-nums" style={{ color: "var(--color-text-muted)" }}>
                  🏃 {e.workout_minutes}分
                </span>
              )}
              {e.energy_self != null && (
                <span className="text-sm tabular-nums" style={{ color: "var(--color-text-muted)" }}>
                  ⚡ {e.energy_self}/5
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* まとめ (期間の平均) */}
      {items.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {(() => {
            const avg = (key: keyof HealthEntry, digits = 0) => {
              const vals = items.map((e) => e[key]).filter((v): v is number => typeof v === "number");
              if (vals.length === 0) return "—";
              const m = vals.reduce((a, b) => a + b, 0) / vals.length;
              return digits > 0 ? m.toFixed(digits) : String(Math.round(m));
            };
            return (
              <>
                <Stat label={`平均睡眠 (${days}日)`} value={`${avg("sleep_hours", 1)}h`} />
                <Stat label={`平均歩数 (${days}日)`} value={avg("steps")} />
                <Stat label={`平均安静時心拍 (${days}日)`} value={avg("resting_hr")} />
              </>
            );
          })()}
        </div>
      )}

      {/* iPhone 側の設定 (初回1回だけ) */}
      <section className="pt-2">
        <button
          onClick={() => setShowSetup((v) => !v)}
          className="text-xs rounded-full px-3 py-1.5"
          style={{ background: "var(--color-surface)", color: "var(--color-text-muted)", border: "1px solid var(--color-border)" }}
        >
          {showSetup ? "設定手順を閉じる" : "📱 iPhone から自動で送る設定 (初回だけ)"}
        </button>
        {showSetup && (
          <div
            className="mt-3 rounded-2xl p-4 space-y-4 text-sm leading-relaxed"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
          >
            <p style={{ color: "var(--color-text-muted)" }}>
              一度だけ設定すれば、あとは毎朝勝手に送られます。日々の入力は不要です。
              ヘッダや JSON 本文の組み立ては要りません。URL に値を並べるだけで届きます。
            </p>

            <div className="space-y-2">
              <span className="text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>
                送信先 URL (ショートカットに貼る)
              </span>
              <div className="flex items-center gap-2 flex-wrap">
                <code
                  className="text-xs rounded-lg px-3 py-2 break-all"
                  style={{ background: "var(--color-surface-hover)", border: "1px solid var(--color-border)" }}
                >
                  {QUICK_URL}?steps=
                </code>
                <button
                  onClick={() => copy(`${QUICK_URL}?steps=`, "quick")}
                  className="text-xs rounded-lg px-3 py-2"
                  style={{ background: "var(--color-accent)", color: "#fff" }}
                >
                  {copied === "quick" ? "コピーしました" : "コピー"}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <span className="text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>
                手順 (ショートカット App) — まず歩数だけの 2 アクション
              </span>
              <ol className="space-y-1.5 list-decimal pl-5" style={{ color: "var(--color-text-muted)" }}>
                <li>「ショートカット」App → 新規作成</li>
                <li>
                  <b>ヘルスサンプルを検索</b> → 種類「歩数」、期間「今日」、まとめ方「合計」
                </li>
                <li>
                  <b>URL の内容を取得</b> → URL 欄に上の URL を貼り、<b>末尾に手順 2 の結果</b>{" "}
                  (青い変数) をドラッグして置く。方法は <b>GET</b> のまま、ヘッダも本文も触りません
                </li>
                <li>
                  「オートメーション」タブ → <b>時刻</b> 毎日 7:00 → このショートカットを実行 →
                  「実行前に尋ねる」を <b>オフ</b>
                </li>
              </ol>
            </div>

            <div className="space-y-2">
              <span className="text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>
                睡眠も足すとき (アクションを 1 つ増やすだけ)
              </span>
              <p className="text-xs leading-relaxed" style={{ color: "var(--color-text-muted)" }}>
                <b>ヘルスサンプルを検索</b> → 種類「睡眠」、期間「今日」を足して、URL を{" "}
                <code className="text-[11px] break-all">?steps=〈歩数〉&amp;sleep_seconds=〈睡眠〉</code>{" "}
                にします。睡眠は秒で返りますが、そのまま渡せば時間に直して保存します
                (分なら <code className="text-[11px]">sleep_minutes</code>)。÷3600 の計算アクションは要りません。
              </p>
            </div>

            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              使える項目: steps / sleep_seconds (または sleep_minutes・sleep_hours) / resting_hr / hrv_ms /
              workout_minutes / energy_self (1〜5)。すべて任意なので、まず歩数だけで動かして、あとから足すのが楽です。
              日付は送らなければ「今日」になります。
            </p>

            <div className="space-y-2 pt-1" style={{ borderTop: "1px solid var(--color-border)" }}>
              <span className="text-xs font-semibold pt-2 block" style={{ color: "var(--color-text-muted)" }}>
                ショートカットを作りたくない場合
              </span>
              <p className="text-xs leading-relaxed" style={{ color: "var(--color-text-muted)" }}>
                「Health Auto Export」アプリの送信先 (REST API) に下の URL を入れるだけでも届きます。
                向こうの形式のまま受けて 1 日 1 行に畳みます。
              </p>
              <div className="flex items-center gap-2 flex-wrap">
                <code
                  className="text-xs rounded-lg px-3 py-2 break-all"
                  style={{ background: "var(--color-surface-hover)", border: "1px solid var(--color-border)" }}
                >
                  {AUTO_EXPORT_URL}
                </code>
                <button
                  onClick={() => copy(AUTO_EXPORT_URL, "hae")}
                  className="text-xs rounded-lg px-3 py-2"
                  style={{ background: "var(--color-surface-hover)", color: "var(--color-text)", border: "1px solid var(--color-border)" }}
                >
                  {copied === "hae" ? "コピーしました" : "コピー"}
                </button>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* 手入力 (任意・保険) */}
      <section className="pt-2">
        <button
          onClick={() => setShowForm((v) => !v)}
          className="text-xs rounded-full px-3 py-1.5"
          style={{ background: "var(--color-surface)", color: "var(--color-text-muted)", border: "1px solid var(--color-border)" }}
        >
          {showForm ? "手入力を閉じる" : "＋ 手で入れる (任意)"}
        </button>
        {showForm && (
          <div
            className="mt-3 rounded-2xl p-4 space-y-3"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
          >
            <p className="text-xs leading-relaxed" style={{ color: "var(--color-text-muted)" }}>
              自動送信が回れば普段は不要です。Health アプリを見ながら、入れたい欄だけ埋めてください (空欄はスキップ)。今日として保存されます。
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: "睡眠 (h)", val: sleep, set: setSleep, ph: "6.5", step: "0.1" },
                { label: "歩数", val: steps, set: setSteps, ph: "8000", step: "1" },
                { label: "安静時心拍", val: hr, set: setHr, ph: "60", step: "1" },
                { label: "エネルギー 1-5", val: energy, set: setEnergy, ph: "3", step: "1" },
              ].map((f) => (
                <label key={f.label} className="flex flex-col gap-1">
                  <span className="text-[11px]" style={{ color: "var(--color-text-muted)" }}>
                    {f.label}
                  </span>
                  <input
                    type="number"
                    inputMode="decimal"
                    step={f.step}
                    placeholder={f.ph}
                    value={f.val}
                    onChange={(ev) => f.set(ev.target.value)}
                    className="rounded-lg px-3 py-2 text-sm tabular-nums"
                    style={{ background: "var(--color-surface-hover)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
                  />
                </label>
              ))}
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={submit}
                disabled={saving}
                className="text-sm rounded-lg px-4 py-2 font-semibold"
                style={{ background: "var(--color-accent)", color: "#fff", opacity: saving ? 0.6 : 1 }}
              >
                {saving ? "保存中..." : "保存"}
              </button>
              {saved && (
                <span className="text-xs" style={{ color: "#10b981" }}>
                  保存しました
                </span>
              )}
            </div>
          </div>
        )}
        </section>
      </div>
    </div>
  );
}
