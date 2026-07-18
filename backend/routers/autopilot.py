"""
Autopilot — 24/7 自律プレップ (read-only + report)
====================================================
本人が見ていない時間に裏で走る「Spark 的」自律エージェント。

3 ジョブ:
- POST /api/autopilot/morning-prep      : 予定を見て会議準備を web 調査 → レポート
- POST /api/autopilot/email-triage       : 新着メールを 3 分類トリアージ → レポート
- POST /api/autopilot/backlog-progress   : 未処理バックログを調べ物/下書きで前進 → レポート
- POST /api/autopilot/run-all            : 上記 3 つを順に実行 (cron 用)

ガードレール (重要):
- 使える道具は【読み取り専用】のみ (web / 検索 / カレンダー閲覧 / 過去データ検索 / マルチモーダル解析)。
- create_event / add_backlog / save_decision 等の【実データ書き込み】は一切与えない。
- 成果物は memo (source=autopilot) に保存 + Resend メール (設定時のみ)。実データは変更しない。
- 各 run は自分の結論を autopilot_state.jsonl (自分専用の progress artifact) に残し、次回はそれを読んで
  続きから動く。これは autopilot 自身の作業台帳であり、decisions / calendar 等の実データではない。

Auth: header `X-Cron-Token` が env CRON_TOKEN と一致しないと 401 (cron._check_token を再利用)。
Model: コスト配慮でデフォルト claude-haiku-4-5 (email_watch の教訓)。query `model` で上書き可。
"""

from __future__ import annotations

import json
import os
import urllib.request

from fastapi import APIRouter, Header

from data_manager import (
    DATA_DIR,
    MEMOS_FILE,
    append_jsonl,
    generate_id,
    get_secret,
    now_jst,
    read_jsonl,
    timestamp_jst,
)
from routers.cron import _check_token

# 既存エージェントのツール群を read-only に絞って再利用 (agent.py 本体は無改変)
from routers.agent import TOOL_SCHEMA, TOOL_FUNCS, SYSTEM_PROMPT as _AGENT_SYSTEM

router = APIRouter()

# ─── read-only ツール許可リスト (書き込み系は意図的に除外) ───
READ_ONLY_TOOLS = {
    "web_search",
    "web_fetch",
    "search_my_data",
    "list_calendar",
    "analyze_image",
    "analyze_pdf",
    "analyze_video_url",
    "analyze_audio",
}
_RO_SCHEMA = [t for t in TOOL_SCHEMA if t.get("name") in READ_ONLY_TOOLS]
_RO_FUNCS = {k: v for k, v in TOOL_FUNCS.items() if k in READ_ONLY_TOOLS}

DEFAULT_AUTOPILOT_MODEL = "claude-haiku-4-5"

AUTOPILOT_SYSTEM = _AGENT_SYSTEM + """

## 自律モード (Autopilot)
- あなたは今、本人が見ていない時間に裏で自走している。対話相手はいない。質問で止まらず、手元の道具で調べて結論まで出す。
- 使える道具は【読み取り専用】のみ (web / 検索 / カレンダー閲覧 / 過去データ検索 / マルチモーダル解析)。カレンダーやバックログへの書き込みはできない。
- 提案は「提案:」として文章で書くだけ。勝手に実行しない (そもそもできない)。
- 最終出力は本人が後で読むレポート。結論から、箇条書き中心、200-500字程度。事実は道具で確認してから書く。
- 最後に『次の一手』を 1 つだけ。
"""


# ─── progress artifact (前回結論の state 化) ───
# Anthropic の long-running agent harness の「progress artifact」パターン。
# 各ジョブが自分の前回 run の結論を残し、次回はそれを読んで続きから動く (繰り返しを避け、前進を追う)。
# append-only + job ごと latest-wins。read-only 方針は不変 (自分の作業台帳を持つだけ、実データは変えない)。

AUTOPILOT_STATE_FILE = DATA_DIR / "autopilot_state.jsonl"


def _load_prior_state(job: str) -> dict | None:
    """直近の同ジョブ run の結論を返す。無ければ None。"""
    latest = None
    try:
        for e in read_jsonl(AUTOPILOT_STATE_FILE):
            if e.get("job") == job:
                latest = e
    except Exception:
        return None
    return latest


def _save_state(job: str, report: str) -> None:
    """今回の結論を progress artifact として残す。次回 run が読んで続きから動く。"""
    try:
        append_jsonl(AUTOPILOT_STATE_FILE, {
            "job": job,
            "date": now_jst().strftime("%Y-%m-%d"),
            "at": now_jst().strftime("%m/%d %H:%M"),
            "summary": (report or "")[:1500],
            "created_at": timestamp_jst(),
        })
    except Exception:
        pass


def _prior_context_block(job: str) -> str:
    """mission に差し込む『前回の結論』ブロック。初回や欠損時は空文字。"""
    prior = _load_prior_state(job)
    if not prior or not prior.get("summary", "").strip():
        return ""
    return (
        f"\n\n## 前回 ({prior.get('at','')}) の自分自身の結論 (progress artifact)\n"
        f"{prior['summary']}\n"
        "→ 今回はこれを踏まえる。同じ話を繰り返さず、前進した点・変わった点・積み残しに触れる。"
        "前回の『次の一手』が実行されたかも意識する。\n"
    )


def _run_readonly_agent(mission: str, max_steps: int = 5, model: str = DEFAULT_AUTOPILOT_MODEL) -> dict:
    """read-only ツールだけを与えた小さな自律ループ。agent_chat のロジックを隔離複製。"""
    import anthropic

    api_key = get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        return {"final": "(ANTHROPIC_API_KEY not set)", "tool_calls": 0, "model": model}
    client = anthropic.Anthropic(api_key=api_key)

    messages: list[dict] = [{"role": "user", "content": mission}]
    final_text = ""
    tool_calls = 0

    for _ in range(max_steps):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=3000,
                system=AUTOPILOT_SYSTEM,
                tools=_RO_SCHEMA,
                messages=messages,
            )
        except Exception as e:
            return {"final": f"(Claude error: {e})", "tool_calls": tool_calls, "model": model}

        text_parts: list[str] = []
        tool_uses: list[dict] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append({"id": block.id, "name": block.name, "input": block.input})
        text_now = "".join(text_parts).strip()

        if resp.stop_reason == "tool_use" and tool_uses:
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for tu in tool_uses:
                fn = _RO_FUNCS.get(tu["name"])
                if not fn:
                    # 書き込み系を呼ぼうとしたら拒否 (二重の安全網)
                    out = f"(tool {tu['name']} は autopilot では無効。読み取り専用のみ)"
                else:
                    tool_calls += 1
                    try:
                        out = str(fn(tu["input"]))[:6000]
                    except Exception as e:
                        out = f"(tool {tu['name']} error: {e})"
                results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": out})
            messages.append({"role": "user", "content": results})
            continue

        final_text = text_now
        break
    else:
        final_text = final_text or "(max_steps 到達)"

    return {"final": final_text, "tool_calls": tool_calls, "model": model}


def _save_report_memo(job: str, text: str) -> str:
    entry = {
        "id": generate_id("memo"),
        "content": f"🤖 [autopilot:{job}] {now_jst().strftime('%m/%d %H:%M')}\n\n{text}",
        "color": "blue",
        "pinned": False,
        "created_at": timestamp_jst(),
        "created_at_ts": int(now_jst().timestamp() * 1000),
        "updated_at": timestamp_jst(),
        "source": "autopilot",
        "autopilot_job": job,
    }
    append_jsonl(MEMOS_FILE, entry)
    return entry["id"]


def _send_report_email(subject: str, text: str) -> bool:
    """Resend で本人にメール (cron.notify_brief と同じ経路)。未設定ならスキップ。"""
    api_key = os.environ.get("RESEND_API_KEY", "")
    to_email = os.environ.get("NOTIFY_EMAIL", "")
    from_email = os.environ.get("NOTIFY_FROM", "Koach OS <onboarding@resend.dev>")
    if not api_key or not to_email:
        return False
    payload = json.dumps({
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "text": text,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "koach-os-autopilot/1.0 (+https://koach-os.vercel.app)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return 200 <= res.status < 300
    except Exception:
        return False


def _finish(job: str, title: str, out: dict) -> dict:
    text = out.get("final", "")
    memo_id = _save_report_memo(job, text)
    _save_state(job, text)  # 次回 run が読む progress artifact を更新
    emailed = _send_report_email(f"🤖 Autopilot: {title} {now_jst().strftime('%m/%d')}", text)
    return {
        "job": job,
        "report": text,
        "memo_id": memo_id,
        "emailed": emailed,
        "tool_calls": out.get("tool_calls", 0),
        "model_used": out.get("model", ""),
        "generated_at": now_jst().isoformat(),
    }


# ─── 各ジョブ本体 (token チェックなし。route か run-all が先にチェック) ───

def _job_morning_prep(days_ahead: int, model: str) -> dict:
    try:
        from routers.agent import tool_list_calendar
        cal = tool_list_calendar(days_ahead)
    except Exception as e:
        cal = f"(カレンダー取得失敗: {e})"
    mission = (
        f"向こう {days_ahead} 日の予定に対する朝の準備レポートを作る。\n\n"
        f"## 現在の予定\n{cal}\n\n"
        "各予定について: 相手や議題が読み取れるものは search_my_data で過去の関連 memo/decision を確認し、"
        "必要なら web_search / web_fetch で最新の背景を調べ、準備すべき点を 1-2 個ずつ挙げる。"
        "予定が無ければ『予定なし。空き時間の使い道』を 1 つだけ提案する。"
        + _prior_context_block("morning-prep")
    )
    return _finish("morning-prep", "朝の自律プレップ", _run_readonly_agent(mission, max_steps=6, model=model))


def _job_email_triage(days: int, limit: int, model: str) -> dict:
    emails: list[dict] = []
    gather_err = ""
    try:
        from routers.gmail_calendar import gmail_recent
        data = gmail_recent(days=days, limit=limit, slot=0)
        emails = data.get("emails", []) if isinstance(data, dict) else []
    except Exception as e:
        gather_err = str(e)

    if not emails:
        text = f"新着メールなし (直近 {days} 日)。" + (f" 取得エラー: {gather_err}" if gather_err else "")
        return _finish("email-triage", "メール自律トリアージ",
                       {"final": text, "tool_calls": 0, "model": model})

    digest = "\n".join(
        f"- from={str(e.get('from',''))[:60]} | subj={str(e.get('subject',''))[:80]} | "
        f"{str(e.get('snippet', e.get('body','')))[:120]}"
        for e in emails[:limit]
    )
    mission = (
        "以下の新着メールをトリアージする。実際の返信や予定追加はしない (できない)。\n\n"
        f"## 新着メール ({len(emails)} 件)\n{digest}\n\n"
        "3 分類で整理: 【要対応 (締切/依頼)】【予定候補 (日時を含む)】【無視可】。"
        "各メールを 1 行で。相手の過去文脈が要るものは search_my_data で確認。"
        "最後に『今日まず着手すべき 1 通』を提案。"
        + _prior_context_block("email-triage")
    )
    return _finish("email-triage", "メール自律トリアージ", _run_readonly_agent(mission, max_steps=5, model=model))


def _job_backlog_progress(max_items: int, model: str) -> dict:
    pending: list[dict] = []
    try:
        from routers.productivity import _load_backlog
        backlog = _load_backlog()
        done = {"done", "archived", "completed", "resolved", "cancelled"}
        pending = [
            b for b in backlog
            if str(b.get("status", "")).lower() not in done and not b.get("done")
        ][:max_items]
    except Exception as e:
        return _finish("backlog-progress", "バックログ自律消化",
                       {"final": f"(バックログ取得失敗: {e})", "tool_calls": 0, "model": model})

    if not pending:
        return _finish("backlog-progress", "バックログ自律消化",
                       {"final": "未処理のバックログなし。", "tool_calls": 0, "model": model})

    items = "\n".join(
        f"- {str(b.get('title', b.get('text','')))[:100]} "
        f"(cat={b.get('category','')}, note={str(b.get('notes',''))[:80]})"
        for b in pending
    )
    mission = (
        "以下の未処理バックログのうち、調べ物や下書きで前進できるものを裏で進める。実データ書き込みはしない。\n\n"
        f"## 未処理バックログ (上位 {len(pending)} 件)\n{items}\n\n"
        "全部やろうとせず、最も前進させやすい 1-2 件に集中。"
        "web_search / web_fetch で必要な情報を集め、次に本人がやる作業を 1-2 手まで具体化する "
        "(下書き文・箇条書き・参考リンク)。"
        + _prior_context_block("backlog-progress")
    )
    return _finish("backlog-progress", "バックログ自律消化", _run_readonly_agent(mission, max_steps=6, model=model))


# ─── Brain Health Check (週次・二段) ───
# Karpathy 方式の Step 6「LLM Health Check」を koach-os ネイティブで実装。
# 蓄積した知識 (decisions/failures/work_log/memos/heuristics/experiences) を週1でフル走査し、
# 矛盾・欠落・重複・数値不整合・新規候補を洗い出す。「追加と整理の両輪」で脳が腐るのを防ぐ装置。
# 二段: Gemini 3.1 Pro で長文コンテキストを一気に読む → Opus 4.8 で有力 issue を精査し修正案まで。
# スコープは【報告 + 修正案の提案】まで。実データへの自動書き込みはしない (read-only 方針を維持)。

BRAIN_SCAN_ENGINE = "gemini"
BRAIN_SCAN_MODEL = "gemini-3.1-pro-preview"
BRAIN_REFINE_ENGINE = "claude"
BRAIN_REFINE_MODEL = "claude-opus-4-8"


def _gather_brain_corpus(max_chars: int = 120_000) -> tuple[str, dict]:
    """koach-os の永続知識を 1 本のテキストに束ねる。source=autopilot の memo は自己言及を避け除外。"""
    from data_manager import (
        read_jsonl, read_yaml,
        DECISIONS_FILE, FAILURES_FILE, MEMOS_FILE, EXPERIENCES_FILE, HEURISTICS_FILE,
    )

    sections: list[str] = []
    counts: dict[str, int] = {}
    truncated = False

    def _add(name: str, entries: list, fmt) -> None:
        nonlocal truncated
        counts[name] = len(entries)
        if not entries:
            return
        body = "\n".join(fmt(e) for e in entries)
        sections.append(f"## {name} ({len(entries)}件)\n{body}")

    try:
        decisions = read_jsonl(DECISIONS_FILE)
        _add("decisions", decisions, lambda d:
             f"- [{str(d.get('timestamp',''))[:10]}] "
             f"{d.get('title') or d.get('decision','')}: {str(d.get('reasoning',''))[:220]}")
    except Exception:
        pass
    try:
        failures = read_jsonl(FAILURES_FILE)
        _add("failures", failures, lambda f:
             f"- {f.get('what') or f.get('what_happened','')}: "
             f"学び={str(f.get('lesson') or f.get('prevention',''))[:180]}")
    except Exception:
        pass
    try:
        from routers.work_log import _materialize
        wl = sorted(_materialize().values(), key=lambda w: w.get("date", ""), reverse=True)
        _add("work_log", wl, lambda w:
             f"- [{w.get('date','')}] [{w.get('category','')}] {w.get('title','')} "
             f"(engine={w.get('engine','')}) {str(w.get('outcome',''))[:120]}")
    except Exception:
        pass
    try:
        # 自分の生成物 (source=autopilot) は除外。走り書きの生 memo だけを対象に。
        memos = [m for m in read_jsonl(MEMOS_FILE) if m.get("source") != "autopilot"]
        _add("memos", memos, lambda m: f"- {str(m.get('content',''))[:200]}")
    except Exception:
        pass
    try:
        experiences = read_jsonl(EXPERIENCES_FILE)
        _add("experiences", experiences, lambda e: f"- {str(e.get('content') or e.get('experience',''))[:200]}")
    except Exception:
        pass
    try:
        heur = read_yaml(HEURISTICS_FILE)
        if heur:
            counts["heuristics"] = len(heur) if isinstance(heur, (list, dict)) else 1
            sections.append("## heuristics\n" + json.dumps(heur, ensure_ascii=False)[:4000])
    except Exception:
        pass

    corpus = "\n\n".join(sections)
    if len(corpus) > max_chars:
        corpus = corpus[:max_chars]
        truncated = True
    counts["_truncated"] = truncated
    counts["_chars"] = len(corpus)
    return corpus, counts


def _job_brain_health_check(
    scan_engine: str = BRAIN_SCAN_ENGINE, scan_model: str = BRAIN_SCAN_MODEL,
    refine_engine: str = BRAIN_REFINE_ENGINE, refine_model: str = BRAIN_REFINE_MODEL,
) -> dict:
    from router import call_ai

    corpus, counts = _gather_brain_corpus()
    total = sum(v for k, v in counts.items() if not k.startswith("_"))
    if not corpus.strip() or total == 0:
        return _finish("brain-health-check", "脳の週次ヘルスチェック",
                       {"final": "知識ベースがまだ空です。decisions/work_log/memos が溜まってから効きます。",
                        "tool_calls": 0, "model": f"{scan_engine}+{refine_engine}"})

    # ─ 一段目: 長文コンテキストで全走査し issue を洗い出す ─
    scan_system = (
        "あなたは志柿の知識ベースの監査役です。以下は koach-os に蓄積された永続知識 "
        "(decisions/failures/work_log/memos/experiences/heuristics)。全体を読み、次の5観点で issue を"
        "洗い出してください。お世辞や褒めは書かない。盲点を突く。\n"
        "(a) 矛盾: 同じ対象について食い違う記述/数値\n"
        "(b) 欠落: 3回以上言及されるのに整理された decision/まとめが無い概念\n"
        "(c) 重複: ほぼ同じ内容が複数あり統合すべきもの\n"
        "(d) 数値不整合/陳腐化: 根拠の古い数値、出典切れ\n"
        "(e) 新規候補: 1件立てる価値のある論点\n"
        "各 issue は必ず『どのエントリが根拠か』を1行添える。網羅的に。"
    )
    try:
        scan_out = call_ai(
            messages=[{"role": "user", "content": f"# 知識ベース\n{corpus}"}],
            system=scan_system, engine=scan_engine, model=scan_model, max_tokens=4000,
        )
    except Exception as e:
        scan_out = f"(一次スキャン失敗: {e})"

    # ─ 二段目: 有力 issue に絞り、修正案まで出す (適用はしない) ─
    refine_system = (
        "あなたは志柿の参謀です。一次監査が出した issue 一覧と元コーパスを踏まえ、"
        "価値の高いものを上位5〜8件に絞り、各々に具体的な修正案まで付けます。\n"
        "- 統合案: 統合後の1行定義を書く\n"
        "- 新規候補: 見出し構成 (箇条書き) を書く\n"
        "- 矛盾/陳腐化: どちらが正か、判断できなければ本人への確認質問を1つ\n"
        "実データへの書き込みはしない (提案のみ)。結論から。です/ます。抽象名詞「〜性」「重要性」禁止。"
        "一人称は「自分」。冒頭に issue 件数と、今週まず1件やるならどれかを書く。"
        "前回の監査結論があれば、そこで挙げた issue が解消したか/積み残したかにも触れる。"
    )
    refine_input = (
        f"# 一次監査の issue 一覧\n{scan_out}\n\n"
        f"# 元コーパス (参照用)\n{corpus[:60000]}"
        + _prior_context_block("brain-health-check")
    )
    try:
        refine_out = call_ai(
            messages=[{"role": "user", "content": refine_input}],
            system=refine_system, engine=refine_engine, model=refine_model, max_tokens=2500,
        )
    except Exception as e:
        refine_out = f"(精査失敗: {e})\n\n一次スキャン結果:\n{scan_out}"

    header = (
        f"走査: " + ", ".join(f"{k}={v}" for k, v in counts.items() if not k.startswith("_"))
        + f" / {counts.get('_chars', 0)}字"
        + (" ※コーパス上限で一部truncate" if counts.get("_truncated") else "")
        + f"\nengine: scan={scan_engine}:{scan_model} → refine={refine_engine}:{refine_model}\n"
        + "─" * 20 + "\n"
    )
    return _finish("brain-health-check", "脳の週次ヘルスチェック",
                   {"final": header + refine_out, "tool_calls": 0,
                    "model": f"{scan_model}+{refine_model}"})


# ─── Consolidation / Compile (週次・二段) ───
# Karpathy 方式 Step 2「compile」+ Anthropic の "Dreaming"(過去ログを構造化知識に一括統合) を自前実装。
# Brain Health Check が「欠落」を"見つける"のに対し、こちらは生の memos/work_log/failures を読み、
# 構造化して残す価値のある知識を decisions 形式の【下書き】として"書く"。両輪で自己維持する脳になる。
# スコープは【提案のみ】: 下書きを memo/メールに出すだけで decisions.jsonl には自動書き込みしない。
# 昇格は本人が判断 (承認導線は次段)。read-only 方針を維持。


def _extract_json_array(text: str) -> list | None:
    """LLM 出力から JSON 配列を寛容に取り出す。コードフェンス除去 + 最初の[〜最後の]。"""
    import re
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?", "", t).strip()
    t = re.sub(r"```$", "", t).strip()
    start, end = t.find("["), t.rfind("]")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        val = json.loads(t[start:end + 1])
        return val if isinstance(val, list) else None
    except Exception:
        return None


def _gather_raw_and_structured(max_chars: int = 100_000) -> tuple[str, str, dict]:
    """生シグナル(未構造)と既存の構造化知識を分けて返す。既存を渡すのは重複提案を避けるため。"""
    from data_manager import (
        read_jsonl, read_yaml,
        DECISIONS_FILE, FAILURES_FILE, MEMOS_FILE, HEURISTICS_FILE,
    )

    counts: dict[str, int] = {}
    raw_sections: list[str] = []

    try:
        memos = [m for m in read_jsonl(MEMOS_FILE) if m.get("source") != "autopilot"]
        counts["memos"] = len(memos)
        if memos:
            raw_sections.append(
                "## memos (走り書き)\n"
                + "\n".join(f"- {str(m.get('content',''))[:220]}" for m in memos)
            )
    except Exception:
        pass
    try:
        from routers.work_log import _materialize
        wl = sorted(_materialize().values(), key=lambda w: w.get("date", ""), reverse=True)
        counts["work_log"] = len(wl)
        if wl:
            raw_sections.append(
                "## work_log (実績)\n"
                + "\n".join(
                    f"- [{w.get('date','')}] [{w.get('category','')}] {w.get('title','')} "
                    f"(engine={w.get('engine','')}) {str(w.get('outcome',''))[:120]}" for w in wl
                )
            )
    except Exception:
        pass
    try:
        failures = read_jsonl(FAILURES_FILE)
        counts["failures"] = len(failures)
        if failures:
            raw_sections.append(
                "## failures\n"
                + "\n".join(
                    f"- {f.get('what') or f.get('what_happened','')}: "
                    f"学び={str(f.get('lesson') or f.get('prevention',''))[:150]}" for f in failures
                )
            )
    except Exception:
        pass

    # 既存の構造化知識 (重複回避用) — タイトル/要約だけで十分
    existing_lines: list[str] = []
    try:
        decisions = read_jsonl(DECISIONS_FILE)
        counts["existing_decisions"] = len(decisions)
        for d in decisions:
            existing_lines.append(f"- {d.get('title') or d.get('decision','')}")
    except Exception:
        pass
    try:
        heur = read_yaml(HEURISTICS_FILE)
        if heur:
            existing_lines.append("(heuristics) " + json.dumps(heur, ensure_ascii=False)[:1500])
    except Exception:
        pass

    raw = "\n\n".join(raw_sections)[:max_chars]
    existing = "\n".join(existing_lines)[:8000] or "(既存の構造化知識なし)"
    counts["_raw_chars"] = len(raw)
    return raw, existing, counts


def _job_consolidate(
    scan_engine: str = BRAIN_SCAN_ENGINE, scan_model: str = BRAIN_SCAN_MODEL,
    refine_engine: str = BRAIN_REFINE_ENGINE, refine_model: str = BRAIN_REFINE_MODEL,
) -> dict:
    from router import call_ai

    raw, existing, counts = _gather_raw_and_structured()
    raw_total = counts.get("memos", 0) + counts.get("work_log", 0) + counts.get("failures", 0)
    if not raw.strip() or raw_total == 0:
        return _finish("consolidate", "知識の構造化 (compile)",
                       {"final": "構造化できる生シグナルがまだありません。memos/work_log が溜まってから効きます。",
                        "tool_calls": 0, "model": f"{scan_engine}+{refine_engine}"})

    # ─ 一段目: 生シグナルから「構造化する価値のある塊」を抽出 (既存と重複しないもの) ─
    scan_system = (
        "あなたは志柿の知識整理係です。以下は未構造の生シグナル(memos/work_log/failures)と、"
        "既に構造化ずみの知識一覧です。生シグナルを読み、繰り返し現れる/後で参照価値のある塊で、"
        "『既存の構造化知識にまだ無いもの』だけを抽出してください。各塊について:\n"
        "- 何についての知識か (1行)\n- 根拠となる生シグナル (どのエントリ)\n"
        "- decision(意思決定) か concept(概念まとめ) か failure(教訓) のどれとして残すべきか\n"
        "既存と重複するものは挙げない。お世辞は書かない。網羅より価値順。"
    )
    scan_input = (
        f"# 生シグナル\n{raw}\n\n"
        f"# 既に構造化ずみ (これと重複するものは除外)\n{existing}"
        + _prior_context_block("consolidate")
    )
    try:
        scan_out = call_ai(
            messages=[{"role": "user", "content": scan_input}],
            system=scan_system, engine=scan_engine, model=scan_model, max_tokens=3500,
        )
    except Exception as e:
        scan_out = f"(一次抽出失敗: {e})"

    # ─ 二段目: 上位を decisions 形式の構造化下書きに整形。JSON で受けてレビューキューに保存 ─
    refine_system = (
        "あなたは志柿の参謀です。一次抽出の塊のうち価値の高い上位3〜6件を、そのまま decisions に"
        "昇格できる構造化下書きにします。出力は【厳密な JSON 配列のみ】。前置き・説明・コードフェンスを"
        "一切書かないでください。各要素は次のキーを持ちます:\n"
        '{"kind":"decision|concept|failure", "title":"短い見出し", "context":"状況・背景(1-2行)", '
        '"options":["検討した選択肢",...], "chosen":"選んだ/現状の結論", '
        '"reasoning":"なぜそうか。根拠の生シグナルに触れる", "domain":"personal|research|platform|revenue|teaching"}\n'
        "文体は です/ます、一人称は「自分」、抽象名詞「〜性」「重要性」は使わない。options が無ければ空配列。"
    )
    refine_input = f"# 一次抽出\n{scan_out}\n\n# 生シグナル(参照用)\n{raw[:50000]}"
    parsed: list[dict] | None = None
    refine_raw = ""
    try:
        refine_raw = call_ai(
            messages=[{"role": "user", "content": refine_input}],
            system=refine_system, engine=refine_engine, model=refine_model, max_tokens=3000,
        )
        parsed = _extract_json_array(refine_raw)
    except Exception as e:
        refine_raw = f"(整形失敗: {e})\n\n一次抽出:\n{scan_out}"

    # レビューキューへ保存 (dedup は add_proposal 側)。実 decisions には書かない。
    saved: list[dict] = []
    parse_ok = isinstance(parsed, list) and len(parsed) > 0
    if parse_ok:
        from routers.proposals import add_proposal
        for item in parsed:
            if not isinstance(item, dict):
                continue
            rec = add_proposal(item)
            if rec:
                saved.append(rec)

    header = (
        "生シグナル走査: "
        + ", ".join(f"{k}={v}" for k, v in counts.items() if not k.startswith("_"))
        + f" / raw {counts.get('_raw_chars', 0)}字\n"
        + f"engine: scan={scan_engine}:{scan_model} → refine={refine_engine}:{refine_model}\n"
        + "─" * 20 + "\n"
    )

    if parse_ok:
        n_new = len(saved)
        n_dup = len(parsed) - n_new
        body_lines = [
            f"昇格候補を {n_new} 件 レビューキューに追加しました"
            + (f" (重複 {n_dup} 件はスキップ)" if n_dup > 0 else "") + "。",
            "承認は Koach OS の『📥 承認待ち』(/proposals) から 1 タップで decisions に昇格できます。",
            "",
        ]
        for i, p in enumerate(saved, 1):
            body_lines.append(f"### 提案{i}: {p['title']}  [{p['kind']}/{p['domain']}]")
            if p.get("context"):
                body_lines.append(f"- context: {p['context']}")
            if p.get("options"):
                body_lines.append("- options: " + " / ".join(p["options"]))
            if p.get("chosen"):
                body_lines.append(f"- chosen: {p['chosen']}")
            if p.get("reasoning"):
                body_lines.append(f"- reasoning: {p['reasoning']}")
            body_lines.append("")
        final = header + "\n".join(body_lines)
    else:
        final = (
            header
            + "※ 構造化(JSON)の解釈に失敗したため、レビューキューには入れていません。"
            "一次抽出と生成結果を貼ります。\n\n" + (refine_raw or "(空)")
        )

    return _finish("consolidate", "知識の構造化 (compile)",
                   {"final": final, "tool_calls": 0, "model": f"{scan_model}+{refine_model}"})


# ─── routes ───

@router.post("/autopilot/morning-prep")
def morning_prep(
    days_ahead: int = 1,
    model: str = DEFAULT_AUTOPILOT_MODEL,
    x_cron_token: str | None = Header(None, alias="X-Cron-Token"),
):
    _check_token(x_cron_token)
    return _job_morning_prep(days_ahead, model)


@router.post("/autopilot/email-triage")
def email_triage(
    days: int = 1,
    limit: int = 30,
    model: str = DEFAULT_AUTOPILOT_MODEL,
    x_cron_token: str | None = Header(None, alias="X-Cron-Token"),
):
    _check_token(x_cron_token)
    return _job_email_triage(days, limit, model)


@router.post("/autopilot/backlog-progress")
def backlog_progress(
    max_items: int = 3,
    model: str = DEFAULT_AUTOPILOT_MODEL,
    x_cron_token: str | None = Header(None, alias="X-Cron-Token"),
):
    _check_token(x_cron_token)
    return _job_backlog_progress(max_items, model)


@router.post("/autopilot/brain-health-check")
def brain_health_check(
    scan_engine: str = BRAIN_SCAN_ENGINE,
    scan_model: str = BRAIN_SCAN_MODEL,
    refine_engine: str = BRAIN_REFINE_ENGINE,
    refine_model: str = BRAIN_REFINE_MODEL,
    x_cron_token: str | None = Header(None, alias="X-Cron-Token"),
):
    """週次: 知識ベースを二段 (Gemini 全走査 → Opus 精査+修正案) で監査。報告のみ、実データ不変。"""
    _check_token(x_cron_token)
    return _job_brain_health_check(scan_engine, scan_model, refine_engine, refine_model)


@router.post("/autopilot/consolidate")
def consolidate(
    scan_engine: str = BRAIN_SCAN_ENGINE,
    scan_model: str = BRAIN_SCAN_MODEL,
    refine_engine: str = BRAIN_REFINE_ENGINE,
    refine_model: str = BRAIN_REFINE_MODEL,
    x_cron_token: str | None = Header(None, alias="X-Cron-Token"),
):
    """週次: 生シグナル (memos/work_log/failures) を二段で構造化下書きに compile。提案のみ、昇格は本人。"""
    _check_token(x_cron_token)
    return _job_consolidate(scan_engine, scan_model, refine_engine, refine_model)


@router.post("/autopilot/run-all")
def run_all(
    model: str = DEFAULT_AUTOPILOT_MODEL,
    x_cron_token: str | None = Header(None, alias="X-Cron-Token"),
):
    """cron 用: 3 ジョブを順に実行。1 つ失敗しても他は続行。"""
    _check_token(x_cron_token)
    results = {}
    for name, fn in (
        ("morning-prep", lambda: _job_morning_prep(1, model)),
        ("email-triage", lambda: _job_email_triage(1, 30, model)),
        ("backlog-progress", lambda: _job_backlog_progress(3, model)),
    ):
        try:
            results[name] = fn()
        except Exception as e:
            results[name] = {"job": name, "error": str(e)}
    return {"ran": list(results.keys()), "results": results, "generated_at": now_jst().isoformat()}
