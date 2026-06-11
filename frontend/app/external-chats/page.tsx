"use client";

import { useEffect, useRef, useState } from "react";

type ChatSummary = {
  id: string;
  provider: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  preview: string;
};

type Message = { role: string; content: string; ts?: string; _engine?: string; _model?: string };

type ChatDetail = {
  id: string;
  provider: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
};

const PROVIDER_LABEL: Record<string, string> = {
  chatgpt: "🤖 ChatGPT",
  claude: "🧠 Claude",
  gemini: "✨ Gemini",
  grok: "🛰 Grok",
};

export default function ExternalChatsPage() {
  const [list, setList] = useState<ChatSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [providerFilter, setProviderFilter] = useState<string>("");
  const [importProvider, setImportProvider] = useState<"chatgpt" | "claude">("chatgpt");
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ChatDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [followup, setFollowup] = useState("");
  const [followupEngine, setFollowupEngine] = useState<string>("claude");
  const [followupSending, setFollowupSending] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const loadList = () => {
    setLoading(true);
    fetch(`/api/external-chats${providerFilter ? `?provider=${providerFilter}` : ""}`)
      .then((r) => r.json())
      .then((d) => setList(d.items ?? []))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providerFilter]);

  const loadDetail = (id: string) => {
    setSelectedId(id);
    setDetail(null);
    setDetailLoading(true);
    fetch(`/api/external-chats/${id}`)
      .then((r) => r.json())
      .then((d) => setDetail(d))
      .finally(() => setDetailLoading(false));
  };

  const handleFile = async (file: File) => {
    setImporting(true);
    setImportResult(null);
    try {
      const text = await file.text();
      const r = await fetch(`/api/external-chats/import-${importProvider}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_json: text }),
      });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      setImportResult(`✓ ${importProvider} 取込: ${d.added} 件追加 / ${d.updated} 件更新 / 合計 ${d.total} 件`);
      loadList();
    } catch (e) {
      setImportResult(`✗ ${(e as Error).message}`);
    } finally {
      setImporting(false);
    }
  };

  const sendFollowup = async () => {
    if (!detail || !followup.trim()) return;
    setFollowupSending(true);
    try {
      const r = await fetch(`/api/external-chats/${detail.id}/continue`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_message: followup, engine: followupEngine, include_messages: 20 }),
      });
      if (!r.ok) throw new Error(await r.text());
      setFollowup("");
      loadDetail(detail.id);
    } catch (e) {
      alert(`送信失敗: ${(e as Error).message}`);
    } finally {
      setFollowupSending(false);
    }
  };

  const deleteChat = async (id: string) => {
    if (!confirm("この会話を削除しますか？")) return;
    await fetch(`/api/external-chats/${id}`, { method: "DELETE" });
    if (selectedId === id) {
      setSelectedId(null);
      setDetail(null);
    }
    loadList();
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div
        className="px-8 pt-12 pb-8"
        style={{
          background:
            "radial-gradient(ellipse at top left, rgba(99, 102, 241, 0.12), transparent 60%)",
        }}
      >
        <div className="max-w-6xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            External AI Chats
          </p>
          <h1 className="text-4xl font-bold tracking-tight">外部 AI チャット履歴</h1>
          <p className="mt-3 text-sm" style={{ color: "var(--color-text-muted)" }}>
            Claude.ai / ChatGPT などの export を取り込み、続き相談 + 横断検索の起点に。
          </p>

          <div className="mt-6 rounded-2xl p-4" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
            <p className="text-xs font-semibold mb-2">📥 Import (conversations.json)</p>
            <div className="flex items-center gap-2 flex-wrap">
              {(["chatgpt", "claude"] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setImportProvider(p)}
                  className="text-xs px-3 py-1.5 rounded-full"
                  style={{
                    background: importProvider === p ? "#6366f1" : "var(--color-surface-hover)",
                    color: importProvider === p ? "white" : "var(--color-text-muted)",
                  }}
                >
                  {PROVIDER_LABEL[p]}
                </button>
              ))}
              <input
                ref={fileInputRef}
                type="file"
                accept=".json,application/json"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleFile(f);
                }}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={importing}
                className="text-xs px-4 py-1.5 rounded-full disabled:opacity-50"
                style={{ background: "#6366f1", color: "white" }}
              >
                {importing ? "取込中..." : "JSON ファイルを選択"}
              </button>
              {importResult && (
                <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {importResult}
                </span>
              )}
            </div>
            <p className="mt-2 text-[11px]" style={{ color: "var(--color-text-muted)" }}>
              ChatGPT: Settings → Data Controls → Export data → メール届く zip 内の <code>conversations.json</code><br />
              Claude.ai: Settings → Privacy → Export data → zip 内の <code>conversations.json</code>
            </p>
          </div>

          <div className="mt-5 flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setProviderFilter("")}
              className="text-xs px-3 py-1 rounded-full"
              style={{ background: providerFilter === "" ? "#6366f1" : "var(--color-surface-hover)", color: providerFilter === "" ? "white" : "var(--color-text-muted)" }}
            >
              全て
            </button>
            {(["chatgpt", "claude", "gemini", "grok"] as const).map((p) => (
              <button
                key={p}
                onClick={() => setProviderFilter(p)}
                className="text-xs px-3 py-1 rounded-full"
                style={{
                  background: providerFilter === p ? "#6366f1" : "var(--color-surface-hover)",
                  color: providerFilter === p ? "white" : "var(--color-text-muted)",
                }}
              >
                {PROVIDER_LABEL[p]}
              </button>
            ))}
            <span className="ml-auto text-xs font-mono" style={{ color: "var(--color-text-muted)" }}>
              {list.length} 件
            </span>
          </div>
        </div>
      </div>

      <div className="px-8 pb-32">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-[1fr,1.4fr] gap-4">
          <div className="space-y-2">
            {loading && <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>読み込み中...</p>}
            {!loading && list.length === 0 && (
              <div className="rounded-2xl p-6 text-sm text-center" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text-muted)" }}>
                まだ取り込まれていません。上のセクションから JSON を import してください。
              </div>
            )}
            {list.map((c) => (
              <button
                key={c.id}
                onClick={() => loadDetail(c.id)}
                className="w-full text-left rounded-xl p-3"
                style={{
                  background: selectedId === c.id ? "var(--color-surface-hover)" : "var(--color-surface)",
                  border: `1px solid ${selectedId === c.id ? "#6366f1" : "var(--color-border)"}`,
                }}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs">{PROVIDER_LABEL[c.provider] ?? c.provider}</span>
                  <span className="text-xs ml-auto" style={{ color: "var(--color-text-muted)" }}>
                    {c.message_count} msg
                  </span>
                </div>
                <p className="text-sm font-semibold truncate">{c.title}</p>
                <p className="text-xs mt-1 line-clamp-2" style={{ color: "var(--color-text-muted)" }}>
                  {c.preview}
                </p>
                <p className="text-[10px] mt-1 font-mono" style={{ color: "var(--color-text-muted)" }}>
                  {(c.updated_at || c.created_at || "").slice(0, 10)}
                </p>
              </button>
            ))}
          </div>

          <div className="rounded-2xl p-4 sticky top-4 self-start" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", maxHeight: "calc(100vh - 6rem)", overflowY: "auto" }}>
            {!detail && !detailLoading && (
              <p className="text-sm text-center py-12" style={{ color: "var(--color-text-muted)" }}>
                左から会話を選択
              </p>
            )}
            {detailLoading && <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>読み込み中...</p>}
            {detail && (
              <>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-semibold truncate flex-1">{detail.title}</h2>
                  <button
                    onClick={() => deleteChat(detail.id)}
                    className="text-xs ml-2"
                    style={{ color: "var(--color-text-muted)" }}
                  >
                    🗑
                  </button>
                </div>
                <div className="space-y-3 mb-4">
                  {detail.messages.map((m, i) => (
                    <div
                      key={i}
                      className="rounded-lg p-3 text-sm whitespace-pre-wrap"
                      style={{
                        background: m.role === "user" ? "var(--color-surface-hover)" : "transparent",
                        border: m.role === "assistant" ? "1px solid var(--color-border)" : "none",
                      }}
                    >
                      <p className="text-[10px] font-mono mb-1" style={{ color: "var(--color-text-muted)" }}>
                        {m.role === "user" ? "▶ あなた" : "◀ AI"} {m._engine ? `· ${m._engine}` : ""}
                      </p>
                      {m.content}
                    </div>
                  ))}
                </div>

                <div className="mt-4 border-t pt-3" style={{ borderColor: "var(--color-border)" }}>
                  <p className="text-xs mb-2" style={{ color: "var(--color-text-muted)" }}>
                    💬 続き相談 (直近 20 msg を context に)
                  </p>
                  <textarea
                    value={followup}
                    onChange={(e) => setFollowup(e.target.value)}
                    placeholder="この会話の続きを聞く..."
                    className="w-full rounded-lg p-2 text-sm"
                    style={{ background: "var(--color-surface-hover)", border: "1px solid var(--color-border)", minHeight: 80 }}
                  />
                  <div className="mt-2 flex items-center gap-2">
                    <label className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                      返答エンジン:
                    </label>
                    {["claude", "gpt", "gemini"].map((en) => (
                      <button
                        key={en}
                        onClick={() => setFollowupEngine(en)}
                        className="text-xs px-2.5 py-1 rounded-full"
                        style={{
                          background: followupEngine === en ? "#6366f1" : "var(--color-surface-hover)",
                          color: followupEngine === en ? "white" : "var(--color-text-muted)",
                        }}
                      >
                        {en}
                      </button>
                    ))}
                    <button
                      onClick={sendFollowup}
                      disabled={followupSending || !followup.trim()}
                      className="ml-auto text-xs px-4 py-1.5 rounded-full disabled:opacity-50"
                      style={{ background: "#6366f1", color: "white" }}
                    >
                      {followupSending ? "送信中..." : "送信"}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
