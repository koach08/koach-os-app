"use client";

import Link from "next/link";
import { useState } from "react";

type Tab = "start" | "day" | "pages" | "trouble";

const PAGES: {
  group: string;
  items: { href: string; icon: string; name: string; one: string; when: string; tips?: string }[];
}[] = [
  {
    group: "毎日のリズム",
    items: [
      {
        href: "/daily",
        icon: "🌅",
        name: "Daily",
        one: "今日の予定 + Coach バックログ + 完了チェック + 音声捕捉 FAB",
        when: "朝起きて最初に開く",
        tips: "右下の 🎤 ボタンで音声 → AI が memo/backlog/decision/failure に自動分類。チェック ✓ で完了ログ。",
      },
      {
        href: "/evening",
        icon: "🌙",
        name: "Evening",
        one: "今日の完了 + 取りこぼし + 明日への繰越提案",
        when: "21 時以降、寝る前",
        tips: "今日の Calendar 予定でチェックが付かなかったものが「取りこぼし」として出ます。",
      },
      {
        href: "/focus",
        icon: "⏱",
        name: "Focus",
        one: "25 / 50 / 90 分の集中タイマー",
        when: "作業を始める時",
        tips: "終了するとカテゴリ別の時間が自動でログされ、週次レビューと「あなたのパターン」分析に効いてきます。",
      },
    ],
  },
  {
    group: "予定の管理",
    items: [
      {
        href: "/calendar",
        icon: "🗓",
        name: "Calendar",
        one: "Google Calendar の月グリッド (全 slot × 全 visible カレンダー横断)",
        when: "予定の閲覧・編集・削除",
        tips: "イベントクリック → 「編集」でタイトル / 日時 / 場所 / メモを直接書き換え。Google 本体に同期します。",
      },
      {
        href: "/coach",
        icon: "🧭",
        name: "Coach",
        one: "AI 週次プラン生成 + バックログ + 生活ブロック + あなたのパターン",
        when: "月曜朝 or 週末",
        tips: "「プラン生成」→「ブロックに変換」→「一括 Calendar 書き込み」の 3 ステップで 1 週間を Calendar に固定。",
      },
      {
        href: "/gmail-sync",
        icon: "📅",
        name: "予定を追加",
        one: "Gmail / PDF / Excel / 手動入力から Calendar に書き込み",
        when: "案内メール・時間割・スケジュール表が来た時",
        tips: "Excel は時間割 .xlsx 専用で RRULE 自動付与。PDF は Gemini multimodal で表組み・スキャンも読めます。",
      },
      {
        href: "/tasks",
        icon: "✅",
        name: "Tasks",
        one: "シンプルな ToDo 管理",
        when: "Coach バックログより軽い ToDo を分けたい時",
      },
      {
        href: "/documents",
        icon: "📄",
        name: "Docs→Tasks",
        one: "PDF を AI に読ませてタスク候補を抽出",
        when: "規程書 / 案内文書から ToDo を抜く時",
      },
    ],
  },
  {
    group: "AI を使い分ける",
    items: [
      {
        href: "/launcher",
        icon: "🚀",
        name: "AI ランチャー",
        one: "Claude / ChatGPT / Codex / Venice / Gemini / Grok / Perplexity / NotebookLM / AI Studio / Grammarly / Canva / Firefly を専用窓で起動",
        when: "AI を使いたい時はまずここから",
        tips: "同じサービスを 2 回押しても同じ窓に refocus されるのでタブ乱立ゼロ。Pro 課金のログイン状態はブラウザ Cookie で保持。",
      },
      {
        href: "/personas",
        icon: "🎭",
        name: "多視点で考える",
        one: "1 つの問いを 志柿本人 / 批判 / 外部識者 / 楽観 / 懐疑 に並列で投げる",
        when: "重要判断・バイアスを疑いたい時",
        tips: "「Style Profile を編集」で本人スタイルガイドを編集、「最近のログから学習」で memo/decision/private から本人特徴を自動追記。",
      },
      {
        href: "/dispatcher",
        icon: "📨",
        name: "AI 外注 (指示書)",
        one: "目的→推奨 AI サービス + そのままコピペで動くプロンプト",
        when: "「どの AI に頼めばいい?」と迷う時",
        tips: "出力された MD を全文コピーして Claude.ai 等にそのまま貼り付け。",
      },
      {
        href: "/extract",
        icon: "🎬",
        name: "動画→構造化",
        one: "動画 / 音声 / YouTube URL → Gemini で 決定 / タスク / メモ / イベント に自動振り分け",
        when: "講義録画・会議録音・YouTube リサーチを片付ける時",
        tips: "選んだ項目だけまとめて backlog / decision / memo / Calendar に投入。ChatGPT/Claude には動画そのものを投げられないので Gemini ならではの経路。",
      },
      {
        href: "/ask",
        icon: "🔎",
        name: "過去に聞く",
        one: "memo / decision / failure / private chat / backlog を横断検索 + 引用付き AI 回答",
        when: "「半年前の自分はどう決めたか」を引き出す時",
        tips: "初回は「再構築」ボタンで知識ベースを構築。新しいデータが増えたら再構築で反映。",
      },
      {
        href: "/private",
        icon: "🤫",
        name: "プライベート",
        one: "Venice (制約少なめ) でジャッジしない相談相手",
        when: "他の AI に聞きにくいこと・揺れている感情・グレーな話",
        tips: "ログは通常チャットと完全に分離されます。",
      },
    ],
  },
  {
    group: "捕捉・記録",
    items: [
      {
        href: "/memos",
        icon: "🪧",
        name: "Memos",
        one: "ふせん風メモ",
        when: "整形不要のメモを残したい時",
      },
      {
        href: "/share",
        icon: "📤",
        name: "Share",
        one: "iOS Safari「共有 → Koach OS」から memo / backlog に直接投入",
        when: "スマホで Web 見ながら片手で捕捉する時",
        tips: "iPhone でホーム画面に Koach OS を追加すると Share Sheet に出てきます。",
      },
      {
        href: "/training",
        icon: "💪",
        name: "Training",
        one: "ブレイクダンス・アクロバット練習ログ",
        when: "練習日に",
      },
    ],
  },
  {
    group: "振り返り・状態",
    items: [
      {
        href: "/review",
        icon: "📊",
        name: "Review (週)",
        one: "対話統計 + AI 週次レビュー (完了 / 集中 / 決定 / 失敗を統合)",
        when: "日曜夜",
      },
      {
        href: "/kpi",
        icon: "📈",
        name: "KPI",
        one: "EGAKU 登録者数 / 売上 / 資産など任意の数字を視界常駐",
        when: "気にしないと忘れる KPI を朝に見たい時",
        tips: "Daily Brief 上部にも mini 表示されます。",
      },
      {
        href: "/analyze",
        icon: "✍️",
        name: "Style",
        one: "自分の文章サンプルから文体プロファイル抽出",
        when: "Persona の Shigaki スタイル更新ソース",
      },
      {
        href: "/memory",
        icon: "🧠",
        name: "Memory",
        one: "ChromaDB ベクトルメモリ統計",
        when: "デバッグ用",
      },
      {
        href: "/logs",
        icon: "📋",
        name: "Logs",
        one: "全インタラクションログ",
        when: "デバッグ用",
      },
    ],
  },
  {
    group: "対話",
    items: [
      {
        href: "/",
        icon: "💬",
        name: "Chat",
        one: "通常チャット (Claude / GPT / Grok / Gemini / Venice / Perplexity / Groq 切替)",
        when: "汎用相談",
      },
      {
        href: "/settings",
        icon: "⚙️",
        name: "Settings",
        one: "設定",
        when: "",
      },
    ],
  },
];

export default function HelpPage() {
  const [tab, setTab] = useState<Tab>("start");

  return (
    <div className="flex-1 overflow-y-auto">
      <div
        className="px-8 pt-12 pb-8"
        style={{
          background:
            "radial-gradient(ellipse at top left, rgba(16, 185, 129, 0.12), transparent 60%), radial-gradient(ellipse at top right, rgba(59, 130, 246, 0.08), transparent 50%)",
        }}
      >
        <div className="max-w-5xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            Koach OS — 使い方ガイド
          </p>
          <h1 className="text-4xl font-bold tracking-tight">何ができるか / どう使うか</h1>
          <p className="mt-3 text-sm" style={{ color: "var(--color-text-muted)" }}>
            ページが多いので、目的別に整理しました。まず「クイックスタート」だけ読めば回ります。
          </p>
          <div className="mt-5 flex gap-2 flex-wrap">
            {[
              { id: "start", label: "🚦 クイックスタート" },
              { id: "day", label: "🕐 1 日の流れ" },
              { id: "pages", label: "🗂 全ページ" },
              { id: "trouble", label: "🔧 困った時" },
            ].map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id as Tab)}
                className="px-4 py-1.5 rounded-full text-xs"
                style={{
                  background: tab === t.id ? "var(--color-text)" : "transparent",
                  color: tab === t.id ? "var(--color-background)" : "var(--color-text-muted)",
                  border: "1px solid var(--color-border)",
                }}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-5xl mx-auto">
          {tab === "start" && <Start />}
          {tab === "day" && <Day />}
          {tab === "pages" && <Pages />}
          {tab === "trouble" && <Trouble />}
        </div>
      </div>
    </div>
  );
}

function Card({ children, color = "rgba(59, 130, 246, 0.05)" }: { children: React.ReactNode; color?: string }) {
  return (
    <div
      className="rounded-2xl p-6"
      style={{ background: color, border: "1px solid var(--color-border)" }}
    >
      {children}
    </div>
  );
}

function Step({ n, title, body }: { n: number; title: React.ReactNode; body: React.ReactNode }) {
  return (
    <div className="flex gap-4 items-start">
      <div
        className="shrink-0 w-8 h-8 rounded-full font-mono text-sm flex items-center justify-center"
        style={{ background: "var(--color-accent)", color: "white" }}
      >
        {n}
      </div>
      <div className="flex-1">
        <div className="font-semibold text-base mb-1">{title}</div>
        <div className="text-sm leading-relaxed" style={{ color: "var(--color-text-muted)" }}>
          {body}
        </div>
      </div>
    </div>
  );
}

function Start() {
  return (
    <div className="space-y-6">
      <Card>
        <h2 className="text-lg font-semibold mb-4">まず覚えるのは 3 つだけ</h2>
        <div className="space-y-5">
          <Step
            n={1}
            title={
              <>
                朝 <Link href="/daily" className="underline">🌅 Daily</Link> を開いて、今日の予定を確認 + Coach バックログから 1〜3 個チェックする
              </>
            }
            body={
              <>
                予定とバックログの隣に <strong>四角いチェックボックス</strong> があります。完了したら ✓ をタップ。これが完了ログになり、Evening / 週次レビュー / パターン分析の素材になります。
                <br />右下の <strong>🎤 ボタン</strong> で音声捕捉。話せば AI が memo / backlog / decision / failure に自動振り分けします。
              </>
            }
          />
          <Step
            n={2}
            title={
              <>
                AI を使う時は <Link href="/launcher" className="underline">🚀 AI ランチャー</Link> から開く
              </>
            }
            body={
              <>
                Claude / ChatGPT / Codex / Venice / Gemini / Grammarly / Firefly などを一覧から起動。<strong>専用ウィンドウで開く</strong>ので、同じサービスを 2 回押しても 1 つの窓に refocus されます。タブ乱立しません。Pro 課金のログインはブラウザ Cookie で持続。
              </>
            }
          />
          <Step
            n={3}
            title={
              <>
                夜 <Link href="/evening" className="underline">🌙 Evening</Link> を開いて、今日できたこと + 明日への繰越を確認する
              </>
            }
            body={
              <>「今日できたこと」「取りこぼした予定」「明日に繰越し候補」「明日の最大の山」が AI で出ます。1 分で読めます。</>
            }
          />
        </div>
      </Card>

      <Card color="rgba(124, 58, 237, 0.05)">
        <h2 className="text-lg font-semibold mb-3">余裕が出てきたら次の 4 つ</h2>
        <ul className="space-y-2 text-sm">
          <li>
            ⏱ <Link href="/focus" className="underline">Focus</Link> — 90 分タイマー終了で時間がカテゴリ別ログ化、週次レビューに効きます
          </li>
          <li>
            🎭 <Link href="/personas" className="underline">多視点で考える</Link> — 重要判断は本人 / 批判 / 外部識者 / 楽観 / 懐疑 に並列で意見を求める
          </li>
          <li>
            🎬 <Link href="/extract" className="underline">動画→構造化</Link> — 講義録画 / Zoom 録画から決定・タスクを自動抽出
          </li>
          <li>
            🔎 <Link href="/ask" className="underline">過去に聞く</Link> — 「半年前の自分はどう決めたか」を引用付きで引き出す
          </li>
        </ul>
      </Card>
    </div>
  );
}

function Day() {
  return (
    <div className="space-y-4">
      <Card>
        <h2 className="text-lg font-semibold mb-4">典型的な 1 日</h2>
        <div className="space-y-4 text-sm">
          <Row time="07:00" page="🌅 Daily" what="開いて AI Brief を読む。今日の予定 + Coach バックログを把握。" />
          <Row time="07:30" page="(Calendar 既存予定)" what="保育園送り。Daily の予定リストでチェック ✓。" />
          <Row time="09:00" page="⏱ Focus" what="50 分セッション開始。終了で時間自動ログ。" />
          <Row time="11:00" page="🚀 AI ランチャー" what="Claude / Codex などを起動して作業。タブ乱立せず。" />
          <Row time="12:00" page="🎤 音声捕捉" what="昼休みに思いついたアイデアを Daily 右下の 🎤 から投入。AI が memo/backlog に自動振分。" />
          <Row time="16:45" page="(Calendar 既存予定)" what="保育園迎え。" />
          <Row time="19:00" page="📨 AI 外注 (dispatcher)" what="夜の執筆タスクは「Claude.ai に貼り付けるプロンプト」を生成して、専用窓で実行。" />
          <Row time="21:30" page="🌙 Evening" what="今日できたこと + 明日への繰越を確認。1 分。" />
          <Row time="(週末)" page="🧭 Coach" what="AI 週次プラン生成 → ブロック化 → Calendar 一括書き込みで来週を固定。" />
          <Row time="(日曜夜)" page="📊 Review (週)" what="AI 週次レビューで「強み・注意点・来週の小さな実験」を受け取る。" />
        </div>
      </Card>
      <Card color="rgba(245, 158, 11, 0.05)">
        <h2 className="text-base font-semibold mb-2">📱 iPhone での使い方</h2>
        <ul className="text-sm space-y-1.5" style={{ color: "var(--color-text-muted)" }}>
          <li>• Safari で <code className="px-1 py-0.5 rounded font-mono text-[11px]" style={{ background: "var(--color-surface-hover)" }}>koach-os.vercel.app</code> 開く → 共有 → 「ホーム画面に追加」</li>
          <li>• Web ページを見ながら → 共有 → 「Koach OS」を選ぶと <Link href="/share" className="underline">/share</Link> 経由で memo / backlog に投入</li>
          <li>• マイク許可を 1 回しておけば、Daily の 🎤 で音声捕捉も使えます</li>
        </ul>
      </Card>
    </div>
  );
}

function Row({ time, page, what }: { time: string; page: string; what: string }) {
  return (
    <div className="flex gap-3 items-start">
      <span className="font-mono text-xs shrink-0 pt-0.5" style={{ color: "var(--color-text-muted)", minWidth: "3.5rem" }}>
        {time}
      </span>
      <span className="font-semibold text-xs shrink-0 pt-0.5" style={{ minWidth: "10rem" }}>
        {page}
      </span>
      <span className="flex-1">{what}</span>
    </div>
  );
}

function Pages() {
  return (
    <div className="space-y-6">
      {PAGES.map((g) => (
        <section key={g.group}>
          <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--color-text-muted)" }}>
            {g.group}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {g.items.map((it) => (
              <Link
                key={it.href}
                href={it.href}
                className="rounded-xl p-4 block hover:scale-[1.01] transition-all"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-lg">{it.icon}</span>
                  <span className="font-semibold text-sm">{it.name}</span>
                  <span className="text-[10px] font-mono ml-auto" style={{ color: "var(--color-text-muted)" }}>
                    {it.href}
                  </span>
                </div>
                <div className="text-xs" style={{ color: "var(--color-text)" }}>
                  {it.one}
                </div>
                {it.when && (
                  <div className="text-[11px] mt-1.5" style={{ color: "var(--color-text-muted)" }}>
                    使う時: {it.when}
                  </div>
                )}
                {it.tips && (
                  <div className="text-[11px] mt-1.5 pt-1.5" style={{ borderTop: "1px dashed var(--color-border)", color: "var(--color-text-muted)" }}>
                    💡 {it.tips}
                  </div>
                )}
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function Trouble() {
  return (
    <div className="space-y-4">
      <Card color="rgba(239, 68, 68, 0.05)">
        <h2 className="text-base font-semibold mb-2">Calendar が 500 / 予定が出ない</h2>
        <p className="text-sm mb-2" style={{ color: "var(--color-text-muted)" }}>
          Google OAuth トークンが 7 日で失効するためです。<Link href="/calendar" className="underline">/calendar</Link> 上にも警告バナーが出ます。復旧手順:
        </p>
        <pre className="text-xs p-3 rounded font-mono whitespace-pre-wrap" style={{ background: "var(--color-background)", color: "var(--color-text)" }}>
{`cd /tmp/koach-os-app
.venv/bin/python scripts/setup_gcal.py  # ブラウザでログイン
base64 -i token.json | tr -d '\\n' | pbcopy
# Railway → koach-os-api → backend → GOOGLE_TOKEN_JSON_B64 に貼り付け`}
        </pre>
      </Card>

      <Card>
        <h2 className="text-base font-semibold mb-2">新ページが 404 になる</h2>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Vercel と GitHub の auto-deploy が切れているため、コミット後に手動で本番反映が必要。
        </p>
        <pre className="text-xs p-3 rounded font-mono mt-2" style={{ background: "var(--color-background)", color: "var(--color-text)" }}>
{`cd /tmp/koach-os-app/frontend
vercel --prod --yes --scope koach08s-projects`}
        </pre>
      </Card>

      <Card>
        <h2 className="text-base font-semibold mb-2">音声捕捉が動かない</h2>
        <ul className="text-sm space-y-1" style={{ color: "var(--color-text-muted)" }}>
          <li>• HTTPS でないと動きません (koach-os.vercel.app は HTTPS なので OK)</li>
          <li>• 初回はブラウザがマイク許可を聞きます → 許可してください</li>
          <li>• iOS で動かない場合: 設定 → Safari → Koach OS → マイク を ON に</li>
        </ul>
      </Card>

      <Card>
        <h2 className="text-base font-semibold mb-2">過去に聞く (RAG) で「未構築」と出る</h2>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          初回はナレッジベース構築が必要。<Link href="/ask" className="underline">/ask</Link> ページの右上「再構築」ボタンを押してください (memo/decision/failure/private/backlog を全部 embedding 化、30 秒前後)。新しいデータを追加したら同じく再構築で反映。
        </p>
      </Card>

      <Card>
        <h2 className="text-base font-semibold mb-2">Persona の Shigaki スタイルを更新する</h2>
        <p className="text-sm mb-2" style={{ color: "var(--color-text-muted)" }}>
          <Link href="/personas" className="underline">/personas</Link> 上部の「Style Profile を編集」で直接編集できます。iCloud の <code className="px-1 font-mono text-[11px] rounded" style={{ background: "var(--color-surface-hover)" }}>koach_style_guide_v2.md</code> を一括で push する場合:
        </p>
        <pre className="text-xs p-3 rounded font-mono" style={{ background: "var(--color-background)", color: "var(--color-text)" }}>
{`/tmp/koach-os-app/scripts/push_style_guide.sh`}
        </pre>
        <p className="text-sm mt-2" style={{ color: "var(--color-text-muted)" }}>
          または「最近のログから学習 (追記)」ボタンで、直近の memo / decision / private chat から本人の文体傾向を自動抽出して style profile に追記。
        </p>
      </Card>

      <Card>
        <h2 className="text-base font-semibold mb-2">バックエンドが落ちた</h2>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Railway dashboard → <code className="px-1 font-mono text-[11px] rounded" style={{ background: "var(--color-surface-hover)" }}>koach-os-api</code> → backend service → Deployments で再デプロイ。または <code className="px-1 font-mono text-[11px] rounded" style={{ background: "var(--color-surface-hover)" }}>railway logs</code> で詳細確認。
        </p>
      </Card>
    </div>
  );
}
