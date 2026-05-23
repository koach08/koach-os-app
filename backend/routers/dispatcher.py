"""
POST /api/dispatcher — AI ディスパッチャー。
目的を渡すと推奨 AI サービスと、そのサービスにそのまま貼り付ける指示書 (MD) を生成。
Koach OS の API 経由ではなく、本物の AI サービス（Claude.ai / NotebookLM / Canva AI / Codex 等）に持ち込む前提。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_manager import now_jst
from router import call_ai, DEFAULT_MODELS

router = APIRouter()


AI_CATALOG = """
[Claude.ai (claude.ai/web)]
- 強み: 長文の思考、戦略、論文ドラフト、コードレビュー
- 弱み: 最新ニュース、画像生成
- 入力上限: 1M tokens (Opus 4.7)

[ChatGPT (chat.openai.com)]
- 強み: マルチモーダル、Canvas、コード実行、画像生成 (DALL-E 3)
- 弱み: 学術文体は Claude より弱め

[Claude Code (CLI in terminal)]
- 強み: ローカル repo を触る、ファイル編集、コマンド実行
- 弱み: 単発の文章生成には過剰

[Codex (codex.openai.com / OpenAI Codex)]
- 強み: コード生成、長いリファクタ、PR ドラフト
- 弱み: 文章

[Gemini (gemini.google.com)]
- 強み: 長文 PDF / 動画解析、Google Workspace 連携
- 弱み: 日本語の論文文体

[Google AI Studio (aistudio.google.com)]
- 強み: Gemini 2.0 multimodal、画像/動画入力、無料
- 弱み: UI が開発者向け

[NotebookLM (notebooklm.google.com)]
- 強み: 自分のドキュメント (PDF, MD, スライド) から RAG、引用付きで答える
- 弱み: 外部 Web 検索なし

[Perplexity (perplexity.ai)]
- 強み: Web 検索ベースの回答、引用 URL あり
- 弱み: 深い論述

[Canva AI (canva.com)]
- 強み: スライド、ソーシャル画像、プレゼン
- 弱み: コード、長文

[Grok (grok.com)]
- 強み: X (Twitter) 連携、リアルタイム情報、規制ゆるめ
- 弱み: 日本語論文体

[GenSpark (genspark.ai)]
- 強み: 自動 Web リサーチ → スライド/レポート生成
- 弱み: 短い対話

[Venice (venice.ai)]
- 強み: uncensored、プライベート相談、規制なし brainstorm
- 弱み: 学術引用

[Pika / Runway (pika.art / runwayml.com)]
- 強み: 動画生成
- 弱み: テキスト
"""


class DispatchReq(BaseModel):
    goal: str
    constraints: str = ""  # 「無料で」「学術文体で」「日本語で」など
    inputs_available: str = ""  # 既に持っている素材（PDF, データ, 過去の下書き等）
    engine: str = "claude"


@router.post("/dispatcher")
def dispatcher(req: DispatchReq):
    if not req.goal.strip():
        raise HTTPException(status_code=400, detail="goal を入力してください")

    system_prompt = f"""あなたは志柿の AI ディスパッチャー。本物の AI サービスへの「外注指示書」を作る。
Koach OS は API 経由で AI を叩くこともできるが、ここでは推奨サービスに直接ブラウザで貼り付けて使う前提。

## 利用可能な AI サービス
{AI_CATALOG}

## 出力フォーマット (MD)

### 🎯 推奨サービス (第1候補)
- **サービス名 (URL)**: 一行で理由

### 🥈 代替候補 (1〜2個)
- 一行ずつ

### 📝 貼り付け用プロンプト
\\`\\`\\`
（そのまま選んだサービスの入力欄にコピペできる完全なプロンプト。
日本語、丁寧、必要なコンテキスト全部含める、出力フォーマット指定込み）
\\`\\`\\`

### 🔧 持ち込む素材
- 何を添付/貼り付けるか具体的に

### ⚠ 注意点 / つまずきポイント
- 1〜2個

## ルール
- 推奨は1つに絞る。迷わせない
- プロンプトは「コピペ即実行」のレベルで完全に。プレースホルダ「[ここに入れる]」を残してよい部分は明示
- トーン: 簡潔、煽らない、抽象名詞「〜性」NG"""

    user_msg = f"""目的: {req.goal}
制約: {req.constraints or "(指定なし)"}
既に持っている素材: {req.inputs_available or "(なし)"}
今: {now_jst().strftime('%Y-%m-%d (%A)')}

上記目的に対して推奨 AI と外注プロンプトを出してください。"""

    engine = req.engine if req.engine in DEFAULT_MODELS else "claude"
    model = DEFAULT_MODELS[engine]

    try:
        out = call_ai(
            messages=[{"role": "user", "content": user_msg}],
            system=system_prompt,
            engine=engine,
            model=model,
            max_tokens=2500,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"dispatch failed: {e}")

    return {
        "generated_at": now_jst().isoformat(),
        "goal": req.goal,
        "engine_used": engine,
        "model_used": model,
        "brief": out,
    }
