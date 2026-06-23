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
- fugu       : 複数フロンティア LLM を自動編成する高速既定 / 強い汎用 / 輸出規制の影響なし (Sakana Fugu)
- fugu-ultra : 難問・多段推論 / AI 研究 / 論文再現 / 文献・特許調査 / 深い分析 (Sakana Fugu Ultra)

判断ヒント:
- 学術文章・論文ドラフト・複雑な思考 → claude
- 「研究」「論文再現」「文献調査」「特許調査」「難しい多段の問題」 → fugu-ultra
- 「最新の」「ニュース」「今日の」「速報」 → grok or perplexity
- 「調査」「引用」「ソース」 → perplexity
- 「個人的な」「相談」「人に言いにくい」 → venice
- 「PDF を読んで」「画像を見て」 → gemini
- 「速く」「短く」「すぐ」 → groq
- 「コード」「リファクタ」 → claude
- それ以外の汎用 → gpt (default)

必ず JSON 1 オブジェクトのみ返す:
{"engine": "claude|gpt|gemini|grok|venice|perplexity|groq|fugu|fugu-ultra", "reason": "1 文の根拠 (40 字以内、体言止め可)"}

Markdown のコードフェンス禁止。"""


EXEC_SYSTEM = """あなたは志柿浩一郎 (北海道大学 准教授・個人開発者・家庭持ち) のアシスタント。

スタイル:
- 簡潔。冗長な前置き禁止。
- 「です・ます」調。 必要なら箇条書き。
- 抽象名詞「〜性」、感情を煽る表現、過度な絵文字は使わない。
- 不明な点は確認し、 仮定を置く時は明示する。
- 迎合しない。 必要なら反対意見を返す。
"""


SUGGEST_SYSTEM = """あなたは志柿の AI エンジン選定アドバイザー。
タスク内容と、本人が過去に「どの種類の作業でどの AI を使ったか」の実績 (work_log) を見て、最適なエンジンを1つ薦める。

利用可能エンジン (一般的な強み):
- claude     : 長文推論 / コード / 学術文章 / 戦略思考
- gpt        : 汎用対話 / 構造化 (JSON) / マルチモーダル
- gemini     : 長 context / PDF・画像・動画解析
- grok       : リアルタイム / X 動向 / 速報
- venice     : 検閲なしの個人相談
- perplexity : 引用付き Web 検索 / 学術調査
- groq       : 超高速・低コスト・短文
- fugu       : 複数フロンティアを自動編成する強い汎用 (Sakana Fugu)
- fugu-ultra : 研究 / 論文再現 / 文献・特許調査 / 難問多段 (Sakana Fugu Ultra)

判断ルール (忖度しない):
- 本人の実績 (履歴) があれば最優先で根拠にする。数字を引いて言う (例: この作業は過去 perplexity 3 回)
- 履歴が薄い / 無い時は「履歴が薄いので一般論ベース」と正直に断る
- 一般論と実績がぶつかる時、僅差なら「僅差」と言って断定しない
- おだてない。タスクに最適な選択だけ返す

必ず JSON 1 オブジェクトのみ返す:
{"engine":"claude|gpt|gemini|grok|venice|perplexity|groq|fugu|fugu-ultra", "reason":"40字以内の根拠 (履歴があれば数字を引く)", "history_used": true|false, "close_call": true|false}
Markdown のコードフェンス禁止。"""


class SuggestReq(BaseModel):
    task: str
    category: str | None = None


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


@router.post("/dispatch/suggest-engine")
def suggest_engine(req: SuggestReq):
    """work_log の実績を根拠に「この作業はこの AI が向く」を提案。
    実績が薄ければ正直に一般論ベースと言い、僅差なら断定しない (忖度しない)。"""
    if not req.task.strip():
        raise HTTPException(400, "task required")

    hist_lines: list[str] = []
    history_thin = True
    try:
        from routers.work_log import work_log_stats
        stats = work_log_stats(90)
        ebc = stats.get("engine_by_category", {})
        by_eng = stats.get("by_engine", {})
        if stats.get("total_entries", 0) >= 3:
            history_thin = False
        if req.category and req.category in ebc:
            pairs = sorted(ebc[req.category].items(), key=lambda x: -x[1])
            hist_lines.append(
                f"カテゴリ「{req.category}」での AI 使用: " + ", ".join(f"{e}:{n}" for e, n in pairs)
            )
        if by_eng:
            pairs = sorted(by_eng.items(), key=lambda x: -x[1])
            hist_lines.append("全体の AI 使用: " + ", ".join(f"{e}:{n}" for e, n in pairs))
        if ebc:
            hist_lines.append("カテゴリ別: " + "; ".join(
                f"{c}=" + ",".join(f"{e}:{n}" for e, n in sorted(m.items(), key=lambda x: -x[1]))
                for c, m in ebc.items()
            ))
    except Exception:
        pass

    hist_text = "\n".join(hist_lines) if hist_lines else "(実績データなし)"
    user_msg = (
        f"タスク: {req.task}\nカテゴリ: {req.category or '(未指定)'}\n\n"
        f"## 本人の過去の AI 使用実績 (直近90日)\n{hist_text}"
    )
    try:
        raw = call_ai(
            messages=[{"role": "user", "content": user_msg}],
            system=SUGGEST_SYSTEM,
            engine="claude",
            model="claude-haiku-4-5",
            max_tokens=200,
        )
    except Exception as e:
        raise HTTPException(500, f"suggest failed: {e}")

    parsed: dict = {}
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(0))
        except Exception:
            parsed = {}
    engine = parsed.get("engine", "claude")
    if engine not in DEFAULT_MODELS:
        engine = "claude"
    return {
        "ok": True,
        "engine": engine,
        "model": DEFAULT_MODELS[engine],
        "reason": (parsed.get("reason", "") or "")[:120],
        "history_used": bool(parsed.get("history_used", False)),
        "close_call": bool(parsed.get("close_call", False)),
        "history_thin": history_thin,
        "history_summary": hist_lines,
    }


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
