"""
研究文献検索 + AI 研究アドバイザー (research-navigator から移植、 軽量版)

POST /api/research/search   : 統合検索 (Semantic Scholar + OpenAlex + CiNii、 DOI で dedup)
POST /api/research/advise   : 研究テーマ → 検索クエリ生成 → 並列検索 → 関連度スコアリング
POST /api/research/save-memo: 1 件の論文を memos に保存 (既存 RAG と連携)

ENV (任意):
- SEMANTIC_SCHOLAR_API_KEY : 無くても動くが rate limit 厳しめ
- OPENALEX_EMAIL           : "Polite Pool" 入り (rate limit 緩和)
- OPENALEX_API_KEY         : OpenAlex Plus key (登録ユーザー、 さらに緩和)
- CINII_API_KEY            : 無いと CiNii は無効
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_manager import MEMOS_FILE, append_jsonl, generate_id, timestamp_jst
from router import call_ai

router = APIRouter()


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _http_get_json(url: str, headers: dict | None = None, timeout: int = 25) -> dict:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "koach-os/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Semantic Scholar
# ---------------------------------------------------------------------------

_S2_FIELDS = "paperId,title,abstract,year,authors,citationCount,referenceCount,isOpenAccess,openAccessPdf,fieldsOfStudy,tldr,externalIds,venue"


def _map_s2(p: dict) -> dict:
    return {
        "source": "semantic_scholar",
        "semantic_scholar_id": p.get("paperId"),
        "doi": (p.get("externalIds") or {}).get("DOI"),
        "title": p.get("title") or "Untitled",
        "abstract": p.get("abstract"),
        "authors": [{"name": a.get("name", "")} for a in (p.get("authors") or [])],
        "year": p.get("year"),
        "venue": p.get("venue"),
        "citation_count": p.get("citationCount") or 0,
        "reference_count": p.get("referenceCount") or 0,
        "is_open_access": bool(p.get("isOpenAccess")),
        "pdf_url": (p.get("openAccessPdf") or {}).get("url"),
        "fields_of_study": p.get("fieldsOfStudy"),
        "tldr": (p.get("tldr") or {}).get("text"),
    }


def _search_semantic_scholar(query: str, limit: int = 20, year_from: int | None = None, year_to: int | None = None) -> dict:
    headers = {"Content-Type": "application/json", "User-Agent": "koach-os/1.0"}
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
    if api_key:
        headers["x-api-key"] = api_key
    url = (
        f"https://api.semanticscholar.org/graph/v1/paper/search"
        f"?query={urllib.parse.quote(query)}&fields={_S2_FIELDS}&limit={min(100, limit)}"
    )
    if year_from or year_to:
        url += f"&year={year_from or 1900}-{year_to or 2026}"
    try:
        data = _http_get_json(url, headers=headers)
    except Exception:
        return {"results": [], "total": 0}
    return {
        "results": [_map_s2(p) for p in (data.get("data") or [])],
        "total": data.get("total") or 0,
    }


# ---------------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------------

def _reconstruct_abstract(inv_idx: dict | None) -> str | None:
    if not inv_idx:
        return None
    words: list[tuple[str, int]] = []
    for word, positions in inv_idx.items():
        for pos in positions:
            words.append((word, pos))
    words.sort(key=lambda x: x[1])
    return " ".join(w for w, _ in words)


def _map_oa(w: dict) -> dict:
    doi_raw = w.get("doi") or ""
    doi = doi_raw.replace("https://doi.org/", "") if doi_raw else None
    return {
        "source": "openalex",
        "openalex_id": (w.get("id") or "").replace("https://openalex.org/", ""),
        "doi": doi,
        "title": w.get("title") or w.get("display_name") or "Untitled",
        "abstract": _reconstruct_abstract(w.get("abstract_inverted_index")),
        "authors": [{"name": (a.get("author") or {}).get("display_name", "")} for a in (w.get("authorships") or [])],
        "year": w.get("publication_year"),
        "venue": ((w.get("primary_location") or {}).get("source") or {}).get("display_name"),
        "citation_count": w.get("cited_by_count") or 0,
        "reference_count": w.get("referenced_works_count") or 0,
        "is_open_access": ((w.get("open_access") or {}).get("is_oa")) or False,
        "pdf_url": (w.get("open_access") or {}).get("oa_url"),
        "fields_of_study": [(c.get("display_name") or "") for c in (w.get("concepts") or [])[:5]],
    }


def _search_openalex(query: str, limit: int = 20, year_from: int | None = None, year_to: int | None = None) -> dict:
    url = f"https://api.openalex.org/works?search={urllib.parse.quote(query)}&per_page={min(50, limit)}"
    mailto = os.environ.get("OPENALEX_EMAIL", "")
    if mailto:
        url += f"&mailto={urllib.parse.quote(mailto)}"
    api_key = os.environ.get("OPENALEX_API_KEY", "")
    if api_key:
        url += f"&api_key={urllib.parse.quote(api_key)}"
    filters: list[str] = []
    if year_from:
        filters.append(f"from_publication_date:{year_from}-01-01")
    if year_to:
        filters.append(f"to_publication_date:{year_to}-12-31")
    if filters:
        url += f"&filter={','.join(filters)}"
    try:
        data = _http_get_json(url)
    except Exception:
        return {"results": [], "total": 0}
    return {
        "results": [_map_oa(w) for w in (data.get("results") or [])],
        "total": (data.get("meta") or {}).get("count") or 0,
    }


# ---------------------------------------------------------------------------
# CiNii (日本論文)
# ---------------------------------------------------------------------------

def _search_cinii(query: str, limit: int = 20, year_from: int | None = None, year_to: int | None = None) -> dict:
    api_key = os.environ.get("CINII_API_KEY", "")
    if not api_key:
        return {"results": [], "total": 0}
    url = (
        f"https://cir.nii.ac.jp/opensearch/articles?q={urllib.parse.quote(query)}"
        f"&count={min(50, limit)}&format=json&appid={api_key}"
    )
    if year_from:
        url += f"&from={year_from}"
    if year_to:
        url += f"&until={year_to}"
    try:
        data = _http_get_json(url)
    except Exception:
        return {"results": [], "total": 0}
    graph = data.get("@graph") or []
    if not graph:
        return {"results": [], "total": 0}
    total_raw = graph[0].get("opensearch:totalResults") or 0
    try:
        total = int(total_raw)
    except Exception:
        total = 0
    items = graph[1:]
    results: list[dict] = []
    for it in items:
        titles = it.get("dc:title") or []
        title_en = next((t.get("@value") for t in titles if t.get("@language") == "en"), None)
        title_ja = next((t.get("@value") for t in titles if t.get("@language") == "ja"), None)
        title = title_en or title_ja or "Untitled"
        cid = (it.get("@id") or "").replace("https://cir.nii.ac.jp/crid/", "")
        year = None
        pub = it.get("prism:publicationDate")
        if pub:
            try:
                year = int(pub[:4])
            except Exception:
                year = None
        results.append({
            "source": "cinii",
            "cinii_id": cid,
            "doi": it.get("prism:doi"),
            "title": title,
            "title_ja": title_ja,
            "abstract": ((it.get("dc:description") or [{}])[0] or {}).get("@value"),
            "authors": [{"name": a.get("@value", "")} for a in (it.get("dc:creator") or [])],
            "year": year,
            "venue": it.get("prism:publicationName"),
            "citation_count": 0,
            "reference_count": 0,
            "is_open_access": False,
        })
    return {"results": results, "total": total}


# ---------------------------------------------------------------------------
# Unified search (DOI dedup + 並列)
# ---------------------------------------------------------------------------

def _dedupe_by_doi(results: list[dict]) -> list[dict]:
    doi_map: dict[str, dict] = {}
    no_doi: list[dict] = []
    for r in results:
        doi = r.get("doi")
        if doi:
            key = doi.lower().strip()
            existing = doi_map.get(key)
            if existing:
                existing.setdefault("sources", []).append(r["source"])
                existing["merged"] = True
                if r["source"] == "semantic_scholar":
                    for field in ("semantic_scholar_id", "abstract", "tldr", "fields_of_study"):
                        if r.get(field):
                            existing[field] = r[field]
                    existing["citation_count"] = max(existing.get("citation_count", 0), r.get("citation_count", 0))
                    existing["reference_count"] = max(existing.get("reference_count", 0), r.get("reference_count", 0))
                if r["source"] == "openalex":
                    existing["openalex_id"] = r.get("openalex_id")
                if r["source"] == "cinii":
                    existing["cinii_id"] = r.get("cinii_id")
                    if r.get("title_ja"):
                        existing["title_ja"] = r["title_ja"]
                if r.get("is_open_access"):
                    existing["is_open_access"] = True
                    existing["pdf_url"] = existing.get("pdf_url") or r.get("pdf_url")
            else:
                doi_map[key] = {**r, "sources": [r["source"]], "merged": False}
        else:
            no_doi.append({**r, "sources": [r["source"]], "merged": False})
    return list(doi_map.values()) + no_doi


_SEARCH_FNS = {
    "semantic_scholar": _search_semantic_scholar,
    "openalex": _search_openalex,
    "cinii": _search_cinii,
}


def _unified_search(query: str, sources: list[str], limit: int, year_from: int | None, year_to: int | None) -> dict:
    sources = [s for s in sources if s in _SEARCH_FNS]
    all_results: list[dict] = []
    total = 0
    errors: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(sources))) as pool:
        futures = {pool.submit(_SEARCH_FNS[s], query, limit, year_from, year_to): s for s in sources}
        for fut in concurrent.futures.as_completed(futures):
            s = futures[fut]
            try:
                d = fut.result()
                all_results.extend(d.get("results") or [])
                total += d.get("total") or 0
            except Exception as e:
                errors.append(f"{s}: {e}")
    deduped = _dedupe_by_doi(all_results)
    deduped.sort(key=lambda x: (-(x.get("citation_count") or 0), -(x.get("year") or 0)))
    return {"results": deduped, "total": total, "errors": errors}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class SearchReq(BaseModel):
    query: str
    limit: int = 20
    year_from: int | None = None
    year_to: int | None = None
    sources: list[str] = ["semantic_scholar", "openalex", "cinii"]


@router.post("/research/search")
def research_search(req: SearchReq):
    if not req.query.strip():
        raise HTTPException(400, "query が空です")
    r = _unified_search(req.query, req.sources, req.limit, req.year_from, req.year_to)
    return {"ok": True, **r}


# --- Research Advisor (2-stage Claude) ---

_ADVISOR_ANALYSIS_PROMPT = """あなたは研究アドバイザー。 以下の研究テキストを分析し、 文献検索のための情報を JSON で返してください。

入力タイプ: {context_type}

テキスト:
{text}

JSON のみを返す (コードフェンス禁止):
{{
  "research_summary": "この研究テーマの簡潔な要約 (2-3 文)",
  "key_concepts": ["主要概念 1", "主要概念 2", "主要概念 3"],
  "search_queries": [
    {{"query": "英語検索クエリ", "category": "foundational | methodology | recent | related", "purpose": "なぜ必要か (日本語)"}}
  ],
  "expected_fields": ["関連学術分野"],
  "advice": "取り組む上でのアドバイス (日本語、 3-5 文)",
  "next_research_directions": [
    {{"title": "次の研究テーマ候補", "description": "概要 (2-3 文)", "rationale": "有望な理由 (1-2 文)", "difficulty": "easy | medium | hard"}}
  ],
  "development_possibilities": [
    {{"direction": "発展方向", "description": "具体的展開 (2-3 文)", "potential_impact": "high | medium | low"}}
  ]
}}

search_queries は 5-8 個 (foundational/methodology/recent/related の 4 カテゴリで均等)。
next_research_directions は 3-5 個、 development_possibilities は 2-4 個。
"""


_SCORING_PROMPT = """以下の研究テーマに対する各論文の関連度を評価してください。

研究テーマ:
{text}

論文リスト:
{paper_list}

以下の JSON 配列のみ返す (Markdown 禁止):
[{{"index": 1, "relevance": 85, "category": "must_read | recommended | related", "reason_ja": "なぜ重要か (日本語、 1 文)"}}]

category 基準:
- must_read (relevance 80+): 不可欠
- recommended (50-79): 推奨
- related (-49): 周辺
"""


class AdviseReq(BaseModel):
    text: str
    context_type: str = "研究メモ"


def _per_query_search(sq: dict) -> dict:
    q = sq.get("query", "")
    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_search_semantic_scholar, q, 10)
        f2 = pool.submit(_search_openalex, q, 10)
        for f in (f1, f2):
            try:
                results.extend((f.result() or {}).get("results") or [])
            except Exception:
                pass
    seen: set[str] = set()
    unique: list[dict] = []
    for r in results:
        key = (r.get("doi") or "").lower()
        if key:
            if key in seen:
                continue
            seen.add(key)
        unique.append(r)
    return {
        "category": sq.get("category"),
        "purpose": sq.get("purpose"),
        "query": q,
        "papers": unique[:8],
    }


@router.post("/research/advise")
def research_advise(req: AdviseReq):
    if not req.text.strip():
        raise HTTPException(400, "text が空です")

    # Step 1: 分析
    try:
        raw = call_ai(
            messages=[{
                "role": "user",
                "content": _ADVISOR_ANALYSIS_PROMPT.format(context_type=req.context_type, text=req.text),
            }],
            system="あなたは研究アドバイザー。 JSON のみ返す。",
            engine="claude",
            model="claude-sonnet-4-6",
            max_tokens=2500,
        )
    except Exception as e:
        raise HTTPException(500, f"AI analysis failed: {e}")
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        raise HTTPException(500, "AI analysis output is not JSON")
    try:
        analysis = json.loads(m.group(0))
    except Exception as e:
        raise HTTPException(500, f"JSON parse failed: {e}")

    # Step 2: 各 query で並列検索 (S2 + OpenAlex のみ)
    queries = analysis.get("search_queries") or []
    category_results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for cr in pool.map(_per_query_search, queries):
            category_results.append(cr)

    # Step 3: 全体 dedup
    all_papers: list[dict] = []
    for cr in category_results:
        for p in cr["papers"]:
            all_papers.append({**p, "search_category": cr["category"]})

    global_seen: set[str] = set()
    unique_papers: list[dict] = []
    for p in all_papers:
        key = (p.get("doi") or "").lower() or (p.get("title") or "").lower()[:50]
        if key in global_seen:
            continue
        global_seen.add(key)
        unique_papers.append(p)

    top_papers = unique_papers[:30]
    paper_list_text = "\n".join(
        f"{i + 1}. \"{p.get('title', '')}\" ({p.get('year', 'N/A')}) - "
        f"{', '.join(a.get('name', '') for a in (p.get('authors') or [])[:2])} - "
        f"cat: {p.get('search_category')}\n   Abstract: {(p.get('abstract') or '')[:200]}..."
        for i, p in enumerate(top_papers)
    )

    # Step 4: スコアリング
    scores: list[dict] = []
    if top_papers:
        try:
            raw = call_ai(
                messages=[{
                    "role": "user",
                    "content": _SCORING_PROMPT.format(text=req.text, paper_list=paper_list_text),
                }],
                system="研究関連度スコアラー。 JSON 配列のみ返す。",
                engine="claude",
                model="claude-sonnet-4-6",
                max_tokens=4000,
            )
            m = re.search(r"\[[\s\S]*\]", raw)
            if m:
                try:
                    scores = json.loads(m.group(0))
                except Exception:
                    scores = []
        except Exception:
            scores = []

    score_map = {s.get("index"): s for s in scores if isinstance(s, dict)}
    for i, p in enumerate(top_papers):
        s = score_map.get(i + 1) or {}
        p["relevance"] = int(s.get("relevance", 50))
        p["recommendation_category"] = s.get("category", "related")
        p["reason_ja"] = s.get("reason_ja", "")
    top_papers.sort(key=lambda p: -p.get("relevance", 0))

    must = [p for p in top_papers if p.get("recommendation_category") == "must_read"]
    rec = [p for p in top_papers if p.get("recommendation_category") == "recommended"]
    rel = [p for p in top_papers if p.get("recommendation_category") == "related"]

    return {
        "ok": True,
        "analysis": {
            "research_summary": analysis.get("research_summary"),
            "key_concepts": analysis.get("key_concepts"),
            "expected_fields": analysis.get("expected_fields"),
            "advice": analysis.get("advice"),
        },
        "categories": [
            {"id": "must_read", "label": "必読文献", "description": "この研究に不可欠な先行研究", "papers": must},
            {"id": "recommended", "label": "推奨文献", "description": "読んでおくべき関連文献", "papers": rec},
            {"id": "related", "label": "関連文献", "description": "参考になる周辺分野の文献", "papers": rel},
        ],
        "search_queries": queries,
        "next_research_directions": analysis.get("next_research_directions") or [],
        "development_possibilities": analysis.get("development_possibilities") or [],
    }


# --- 論文を memos に保存 (Personal RAG に取り込まれる) ---

class SaveMemoReq(BaseModel):
    title: str
    authors: list[dict] = []
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    abstract: str | None = None
    pdf_url: str | None = None
    tldr: str | None = None
    note: str | None = None  # ユーザーのコメント


@router.post("/research/save-memo")
def save_as_memo(req: SaveMemoReq):
    authors_str = ", ".join(a.get("name", "") for a in req.authors[:5])
    parts = [f"# {req.title}", ""]
    if authors_str:
        parts.append(f"**著者**: {authors_str}")
    if req.year:
        parts.append(f"**年**: {req.year}")
    if req.venue:
        parts.append(f"**掲載**: {req.venue}")
    if req.doi:
        parts.append(f"**DOI**: https://doi.org/{req.doi}")
    if req.pdf_url:
        parts.append(f"**PDF**: {req.pdf_url}")
    if req.tldr:
        parts.append(f"\n**TL;DR**: {req.tldr}")
    if req.abstract:
        parts.append(f"\n**Abstract**\n{req.abstract}")
    if req.note:
        parts.append(f"\n**メモ**\n{req.note}")
    content = "\n".join(parts)

    memo = {
        "id": generate_id("memo"),
        "timestamp": timestamp_jst(),
        "title": req.title[:120],
        "content": content,
        "tags": ["research", "paper"] + ([f"year:{req.year}"] if req.year else []),
        "source": "research-advisor",
    }
    append_jsonl(MEMOS_FILE, memo)
    return {"ok": True, "memo_id": memo["id"]}
