"use client";

import { useEffect, useState } from "react";
import { useSession, signIn, signOut } from "next-auth/react";
import { PHASES } from "@/lib/training-data";
import { CATEGORIES } from "@/lib/categories";
import {
  loadSettings,
  saveSettings,
  getDefaultSettings,
  type AppSettings,
} from "@/lib/settings-storage";
import { setCurrentPhase } from "@/lib/training-storage";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  LogIn,
  LogOut,
  CheckCircle,
  RotateCcw,
  Save,
  Eye,
  EyeOff,
  X,
  Plus,
} from "lucide-react";

export default function SettingsPage() {
  const { data: session, status } = useSession();
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [showApiKey, setShowApiKey] = useState(false);
  const [newKeyword, setNewKeyword] = useState("");

  useEffect(() => {
    setSettings(loadSettings());
  }, []);

  if (!settings) return null;

  const handleSave = () => {
    saveSettings(settings);
    setCurrentPhase(settings.currentPhase);
    toast.success("設定を保存しました");
  };

  const handleReset = () => {
    const defaults = getDefaultSettings();
    setSettings(defaults);
    saveSettings(defaults);
    toast.info("設定をリセットしました");
  };

  const updateColor = (catId: string, color: string) => {
    setSettings({
      ...settings,
      categoryColors: { ...settings.categoryColors, [catId]: color },
    });
  };

  const addKeyword = () => {
    if (!newKeyword.trim()) return;
    if (settings.scanKeywords.includes(newKeyword.trim())) return;
    setSettings({
      ...settings,
      scanKeywords: [...settings.scanKeywords, newKeyword.trim()],
    });
    setNewKeyword("");
  };

  const removeKeyword = (kw: string) => {
    setSettings({
      ...settings,
      scanKeywords: settings.scanKeywords.filter((k) => k !== kw),
    });
  };

  return (
    <div className="min-h-screen px-4 py-6">
      <div className="mx-auto max-w-lg">
        <h1 className="mb-1 text-xl font-black">⚙️ 設定</h1>
        <p className="mb-5 text-xs text-muted-foreground">
          アカウント・API・表示のカスタマイズ
        </p>

        {/* Google Account */}
        <section className="mb-5">
          <h2 className="mb-2 text-sm font-bold">Google アカウント</h2>
          <div className="rounded-xl border border-border bg-card p-4">
            {status === "authenticated" && session?.user ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <CheckCircle className="h-5 w-5 text-[var(--color-cat-growth)]" />
                  <div>
                    <p className="text-xs font-bold">{session.user.name}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {session.user.email}
                    </p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => signOut()}
                  className="gap-1 text-xs text-muted-foreground"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  ログアウト
                </Button>
              </div>
            ) : (
              <Button
                variant="outline"
                className="w-full gap-2"
                onClick={() => signIn("google")}
              >
                <LogIn className="h-4 w-4" />
                Googleでログイン
              </Button>
            )}
            <p className="mt-2 text-[10px] text-muted-foreground">
              Calendar API + Gmail API のスコープで接続
            </p>
          </div>
        </section>

        <Separator className="mb-5" />

        {/* OpenAI API Key */}
        <section className="mb-5">
          <h2 className="mb-2 text-sm font-bold">OpenAI API Key</h2>
          <div className="rounded-xl border border-border bg-card p-4">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <input
                  type={showApiKey ? "text" : "password"}
                  value={settings.openaiApiKey}
                  onChange={(e) =>
                    setSettings({ ...settings, openaiApiKey: e.target.value })
                  }
                  placeholder="sk-proj-..."
                  className="w-full rounded-md border border-border bg-background px-3 py-2 pr-10 font-mono text-xs"
                />
                <button
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                >
                  {showApiKey ? (
                    <EyeOff className="h-3.5 w-3.5" />
                  ) : (
                    <Eye className="h-3.5 w-3.5" />
                  )}
                </button>
              </div>
            </div>
            <p className="mt-2 text-[10px] text-muted-foreground">
              文書インポート・メールスキャンの日程抽出に使用。サーバー側の環境変数が優先されます。
            </p>
          </div>
        </section>

        <Separator className="mb-5" />

        {/* Current Phase */}
        <section className="mb-5">
          <h2 className="mb-2 text-sm font-bold">トレーニング Phase</h2>
          <div className="rounded-xl border border-border bg-card p-4">
            <div className="grid grid-cols-2 gap-2">
              {PHASES.map((p) => (
                <button
                  key={p.id}
                  onClick={() =>
                    setSettings({ ...settings, currentPhase: p.id })
                  }
                  className="rounded-lg border-2 px-3 py-2.5 text-left transition-colors"
                  style={{
                    borderColor:
                      settings.currentPhase === p.id
                        ? p.color
                        : "var(--border)",
                    background:
                      settings.currentPhase === p.id
                        ? `${p.color}12`
                        : "transparent",
                  }}
                >
                  <p
                    className="text-xs font-bold"
                    style={{
                      color:
                        settings.currentPhase === p.id
                          ? p.color
                          : "var(--foreground)",
                    }}
                  >
                    Phase {p.id}
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    {p.title.replace(`Phase ${p.id}: `, "")}
                  </p>
                  <p className="mt-0.5 text-[9px] text-muted-foreground">
                    {p.weeks}
                  </p>
                </button>
              ))}
            </div>
          </div>
        </section>

        <Separator className="mb-5" />

        {/* Category colors */}
        <section className="mb-5">
          <h2 className="mb-2 text-sm font-bold">カテゴリ色</h2>
          <div className="rounded-xl border border-border bg-card p-4">
            <div className="space-y-2">
              {CATEGORIES.map((cat) => (
                <div
                  key={cat.id}
                  className="flex items-center gap-3"
                >
                  <input
                    type="color"
                    value={settings.categoryColors[cat.id] || cat.color}
                    onChange={(e) => updateColor(cat.id, e.target.value)}
                    className="h-7 w-7 cursor-pointer rounded border border-border bg-transparent"
                  />
                  <span className="flex-1 text-xs font-medium">
                    {cat.label}
                  </span>
                  <span className="font-mono text-[10px] text-muted-foreground">
                    {settings.categoryColors[cat.id] || cat.color}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <Separator className="mb-5" />

        {/* Scan keywords */}
        <section className="mb-5">
          <h2 className="mb-2 text-sm font-bold">メールスキャン キーワード</h2>
          <div className="rounded-xl border border-border bg-card p-4">
            <div className="mb-2 flex flex-wrap gap-1.5">
              {settings.scanKeywords.map((kw) => (
                <span
                  key={kw}
                  className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-2 py-1 text-[10px] font-medium"
                >
                  {kw}
                  <button
                    onClick={() => removeKeyword(kw)}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <X className="h-2.5 w-2.5" />
                  </button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={newKeyword}
                onChange={(e) => setNewKeyword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addKeyword()}
                placeholder="キーワード追加..."
                className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-xs"
              />
              <Button size="sm" variant="outline" onClick={addKeyword}>
                <Plus className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </section>

        <Separator className="mb-5" />

        {/* Reminder */}
        <section className="mb-5">
          <h2 className="mb-2 text-sm font-bold">リマインダー</h2>
          <div className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-center gap-3">
              <span className="text-xs">デフォルト通知</span>
              <select
                value={settings.reminderMinutes}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    reminderMinutes: Number(e.target.value),
                  })
                }
                className="rounded-md border border-border bg-background px-2 py-1.5 text-xs"
              >
                <option value={5}>5分前</option>
                <option value={10}>10分前</option>
                <option value={15}>15分前</option>
                <option value={30}>30分前</option>
                <option value={60}>1時間前</option>
                <option value={1440}>1日前</option>
              </select>
            </div>
          </div>
        </section>

        {/* Action buttons */}
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="flex-1 gap-1.5 text-xs"
            onClick={handleReset}
          >
            <RotateCcw className="h-3.5 w-3.5" />
            リセット
          </Button>
          <Button
            className="flex-1 gap-1.5 bg-[var(--color-cat-growth)] text-xs text-white hover:bg-[var(--color-cat-growth)]/80"
            onClick={handleSave}
          >
            <Save className="h-3.5 w-3.5" />
            保存
          </Button>
        </div>

        {/* App info */}
        <div className="mt-6 text-center text-[10px] text-muted-foreground">
          <p>Schedule Manager v1.0</p>
          <p className="mt-0.5">データ: localStorage（DB移行可能な設計）</p>
        </div>
      </div>
    </div>
  );
}
