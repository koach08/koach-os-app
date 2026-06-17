"""
AI 自動ディスパッチ — 目的を渡すと、ルーター LLM (Haiku) が最適エンジンを選び、
そのエンジンに直接実行させて結果を返す。

POST /api/dispatch/auto
body: { goal, context?, max_tokens?, force_engine? }
res:  { ok, router: {engine, model, reason}, result, latency_ms }

POST /api/dispatch/auto/preview
  ルーター判定だけを返し実行しない (engine + reason のみ確認)。
"""

from __future__ import annotations

import json
import re
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from router import call_ai, DEFAULT_MODELS

router = APIRouter()


ROUTER_SYSTEM = """あなたは目的を読んで、最適な AI エンジンを 1 つ選ぶルーター。

利用可能エンジン:
- claude     : 長文の論理推論 / コード生成 / 学術文章 / 文体重視 / 戦略思考 (Claude Opus 4.8 / Sonnet 4.6)
- gpt        : 汎用対話 / 構造化 (JSON 出力) / マルチモーダル / 短い実用回答 (GPT-5.5)
- gemini     : 長 context (>100k) / PDF・動画・画像解析 / Google Workspace 連携 (Gemini 2.5 Pro)
- grok       : リアルタイム情報 / X (旧 Twitter) 動向 / 速報 / 規制ゆるめ (Grok 4)
- venice     : 倫理制約なしの個人相談 / プライベート / 検閲なし (Venice Uncensored)
- perplexity : 引用付き Web 検索 / 学術調査 / ファクトチェック (Sonar Pro)
- groq       : 超高速・低コスト・短文回答 / レイテンシ最優先 (Llama 3.3 70B)

判断ヒント:
- 学術文章・論文ドラフト・複雑な思考 → claude
- 「最新の」「ニュース」「今日の」「速報」 → grok or perplexity
- 「調査」「引用」「ソース」 → perplexity
- 「個人的な」「相談」「人に言いにくい」 → venice
- 「PDF を読んで」「画像を見て」 → gemini
- 「速く」「短く」「すぐ」 → groq
- 「コード」「リファクタ」 → claude
- それ以外の汎用 → gpt (default)

必ず JSON 1 オブジェクトのみ返す:
{"engine": "claude|gpt|gemini|grok|venice|perplexity|groq", "reason": "1 文の根拠 (40 字以内、体言止め可)"}

Markdown のコードフェンス禁止。"""


EXEC_SYSTEM = """あなたは志柿浩一郎 (北海道大学 准教授・個人開発者・家庭持ち) のアシスタント。

スタイル:
- 簡潔。冗長な前置き禁止。
- 「です・ます」調。 必要なら箇条書き。
- 抽象名詞「〜性」、感情を煽る表現、過度な絵文字は使わない。
- 不明な点は確認し、 仮定を置く時は明示する。
- 迎合しない。 必要なら反対意見を返す。
"""


class AutoDispatchReq(BaseModel):
    goal: str
    context: str | None = None
    max_tokens: int = 2000
    force_engine: str | None = None  # 指定があればルーター LLM を呼ばずそのまま使う


def _route(goal: str, context: str | None) -> tuple[str, str]:
    """ルーター LLM (Haiku) で engine を選ぶ。戻り値 (engine, reason)"""
    user_msg = f"目的: {goal}\n追加 context: {context or '(なし)'}"
    try:
        raw = call_ai(
            messages=[{"role": "user", "content": user_msg}],
            system=ROUTER_SYSTEM,
            engine="claude",
            model="claude-haiku-4-5",
            max_tokens=200,
        )
    except Exception:
        return ("claude", "fallback (router 不通)")
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return ("claude", "fallback (router 出力 parse 不可)")
    try:
        d = json.loads(m.group(0))
    except Exception:
        return ("claude", "fallback (JSON parse 失敗)")
    engine = d.get("engine", "claude")
    reason = d.get("reason", "")
    if engine not in DEFAULT_MODELS:
        engine = "claude"
        reason = f"フォールバック ({d.get('engine')} は未登録)"
    return (engine, reason[:80])


@router.post("/dispatch/auto/preview")
def dispatch_preview(req: AutoDispatchReq):
    engine, reason = _route(req.goal, req.context)
    return {
        "ok": True,
        "router": {"engine": engine, "model": DEFAULT_MODELS[engine], "reason": reason},
    }


@router.post("/dispatch/auto")
def dispatch_auto(req: AutoDispatchReq):
    t0 = time.time()
    if req.force_engine and req.force_engine in DEFAULT_MODELS:
        engine, reason = req.force_engine, "ユーザー指定 (force_engine)"
    else:
        engine, reason = _route(req.goal, req.context)

    model = DEFAULT_MODELS[engine]
    user_content = req.goal + (f"\n\n=== 追加 context ===\n{req.context}" if req.context else "")
    try:
        result = call_ai(
            messages=[{"role": "user", "content": user_content}],
            system=EXEC_SYSTEM,
            engine=engine,
            model=model,
            max_tokens=req.max_tokens,
        )
    except Exception as e:
        raise HTTPException(500, f"exec failed ({engine}/{model}): {e}")

    return {
        "ok": True,
        "router": {"engine": engine, "model": model, "reason": reason},
        "result": result,
        "latency_ms": int((time.time() - t0) * 1000),
    }
