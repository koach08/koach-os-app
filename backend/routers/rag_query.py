"""
NotebookLM 風パーソナル RAG。
memos / decisions / private_chat / Coach backlog / failures を semantic search し、
引用付きで AI が回答する。

埋め込みは memory_engine の collection を再利用 + 新しい "personal_kb" collection を使う。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_manager import (
    DATA_DIR,
    DECISIONS_FILE,
    FAILURES_FILE,
    MEMOS_FILE,
    get_secret,
    now_jst,
    read_jsonl,
)
from router import call_ai, DEFAULT_MODELS

router = APIRouter()

KB_DIR = Path(__file__).parent.parent.parent / "memory" / "personal_kb"
KB_DIR.mkdir(parents=True, exist_ok=True)
PRIVATE_CHAT_FILE = DATA_DIR / "private_chat.jsonl"


def _get_collection():
    import chromadb
    client = chromadb.PersistentClient(path=str(KB_DIR))
    return client.get_or_create_collection(
        name="personal_kb",
        metadata={"hnsw:space": "cosine"},
    )


def _embed(texts: list[str]) -> list[list[float]]:
    import openai
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = openai.OpenAI(api_key=api_key)
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=[t[:8000] for t in texts if t.strip()],
    )
    return [d.embedding for d in resp.data]


def _gather_docs() -> list[dict]:
    """Pull all knowledge sources into a flat doc list."""
    docs: list[dict] = []

    # Memos: 同じ id を後ろの行が上書きする (append-only update)。最新だけ採用
    memo_state: dict[str, dict] = {}
    for m in read_jsonl(MEMOS_FILE):
        if not m.get("id"):
            continue
        if m.get("_deleted"):
            memo_state.pop(m["id"], None)
            continue
        memo_state[m["id"]] = m
    for m in memo_state.values():
        text = (m.get("content", "") or m.get("body", "") or "").strip()
        if not text:
            continue
        first_line = text.splitlines()[0][:120] if text else ""
        docs.append({
            "id": f"memo:{m['id']}",
            "kind": "memo",
            "text": text[:4000],
            "title": first_line,
            "timestamp": m.get("created_at", m.get("timestamp", "")),
        })

    for d in read_jsonl(DECISIONS_FILE):
        text = (d.get("title", "") + "\n" + d.get("reasoning", "")).strip()
        if not text:
            continue
        docs.append({
            "id": f"decision:{d.get('id', d.get('timestamp', ''))[:60]}",
            "kind": "decision",
            "text": text[:4000],
            "title": d.get("title", "")[:120],
            "timestamp": d.get("timestamp", ""),
        })

    for f in read_jsonl(FAILURES_FILE):
        text = (f.get("what", "") + "\n→ " + f.get("lesson", "")).strip()
        if not text:
            continue
        docs.append({
            "id": f"failure:{f.get('id', f.get('timestamp', ''))[:60]}",
            "kind": "failure",
            "text": text[:4000],
            "title": f.get("what", "")[:120],
            "timestamp": f.get("timestamp", ""),
        })

    if PRIVATE_CHAT_FILE.exists():
        # Pair consecutive user→assistant turns (each line is one message)
        last_user: dict | None = None
        for line in PRIVATE_CHAT_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            role = e.get("role", "")
            content = (e.get("content", "") or "").strip()
            if not content:
                continue
            if role == "user":
                last_user = e
            elif role == "assistant" and last_user is not None:
                text = f"Q: {last_user.get('content','')}\nA: {content}"
                ts = last_user.get("timestamp", "")
                docs.append({
                    "id": f"private:{ts[:30]}",
                    "kind": "private",
                    "text": text[:4000],
                    "title": (last_user.get("content", "") or "")[:80],
                    "timestamp": ts,
                })
                last_user = None

    try:
        from routers.productivity import _load_backlog
        for b in _load_backlog():
            text = (b.get("title", "") + "\n" + b.get("notes", "")).strip()
            if not text:
                continue
            docs.append({
                "id": f"backlog:{b.get('id','')}",
                "kind": "backlog",
                "text": text[:2000],
                "title": b.get("title", "")[:120],
                "timestamp": "",
            })
    except Exception:
        pass

    # work_log (実績台帳): やり遂げた作業を「自分が過去にやった事」として検索可能に
    try:
        from routers.work_log import _materialize as _wl_materialize
        for w in _wl_materialize().values():
            bits = [w.get("title", "")]
            meta_line = " / ".join(
                x for x in [w.get("project", ""), w.get("category", ""),
                            (f"AI: {w['engine']}" if w.get("engine") else "")]
                if x
            )
            if meta_line:
                bits.append(meta_line)
            if w.get("outcome"):
                bits.append(w["outcome"])
            text = "\n".join(b for b in bits if b).strip()
            if not text:
                continue
            docs.append({
                "id": f"work:{w.get('id','')}",
                "kind": "work",
                "text": text[:2000],
                "title": w.get("title", "")[:120],
                "timestamp": w.get("date", "") or w.get("created_at", ""),
            })
    except Exception:
        pass

    return docs


@router.post("/rag/reindex")
def rag_reindex():
    docs = _gather_docs()
    if not docs:
        return {"indexed": 0, "skipped": "no docs"}
    col = _get_collection()
    try:
        col.delete(where={"_": {"$ne": "never"}})
    except Exception:
        pass
    try:
        existing_ids = col.get(limit=10000).get("ids", [])
        if existing_ids:
            col.delete(ids=existing_ids)
    except Exception:
        pass
    texts = [d["text"] for d in docs]
    try:
        embeddings = _embed(texts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"embedding failed: {e}")
    metas = [
        {"kind": d["kind"], "title": d["title"], "timestamp": d["timestamp"], "_": "doc"}
        for d in docs
    ]
    col.add(
        ids=[d["id"] for d in docs],
        embeddings=embeddings,
        documents=texts,
        metadatas=metas,
    )
    return {"indexed": len(docs)}


class RagQuery(BaseModel):
    query: str
    top_k: int = 6
    engine: str = "claude"


@router.post("/rag/query")
def rag_query(req: RagQuery):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query 必須")
    col = _get_collection()
    total = 0
    try:
        total = col.count()
    except Exception:
        total = 0
    if total == 0:
        return {
            "answer": "ナレッジベース未構築。/api/rag/reindex を一度叩いてください。",
            "citations": [],
            "indexed_count": 0,
        }
    try:
        emb = _embed([req.query])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"embed failed: {e}")
    results = col.query(
        query_embeddings=emb,
        n_results=min(req.top_k, total),
        include=["documents", "metadatas", "distances"],
    )
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]
    citations: list[dict[str, Any]] = []
    for i, (doc, meta, dist) in enumerate(zip(docs, metas, dists)):
        citations.append({
            "index": i + 1,
            "kind": meta.get("kind", ""),
            "title": meta.get("title", ""),
            "timestamp": meta.get("timestamp", ""),
            "excerpt": doc[:400],
            "relevance": round(1 - dist, 3),
        })

    citation_text = "\n\n".join(
        f"[{c['index']}] ({c['kind']}, {c['timestamp'][:10]}) {c['title']}\n  {c['excerpt']}"
        for c in citations
    )

    system_prompt = """あなたは志柿のパーソナル知識ベース AI。
過去の memo / decision / failure / private chat / backlog / work (実績台帳) から引用付きで質問に答える。

ルール:
- 引用元は [1], [2] の形式で本文中に挟む。citation_text にない情報を勝手に補わない
- 該当が薄ければ「該当する記録が薄いです」と素直に言う
- 推測や一般論で水増ししない
- 200〜400字。です/ます調。一人称「自分」。抽象名詞「〜性」NG"""

    user_msg = f"""質問: {req.query}

## 関連する過去の記録
{citation_text}

上の記録だけを根拠に、引用 [1] [2] を本文に挟みながら答えてください。"""

    engine = req.engine if req.engine in DEFAULT_MODELS else "claude"
    model = DEFAULT_MODELS[engine]

    try:
        answer = call_ai(
            messages=[{"role": "user", "content": user_msg}],
            system=system_prompt,
            engine=engine,
            model=model,
            max_tokens=900,
        )
    except Exception as e:
        answer = f"(AI 生成失敗: {e})"

    return {
        "query": req.query,
        "answer": answer,
        "citations": citations,
        "indexed_count": total,
        "engine_used": engine,
        "model_used": model,
        "generated_at": now_jst().isoformat(),
    }


@router.get("/rag/stats")
def rag_stats():
    try:
        col = _get_collection()
        return {"indexed_count": col.count()}
    except Exception as e:
        return {"indexed_count": 0, "error": str(e)}
