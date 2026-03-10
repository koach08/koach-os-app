"""
Koach OS v2 — Cognitive Bias Detection
========================================
7 biases with keyword detection + 4-axis intervention level analysis.
"""

BIASES = {
    "abstraction_bias": {
        "label": "Abstraction Bias / 抽象化偏向",
        "keywords": [
            "concept", "theory", "framework", "abstract", "theoretical", "paradigm",
            "理論", "概念", "フレームワーク", "抽象", "パラダイム",
        ],
        "anti_keywords": [
            "example", "specific", "concrete", "instance", "case",
            "具体", "例えば", "実際", "ケース",
        ],
        "correction": "Require one concrete operational example.",
        "prompt_addition": "The user is being abstract. Ask for a specific, concrete example before proceeding.",
    },
    "critique_first": {
        "label": "Critique First / 批判優先",
        "keywords": [
            "problem", "issue", "wrong", "fail", "bad", "mistake", "flaw",
            "問題", "課題", "失敗", "ダメ", "間違い", "欠陥",
        ],
        "anti_keywords": [
            "solution", "improve", "better", "good", "alternative", "fix",
            "解決", "改善", "良い", "代替", "対策",
        ],
        "correction": "Generate constructive alternative alongside critique.",
        "prompt_addition": "The user is leading with criticism. Push for a constructive alternative before continuing.",
    },
    "sunk_cost": {
        "label": "Sunk Cost / 埋没費用",
        "keywords": [
            "already invested", "spent so much", "come this far", "too late to",
            "ここまでやった", "もったいない", "せっかく", "今さら",
        ],
        "anti_keywords": [],
        "correction": "Evaluate from zero-base, ignore past investment.",
        "prompt_addition": "The user shows sunk cost thinking. Ask: 'If starting from zero today, would you make this same choice?'",
    },
    "optimism_bias": {
        "label": "Optimism Bias / 楽観偏向",
        "keywords": [
            "definitely will", "surely", "no problem", "easy", "guaranteed", "certain",
            "絶対", "間違いなく", "必ず", "簡単", "大丈夫", "余裕",
        ],
        "anti_keywords": [],
        "correction": "Request worst-case scenario analysis.",
        "prompt_addition": "The user sounds overly optimistic. Ask: 'What's the worst-case scenario, and how likely is it?'",
    },
    "echo_chamber": {
        "label": "Echo Chamber / エコーチェンバー",
        "keywords": [
            "everyone agrees", "obvious", "clearly", "no one would", "common sense",
            "当然", "みんな", "明らかに", "当たり前", "誰でも",
        ],
        "anti_keywords": [],
        "correction": "Surface opposing evidence.",
        "prompt_addition": "The user assumes consensus. Surface what someone who disagrees would say.",
    },
    "fatigue_drop": {
        "label": "Fatigue Drop / 疲労低下",
        "keywords": [
            "tired", "exhausted", "too much", "overwhelmed", "burned out", "can't anymore",
            "疲れ", "しんどい", "無理", "もう", "限界", "つらい",
        ],
        "anti_keywords": [],
        "correction": "Invoke 5-year axis check.",
        "prompt_addition": "The user shows fatigue signals. Invoke the 5-year axis check before any major decisions. Suggest rest if appropriate.",
    },
    "scope_creep": {
        "label": "Scope Creep / スコープ拡大",
        "keywords": [
            "also", "additionally", "while we're at it", "and another thing", "plus",
            "ついでに", "あと", "さらに", "ついでだから", "それと",
        ],
        "anti_keywords": [],
        "correction": "Ask: What are you willing to NOT do to make room for this?",
        "prompt_addition": "The user may be expanding scope. Challenge: 'What gets dropped to make room for this?'",
    },
    "decision_fatigue": {
        "label": "Decision Fatigue / 判断疲労",
        "keywords": [
            "don't know", "can't decide", "whatever", "you decide", "any is fine",
            "either way", "I don't care", "just pick",
            "わからない", "決められない", "どれでもいい", "任せる", "なんでもいい",
            "もういい", "どうでも",
        ],
        "anti_keywords": [
            "analyze", "compare", "help me think", "分析", "比較",
        ],
        "correction": "Reduce options to 2. Provide clear recommendation with reasoning.",
        "prompt_addition": "The user shows decision fatigue. Simplify: narrow to 2 options max, give a clear recommendation, and explain the key differentiator.",
    },
    "priority_confusion": {
        "label": "Priority Confusion / 優先順位混乱",
        "keywords": [
            "everything is important", "all urgent", "need to do all",
            "can't prioritize", "everything at once", "juggling",
            "全部大事", "全部やらないと", "優先順位がつけられない",
            "どれも重要", "同時に", "全部急ぎ",
        ],
        "anti_keywords": [],
        "correction": "Apply Eisenhower matrix. Force-rank top 3.",
        "prompt_addition": "The user can't prioritize. Apply Eisenhower matrix (urgent/important), force-rank the top 3 items, and explicitly state what should be DROPPED or DELAYED. Reference the value hierarchy: Family > Students > Research > Platform > Revenue > Personal growth.",
    },
    "recency_bias": {
        "label": "Recency Bias / 近時性偏向",
        "keywords": [
            "just saw", "just read", "trending", "everyone is talking",
            "just happened", "latest", "this morning",
            "さっき見た", "今話題の", "最近の", "今朝の", "バズってる",
        ],
        "anti_keywords": [
            "pattern", "historically", "long-term", "over time",
            "パターン", "歴史的に", "長期的に",
        ],
        "correction": "Check: Is this genuinely important, or just recent/salient?",
        "prompt_addition": "The user may be reacting to something recent. Ask: 'Will this still matter in 3 months? Is this a genuine priority shift or a reaction to something new?'",
    },
    "planning_fallacy": {
        "label": "Planning Fallacy / 計画錯誤",
        "keywords": [
            "should be quick", "only take a day", "easy to do", "just a few hours",
            "simple change", "won't take long",
            "すぐ終わる", "簡単にできる", "1日あれば", "すぐできる", "たいしたことない",
        ],
        "anti_keywords": [],
        "correction": "Multiply time estimate by 2-3x. Ask about hidden dependencies.",
        "prompt_addition": "The user may be underestimating effort. Ask: 'What are the hidden dependencies? What could go wrong? Multiply your time estimate by 2.5x — does it still make sense?'",
    },
}

# ─── Intervention Level Keywords ───

L4_KEYWORDS = [
    "career", "resign", "quit", "public statement", "fire", "lawsuit", "divorce",
    "キャリア", "辞職", "退職", "公式", "大きな決断", "裁判", "離婚", "解雇",
]

L3_KEYWORDS = [
    "strategy", "decision", "compare", "tradeoff", "launch", "invest", "priority",
    "partnership", "contract", "negotiate",
    "戦略", "判断", "比較", "トレードオフ", "ローンチ", "投資", "優先", "契約", "交渉",
]

L2_KEYWORDS = [
    "plan", "structure", "organize", "outline", "prepare", "schedule", "draft",
    "計画", "構成", "整理", "準備", "スケジュール", "下書き",
]

# ─── 4-Axis Signals ───

PUBLIC_EXPOSURE_SIGNALS = [
    "student", "class", "colleague", "public", "publish", "present", "conference",
    "学生", "授業", "同僚", "公開", "発表", "学会", "出版",
]

LONG_TERM_SIGNALS = [
    "career", "tenure", "years", "long-term", "permanent", "family", "child",
    "キャリア", "長期", "将来", "家族", "子供", "永続",
]

EMOTIONAL_SIGNALS = [
    "frustrated", "angry", "excited", "anxious", "worried", "stressed", "overwhelmed",
    "happy", "thrilled",
    "イライラ", "怒り", "興奮", "不安", "心配", "ストレス", "嬉しい", "焦り",
    "tired", "exhausted", "疲れ", "しんどい", "もう", "限界",
]

VALUE_CONFLICT_SIGNALS = [
    "but family", "vs family", "sacrifice", "give up", "skip", "cancel",
    "でも家族", "犠牲", "諦め", "やめる", "キャンセル",
]


def detect_biases(text: str) -> list[dict]:
    """Return list of detected bias dicts with label, correction, and prompt_addition."""
    t = text.lower()
    found = []
    for bias_id, b in BIASES.items():
        kw_count = sum(1 for k in b["keywords"] if k in t)
        anti_count = sum(1 for k in b["anti_keywords"] if k in t) if b["anti_keywords"] else 0
        if kw_count >= 1 and anti_count == 0:
            found.append({
                "id": bias_id,
                "label": b["label"],
                "correction": b["correction"],
                "prompt_addition": b["prompt_addition"],
            })
    return found


def _count_axis_hits(text: str, signals: list[str]) -> int:
    t = text.lower()
    return sum(1 for s in signals if s in t)


def detect_intervention_level(text: str) -> tuple[str, dict]:
    """Return (level, axes_triggered) based on keyword + 4-axis analysis."""
    t = text.lower()

    # Base level from keywords
    if any(k in t for k in L4_KEYWORDS):
        base = "L4"
    elif any(k in t for k in L3_KEYWORDS):
        base = "L3"
    elif any(k in t for k in L2_KEYWORDS):
        base = "L2"
    else:
        base = "L1"

    # 4-axis analysis
    axes = {
        "public_exposure": _count_axis_hits(text, PUBLIC_EXPOSURE_SIGNALS) >= 1,
        "long_term_impact": _count_axis_hits(text, LONG_TERM_SIGNALS) >= 1,
        "emotional_signals": _count_axis_hits(text, EMOTIONAL_SIGNALS) >= 1,
        "value_conflict": _count_axis_hits(text, VALUE_CONFLICT_SIGNALS) >= 1,
    }

    triggered_count = sum(axes.values())

    # Escalation rules
    level_order = ["L1", "L2", "L3", "L4"]
    idx = level_order.index(base)

    # Public exposure + emotional signals → jump to L4
    if axes["public_exposure"] and axes["emotional_signals"]:
        return "L4", axes

    # 2+ axes triggered → escalate one level
    if triggered_count >= 2 and idx < 3:
        return level_order[idx + 1], axes

    return base, axes
