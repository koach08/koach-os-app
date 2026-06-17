"use client";

import { useState } from "react";

type Author = { name: string };

type Paper = {
  source?: string;
  doi?: string;
  semantic_scholar_id?: string;
  openalex_id?: string;
  cinii_id?: string;
  title: string;
  title_ja?: string;
  abstract?: string;
  tldr?: string;
  authors?: Author[];
  year?: number;
  venue?: string;
  citation_count?: number;
  reference_count?: number;
  is_open_access?: boolean;
  pdf_url?: string;
  fields_of_study?: string[];
  sources?: string[];
  relevance?: number;
  recommendation_category?: string;
  reason_ja?: string;
};

type SearchRes = { ok: boolean; results: Paper[]; total: number; errors?: string[] };

type AdviseRes = {
  ok: boolean;
  analysis: { research_summary?: string; key_concepts?: string[]; expected_fields?: string[]; advice?: string };
  categories: { id: string; label: string; description: string; papers: Paper[] }[];
  search_queries: { query: string; category: string; purpose: string }[];
  next_research_directions: { title: string; description: string; rationale: string; difficulty: string }[];
  development_possibilities: { direction: string; description: string; potential_impact: string }[];
};

const SOURCE_LABEL: Record<string, string> = {
  semantic_scholar: "S2",
  openalex: "OA",
  cinii: "CiNii",
};

function PaperCard({ p, onSave }: { p: Paper; onSave: (p: Paper) => void }) {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const handleSave = async () => {
    setSaving(true);
    await onSave(p);
    setSaved(true);
    setSaving(false);
  };
  return (
    <div className="rounded-xl p-3" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
      <div className="flex items-start gap-2 mb-1">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold">{p.title}</p>
          {p.title_ja && p.title_ja !== p.title && (
            <p className="text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>
              {p.title_ja}
            </p>
          )}
        </div>
        {typeof p.relevance === "number" && (
          <span
            className="text-[10px] font-mono px-1.5 py-0.5 rounded"
            style={{
              background: p.recommendation_category === "must_read" ? "#ef4444" : p.recommendation_category === "recommended" ? "#f59e0b" : "var(--color-surface-hover)",
              color: p.recommendation_category === "related" ? "var(--color-text-muted)" : "white",
            }}
          >
            {p.relevance}
          </span>
        )}
      </div>
      <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
        {(p.authors || []).slice(0, 3).map((a) => a.name).join(", ")}
        {p.authors && p.authors.length > 3 ? ` 他 ${p.authors.length - 3} 名` : ""}
        {p.year ? ` · ${p.year}` : ""}
        {p.venue ? ` · ${p.venue.slice(0, 40)}` : ""}
        {typeof p.citation_count === "number" ? ` · cited ${p.citation_count}` : ""}
      </p>
      {p.tldr && (
        <p className="text-xs mt-1.5 italic" style={{ color: "var(--color-text-muted)" }}>
          TL;DR: {p.tldr}
        </p>
      )}
      {p.reason_ja && (
        <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
          理由: {p.reason_ja}
        </p>
      )}
      {p.abstract && (
        <details className="mt-2">
          <summary className="text-xs cursor-pointer" style={{ color: "var(--color-text-muted)" }}>
            Abstract
          </summary>
          <p className="text-xs mt-1 whitespace-pre-wrap" style={{ color: "var(--color-text-muted)" }}>
            {p.abstract}
          </p>
        </details>
      )}
      <div className="mt-2 flex items-center gap-1.5 flex-wrap">
        {(p.sources || (p.source ? [p.source] : [])).map((s) => (
          <span key={s} className="text-[10px] font-mono px-1.5 py-0.5 rounded" style={{ background: "var(--color-surface-hover)" }}>
            {SOURCE_LABEL[s] || s}
          </span>
        ))}
        {p.is_open_access && (
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded" style={{ background: "rgba(16, 185, 129, 0.15)", color: "#10b981" }}>
            OA
          </span>
        )}
        {p.doi && (
          <a href={`https://doi.org/${p.doi}`} target="_blank" rel="noreferrer" className="text-xs px-2 py-0.5 rounded" style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}>
            DOI
          </a>
        )}
        {p.pdf_url && (
          <a href={p.pdf_url} target="_blank" rel="noreferrer" className="text-xs px-2 py-0.5 rounded" style={{ background: "var(--color-surface-hover)", color: "var(--color-text-muted)" }}>
            PDF
          </a>
        )}
        <button
          onClick={handleSave}
          disabled={saving || saved}
          className="ml-auto text-xs px-2 py-0.5 rounded disabled:opacity-50"
          style={{ background: saved ? "#10b981" : "var(--color-surface-hover)", color: saved ? "white" : "var(--color-text-muted)" }}
        >
          {saved ? "✓ memo 化済み" : saving ? "保存中..." : "📝 memo に保存"}
        </button>
      </div>
    </div>
  );
}

export default function ResearchPage() {
  const [tab, setTab] = useState<"search" | "advise">("search");

  // search
  const [query, setQuery] = useState("");
  const [yearFrom, setYearFrom] = useState<string>("");
  const [yearTo, setYearTo] = useState<string>("");
  const [searchRes, setSearchRes] = useState<SearchRes | null>(null);
  const [searching, setSearching] = useState(false);

  // advise
  const [adviseText, setAdviseText] = useState("");
  const [adviseRes, setAdviseRes] = useState<AdviseRes | null>(null);
  const [advising, setAdvising] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const doSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    setSearchRes(null);
    try {
      const r = await fetch("/api/research/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          limit: 20,
          year_from: yearFrom ? parseInt(yearFrom) : null,
          year_to: yearTo ? parseInt(yearTo) : null,
        }),
      });
      if (!r.ok) throw new Error(await r.text());
      setSearchRes(await r.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSearching(false);
    }
  };

  const doAdvise = async () => {
    if (!adviseText.trim()) return;
    setAdvising(true);
    setError(null);
    setAdviseRes(null);
    try {
      const r = await fetch("/api/research/advise", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: adviseText, context_type: "研究テーマ" }),
      });
      if (!r.ok) throw new Error(await r.text());
      setAdviseRes(await r.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAdvising(false);
    }
  };

  const saveMemo = async (p: Paper) => {
    await fetch("/api/research/save-memo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: p.title,
        authors: p.authors,
        year: p.year,
        venue: p.venue,
        doi: p.doi,
        abstract: p.abstract,
        pdf_url: p.pdf_url,
        tldr: p.tldr,
      }),
    });
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div
        className="px-8 pt-12 pb-8"
        style={{ background: "radial-gradient(ellipse at top, rgba(20, 184, 166, 0.10), transparent 60%)" }}
      >
        <div className="max-w-5xl mx-auto">
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)", letterSpacing: "0.2em" }}>
            Research
          </p>
          <h1 className="text-4xl font-bold tracking-tight">📚 研究文献 + AI アドバイザー</h1>
          <p className="mt-3 text-sm" style={{ color: "var(--color-text-muted)" }}>
            Semantic Scholar / OpenAlex / CiNii 統合検索 + Claude による研究方向 + 必読文献の提案。 保存は memos に流れて Personal RAG に取り込まれる。
          </p>

          <div className="mt-5 flex items-center gap-2">
            <button
              onClick={() => setTab("search")}
              className="text-sm px-4 py-1.5 rounded-full"
              style={{ background: tab === "search" ? "#14b8a6" : "var(--color-surface-hover)", color: tab === "search" ? "white" : "var(--color-text-muted)" }}
            >
              🔎 統合検索
            </button>
            <button
              onClick={() => setTab("advise")}
              className="text-sm px-4 py-1.5 rounded-full"
              style={{ background: tab === "advise" ? "#14b8a6" : "var(--color-surface-hover)", color: tab === "advise" ? "white" : "var(--color-text-muted)" }}
            >
              🧭 AI アドバイザー
            </button>
          </div>
        </div>
      </div>

      <div className="px-8 pb-32">
        <div className="max-w-5xl mx-auto">
          {error && (
            <div className="mb-4 p-3 rounded-xl text-sm" style={{ background: "rgba(239, 68, 68, 0.08)", color: "var(--color-red)" }}>
              {error}
            </div>
          )}

          {tab === "search" && (
            <>
              <div className="rounded-2xl p-4 mb-4" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && doSearch()}
                  placeholder="検索クエリ (英語推奨。CiNii には日本語可)"
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: "var(--color-surface-hover)", border: "1px solid var(--color-border)" }}
                />
                <div className="mt-3 flex items-center gap-2 flex-wrap">
                  <label className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                    期間:
                    <input
                      type="number"
                      value={yearFrom}
                      onChange={(e) => setYearFrom(e.target.value)}
                      placeholder="from"
                      className="ml-2 w-20 px-2 py-1 rounded text-xs"
                      style={{ background: "var(--color-surface-hover)", border: "1px solid var(--color-border)" }}
                    />
                    <input
                      type="number"
                      value={yearTo}
                      onChange={(e) => setYearTo(e.target.value)}
                      placeholder="to"
                      className="ml-2 w-20 px-2 py-1 rounded text-xs"
                      style={{ background: "var(--color-surface-hover)", border: "1px solid var(--color-border)" }}
                    />
                  </label>
                  <button
                    onClick={doSearch}
                    disabled={searching || !query.trim()}
                    className="ml-auto text-xs px-5 py-1.5 rounded-full disabled:opacity-50"
                    style={{ background: "#14b8a6", color: "white" }}
                  >
                    {searching ? "検索中..." : "🔎 検索"}
                  </button>
                </div>
              </div>

              {searchRes && (
                <>
                  <p className="text-xs mb-3" style={{ color: "var(--color-text-muted)" }}>
                    {searchRes.results.length} 件 (total ≈ {searchRes.total})
                    {searchRes.errors && searchRes.errors.length > 0 ? ` · エラー: ${searchRes.errors.join(", ")}` : ""}
                  </p>
                  <div className="space-y-2">
                    {searchRes.results.map((p, i) => (
                      <PaperCard key={p.doi || `${i}-${p.title}`} p={p} onSave={saveMemo} />
                    ))}
                  </div>
                </>
              )}
            </>
          )}

          {tab === "advise" && (
            <>
              <div className="rounded-2xl p-4 mb-4" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
                <label className="text-xs block mb-1" style={{ color: "var(--color-text-muted)" }}>
                  研究テーマ / 研究計画 (英語または日本語、 1-2 段落程度)
                </label>
                <textarea
                  value={adviseText}
                  onChange={(e) => setAdviseText(e.target.value)}
                  placeholder="例: 多文化共生の文脈における日本語学習者のメタ認知方略と動機づけの関係を、 縦断調査と SCAT 分析で検証する..."
                  className="w-full rounded-lg p-3 text-sm"
                  style={{ background: "var(--color-surface-hover)", border: "1px solid var(--color-border)", minHeight: 140 }}
                />
                <button
                  onClick={doAdvise}
                  disabled={advising || !adviseText.trim()}
                  className="mt-3 text-xs px-5 py-1.5 rounded-full disabled:opacity-50"
                  style={{ background: "#14b8a6", color: "white" }}
                >
                  {advising ? "分析中 (60秒〜)..." : "🧭 AI アドバイザー実行"}
                </button>
              </div>

              {adviseRes && (
                <div className="space-y-5">
                  <div className="rounded-2xl p-4" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
                    <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)" }}>
                      要約
                    </p>
                    <p className="text-sm">{adviseRes.analysis.research_summary}</p>
                    {adviseRes.analysis.key_concepts && (
                      <div className="mt-2 flex gap-1.5 flex-wrap">
                        {adviseRes.analysis.key_concepts.map((c, i) => (
                          <span key={i} className="text-[10px] px-2 py-0.5 rounded" style={{ background: "var(--color-surface-hover)" }}>
                            {c}
                          </span>
                        ))}
                      </div>
                    )}
                    {adviseRes.analysis.advice && (
                      <p className="text-sm mt-3 whitespace-pre-wrap">{adviseRes.analysis.advice}</p>
                    )}
                  </div>

                  {adviseRes.categories.map((cat) => (
                    cat.papers.length > 0 && (
                      <div key={cat.id}>
                        <p className="text-sm font-semibold mb-1">{cat.label} ({cat.papers.length})</p>
                        <p className="text-xs mb-2" style={{ color: "var(--color-text-muted)" }}>
                          {cat.description}
                        </p>
                        <div className="space-y-2">
                          {cat.papers.map((p, i) => (
                            <PaperCard key={p.doi || `${cat.id}-${i}-${p.title}`} p={p} onSave={saveMemo} />
                          ))}
                        </div>
                      </div>
                    )
                  ))}

                  {adviseRes.next_research_directions.length > 0 && (
                    <div className="rounded-2xl p-4" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
                      <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)" }}>
                        次の研究テーマ候補
                      </p>
                      <div className="space-y-3">
                        {adviseRes.next_research_directions.map((d, i) => (
                          <div key={i} className="border-l-2 pl-3" style={{ borderColor: d.difficulty === "easy" ? "#10b981" : d.difficulty === "medium" ? "#f59e0b" : "#ef4444" }}>
                            <p className="text-sm font-semibold">{d.title}</p>
                            <p className="text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>
                              {d.description}
                            </p>
                            <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                              💡 {d.rationale} · 難度: {d.difficulty}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {adviseRes.development_possibilities.length > 0 && (
                    <div className="rounded-2xl p-4" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
                      <p className="text-xs uppercase tracking-widest mb-2" style={{ color: "var(--color-text-muted)" }}>
                        発展の可能性
                      </p>
                      <div className="space-y-3">
                        {adviseRes.development_possibilities.map((d, i) => (
                          <div key={i} className="border-l-2 pl-3" style={{ borderColor: d.potential_impact === "high" ? "#ef4444" : d.potential_impact === "medium" ? "#f59e0b" : "var(--color-border)" }}>
                            <p className="text-sm font-semibold">{d.direction}</p>
                            <p className="text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>
                              {d.description}
                            </p>
                            <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                              影響度: {d.potential_impact}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
