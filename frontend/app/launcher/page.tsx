"use client";

import { useEffect, useMemo, useState } from "react";

type AiService = {
  id: string;
  name: string;
  url: string;
  emoji: string;
  category: string;
  color: string;
  note: string;
  pinned?: boolean;
  opened_count?: number;
  last_opened?: string | null;
};

const CAT_META: Record<string, { label: string; emoji: string }> = {
  chat: { label: "Chat", emoji: "💬" },
  code: { label: "Code", emoji: "⌨️" },
  research: { label: "Research", emoji: "🔍" },
  writing: { label: "Writing", emoji: "✍️" },
  creative: { label: "Creative", emoji: "🎨" },
  studio: { label: "Studio", emoji: "🛠" },
  other: { label: "Other", emoji: "📌" },
};

export default function LauncherPage() {
  const [services, setServices] = useState<AiService[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<AiService | null>(null);
  const [adding, setAdding] = useState(false);
  const [sortMode, setSortMode] = useState<"category" | "frequency">("category");

  const load = () => {
    setLoading(true);
    fetch("/api/ai-services")
      .then((r) => r.json())
      .then((d) => setServices(d.services ?? []))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const open = async (svc: AiService) => {
    // 名前付きウィンドウで開くと、2回目以降は同じ窓に refocus される (タブ乱立防止)
    const target = `koach-ai-${svc.id}`;
    const feat = "popup,width=1100,height=900,scrollbars=yes,resizable=yes";
    const w = window.open(svc.url, target, feat);
    if (!w || w.closed) {
      // popup ブロックされた場合は新タブで開く
      window.open(svc.url, "_blank");
    } else {
      w.focus();
    }
    // 利用記録
    fetch(`/api/ai-services/${svc.id}/opened`, { method: "POST" })
      .then((r) => r.ok ? r.json() : null)
      .then((updated) => {
        if (updated) {
          setServices((prev) => prev.map((s) => (s.id === svc.id ? { ...s, ...updated } : s)));
        }
      })
      .catch(() => {});
  };

  const save = async (svc: AiService) => {
    if (adding) {
      await fetch("/api/ai-services", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(svc),
      });
    } else {
      await fetch(`/api/ai-services/${svc.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: svc.name,
          url: svc.url,
          emoji: svc.emoji,
          category: svc.category,
          color: svc.color,
          note: svc.note,
          pinned: svc.pinned,
        }),
      });
    }
    setEditing(null);
    setAdding(false);
    load();
  };

  const remove = async (id: string) => {
    if (!confirm(`「${id}」を削除しますか?`)) return;
    await fetch(`/api/ai-services/${id}`, { method: "DELETE" });
    load();
  };

  const togglePin = async (svc: AiService) => {
    await fetch(`/api/ai-services/${svc.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pinned: !svc.pinned }),
    });
    load();
  };

  const groups = useMemo(() => {
    if (sortMode === "frequency") {
      const sorted = [...services].sort((a, b) => {
        if (!!b.pinned !== !!a.pinned) return b.pinned ? 1 : -1;
        const ac = a.opened_count ?? 0;
        const bc = b.opened_count ?? 0;
        if (bc !== ac) return bc - ac;
        return (b.last_opened ?? "").localeCompare(a.last_opened ?? "");
      });
      return [{ category: "all", items: sorted }];
    }
    const map = new Map<string, AiService[]>();
    for (const s of services) {
      const cat = s.category || "other";
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(s);
    }
    const order = ["chat", "code", "research", "writing", "creative", "studio", "other"];
    return order
      .filter((c) => map.has(c))
      .map((c) => ({
        category: c,
        items: map.get(c)!.sort((a, b) => {
          if (!!b.pinned !== !!a.pinned) return b.pinned ? 1 : -1;
          return a.name.localeCompare(b.name);
        }),
      }));
  }, [services, sortMode]);

  return (
    <div className="flex-1 overflow-y-auto">
      <div
        className="px-8 pt-12 pb-8"
        style={{
          background:
            "radial-gradient(ellipse at top left, rgba(59, 130, 246, 0.12), transparent 60%), radial-gradient(ellipse at top right, rgba(244, 114, 182, 0.08), transparent 50%)",
        }}
      >
        <div className="max-w-5xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            AI Launcher
          </p>
          <h1 className="text-4xl font-bold tracking-tight">使う AI を 1 タップで</h1>
          <p className="mt-3 text-sm" style={{ color: "var(--color-text-muted)" }}>
            各サービスは専用ウィンドウで開きます (ログイン保持・タブ乱立なし)。本家がアップデートされれば次に開いた時に自動で最新版。
          </p>
          <div className="mt-5 flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setSortMode("category")}
              className="px-3 py-1.5 rounded-full text-xs"
              style={{
                background: sortMode === "category" ? "var(--color-text)" : "transparent",
                color: sortMode === "category" ? "var(--color-background)" : "var(--color-text-muted)",
                border: "1px solid var(--color-border)",
              }}
            >
              カテゴリ順
            </button>
            <button
              onClick={() => setSortMode("frequency")}
              className="px-3 py-1.5 rounded-full text-xs"
              style={{
                background: sortMode === "frequency" ? "var(--color-text)" : "transparent",
                color: sortMode === "frequency" ? "var(--color-background)" : "var(--color-text-muted)",
                border: "1px solid var(--color-border)",
              }}
            >
              よく使う順
            </button>
            <button
              onClick={() => {
                setAdding(true);
                setEditing({ id: "", name: "", url: "", emoji: "🤖", category: "chat", color: "#71717a", note: "" });
              }}
              className="ml-auto px-4 py-1.5 rounded-full text-xs"
              style={{ background: "var(--color-accent)", color: "white" }}
            >
              + サービス追加
            </button>
          </div>
        </div>
      </div>

      <div className="px-8 pb-16">
        <div className="max-w-5xl mx-auto space-y-8">
          {loading && <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>読み込み中...</p>}

          {!loading &&
            groups.map((g) => (
              <section key={g.category}>
                {sortMode === "category" && (
                  <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
                    <span>{CAT_META[g.category]?.emoji ?? "•"}</span>
                    <span>{CAT_META[g.category]?.label ?? g.category}</span>
                  </h2>
                )}
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {g.items.map((svc) => (
                    <div
                      key={svc.id}
                      className="rounded-2xl p-4 group relative transition-all hover:scale-[1.02] cursor-pointer"
                      style={{
                        background: "var(--color-surface)",
                        border: "1px solid var(--color-border)",
                        borderLeft: `3px solid ${svc.color}`,
                      }}
                      onClick={() => open(svc)}
                    >
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <span className="text-2xl">{svc.emoji}</span>
                        <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              togglePin(svc);
                            }}
                            title={svc.pinned ? "ピン解除" : "ピン留め"}
                            className="text-[10px] px-1.5 py-0.5 rounded"
                            style={{
                              background: svc.pinned ? "rgba(245, 158, 11, 0.2)" : "var(--color-surface-hover)",
                              color: svc.pinned ? "#f59e0b" : "var(--color-text-muted)",
                            }}
                          >
                            📌
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditing(svc);
                              setAdding(false);
                            }}
                            className="text-[10px] px-1.5 py-0.5 rounded"
                            style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}
                          >
                            ✎
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              remove(svc.id);
                            }}
                            className="text-[10px] px-1.5 py-0.5 rounded"
                            style={{ background: "rgba(239, 68, 68, 0.1)", color: "#ef4444" }}
                          >
                            ×
                          </button>
                        </div>
                      </div>
                      <div className="font-semibold text-sm">{svc.name}</div>
                      {svc.note && (
                        <div className="text-[11px] mt-1" style={{ color: "var(--color-text-muted)" }}>
                          {svc.note}
                        </div>
                      )}
                      <div className="text-[10px] mt-2 font-mono" style={{ color: "var(--color-text-muted)" }}>
                        {svc.opened_count ? `${svc.opened_count} 回 / ${(svc.last_opened ?? "").slice(5, 10)}` : "未利用"}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ))}

          <div
            className="rounded-2xl p-5 text-xs space-y-2"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}
          >
            <div className="font-semibold" style={{ color: "var(--color-text)" }}>
              💡 タブ乱立を本格的に解消するなら
            </div>
            <p>
              Chrome / Edge で各サービスを <strong>PWA としてインストール</strong> すると Dock アイコン化され、専用ウィンドウとして OS 管理になります:
            </p>
            <ol className="list-decimal list-inside space-y-0.5">
              <li>Chrome で対象サービスを開く (例: chatgpt.com)</li>
              <li>アドレスバー右のインストールアイコン or ⋮ → 「アプリとしてインストール」</li>
              <li>Dock 常駐 → このランチャーから開いてもブラウザではなく PWA 窓に refocus</li>
            </ol>
          </div>
        </div>
      </div>

      {editing && (
        <Editor
          svc={editing}
          isNew={adding}
          onClose={() => {
            setEditing(null);
            setAdding(false);
          }}
          onSave={save}
        />
      )}
    </div>
  );
}

function Editor({
  svc,
  isNew,
  onClose,
  onSave,
}: {
  svc: AiService;
  isNew: boolean;
  onClose: () => void;
  onSave: (s: AiService) => void;
}) {
  const [s, setS] = useState(svc);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.6)" }} onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="rounded-2xl p-6 w-full max-w-md space-y-3"
        style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
      >
        <h3 className="font-semibold">{isNew ? "サービスを追加" : `${s.name} を編集`}</h3>
        <div className="grid grid-cols-3 gap-3">
          <Field label="ID" value={s.id} onChange={(v) => setS({ ...s, id: v })} disabled={!isNew} />
          <Field label="絵文字" value={s.emoji} onChange={(v) => setS({ ...s, emoji: v })} />
          <div>
            <label className="block text-[10px] mb-1 uppercase" style={{ color: "var(--color-text-muted)" }}>
              カテゴリ
            </label>
            <select
              value={s.category}
              onChange={(e) => setS({ ...s, category: e.target.value })}
              className="w-full px-3 py-2 rounded text-sm"
              style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
            >
              {Object.entries(CAT_META).map(([k, v]) => (
                <option key={k} value={k}>
                  {v.emoji} {v.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <Field label="名前" value={s.name} onChange={(v) => setS({ ...s, name: v })} />
        <Field label="URL" value={s.url} onChange={(v) => setS({ ...s, url: v })} />
        <Field label="メモ (任意)" value={s.note} onChange={(v) => setS({ ...s, note: v })} />
        <Field label="色 (#hex)" value={s.color} onChange={(v) => setS({ ...s, color: v })} />
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="px-4 py-2 rounded-full text-sm" style={{ color: "var(--color-text-muted)" }}>
            キャンセル
          </button>
          <button
            onClick={() => onSave(s)}
            disabled={!s.id || !s.name || !s.url}
            className="px-5 py-2 rounded-full text-sm font-medium disabled:opacity-50"
            style={{ background: "var(--color-accent)", color: "white" }}
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  return (
    <div>
      <label className="block text-[10px] mb-1 uppercase" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </label>
      <input
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 rounded text-sm disabled:opacity-50"
        style={{ background: "var(--color-background)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
      />
    </div>
  );
}
