"""
Koach OS v2 — AI Routing Engine
=================================
Routes between Claude (reflective) and GPT (execution).
Unified call_ai() handles both providers.
"""

from data_manager import get_secret

# ─── Routing Table ───

ROUTING_TABLE = {
    # Reflective tasks → Claude
    "decision_analysis": "claude",
    "strategic_planning": "claude",
    "writing_feedback": "claude",
    "counterpoint_generation": "claude",
    "weekly_review": "claude",
    "five_year_check": "claude",
    "self_reflection": "claude",
    "research_discussion": "claude",

    # Execution tasks → GPT
    "quick_task": "gpt",
    "code_debugging": "gpt",
    "email_drafting": "gpt",
    "summarization": "gpt",
    "translation": "gpt",
    "data_processing": "gpt",

    # Learning tasks → Claude
    "style_analysis": "claude",
    "pattern_extraction": "claude",
}

# Task type detection keywords
TASK_TYPE_KEYWORDS = {
    "decision_analysis": [
        "decide", "decision", "choose", "which", "should I",
        "判断", "決め", "選ぶ", "どっち", "どちら",
    ],
    "strategic_planning": [
        "strategy", "plan", "roadmap", "long-term", "priority",
        "戦略", "計画", "ロードマップ", "優先",
    ],
    "writing_feedback": [
        "review my", "draft", "writing", "paper", "edit",
        "添削", "下書き", "文章", "論文", "レビュー",
    ],
    "self_reflection": [
        "reflect", "why did I", "pattern", "habit",
        "振り返", "なぜ", "パターン", "習慣",
    ],
    "quick_task": [
        "quickly", "just", "simple", "fast",
        "ちょっと", "簡単に", "すぐ", "さっと",
    ],
    "code_debugging": [
        "bug", "error", "fix", "debug", "code",
        "バグ", "エラー", "修正", "コード",
    ],
    "email_drafting": [
        "email", "mail", "message to", "draft a",
        "メール", "連絡", "文面",
    ],
    "summarization": [
        "summarize", "summary", "tldr", "key points",
        "要約", "まとめ", "ポイント",
    ],
    "translation": [
        "translate", "翻訳", "英訳", "和訳",
    ],
    "research_discussion": [
        "research", "paper", "study", "methodology", "hypothesis",
        "研究", "論文", "方法論", "仮説",
    ],
}

# Default models per engine
DEFAULT_MODELS = {
    "claude": "claude-opus-4-6",
    "gpt": "gpt-5.4",
}

# Available models for settings UI
AVAILABLE_MODELS = {
    "claude": [
        ("claude-opus-4-6", "Claude Opus 4.6 (最高性能 $5/$25)"),
        ("claude-sonnet-4-6", "Claude Sonnet 4.6 (バランス $3/$15)"),
        ("claude-haiku-4-5", "Claude Haiku 4.5 (高速・低コスト $1/$5)"),
    ],
    "gpt": [
        ("gpt-5.4", "GPT-5.4 (最新・最高性能 $2.50/$15)"),
        ("gpt-5.2", "GPT-5.2 (コード・エージェント向け $1.75/$14)"),
        ("gpt-5", "GPT-5 (コスパ良好 $1.25/$10)"),
        ("gpt-4.1", "GPT-4.1 (非推論・安定 $2.00/$8)"),
        ("gpt-4.1-mini", "GPT-4.1 Mini (低コスト $0.40/$1.60)"),
        ("gpt-4.1-nano", "GPT-4.1 Nano (超低コスト $0.10/$0.40)"),
    ],
}


def detect_task_type(user_input: str, domain: str) -> str:
    """Analyze user input to determine task type."""
    t = user_input.lower()

    # Score each task type
    scores = {}
    for task_type, keywords in TASK_TYPE_KEYWORDS.items():
        score = sum(1 for k in keywords if k in t)
        if score > 0:
            scores[task_type] = score

    if scores:
        return max(scores, key=scores.get)

    # Domain-based fallback
    domain_defaults = {
        "teaching": "quick_task",
        "research": "research_discussion",
        "platform": "code_debugging",
        "revenue": "strategic_planning",
        "personal": "self_reflection",
        "business": "strategic_planning",
    }
    return domain_defaults.get(domain, "quick_task")


def route(task_type: str, override: str | None = None, custom_models: dict | None = None) -> dict:
    """Return routing decision: {engine, model, reason}."""
    if override:
        engine = override
        reason = "user_override"
    else:
        engine = ROUTING_TABLE.get(task_type, "claude")
        reason = f"routing_table:{task_type}"

    models = custom_models or DEFAULT_MODELS
    model = models.get(engine, DEFAULT_MODELS[engine])

    return {
        "engine": engine,
        "model": model,
        "reason": reason,
    }


def call_ai(messages: list[dict], system: str, engine: str, model: str, max_tokens: int = 2048) -> str:
    """Unified API call for both Anthropic and OpenAI."""
    try:
        if engine == "claude":
            return _call_claude(messages, system, model, max_tokens)
        else:
            return _call_gpt(messages, system, model, max_tokens)
    except Exception as e:
        # Fallback: try the other engine
        try:
            if engine == "claude":
                fallback_model = DEFAULT_MODELS["gpt"]
                return _call_gpt(messages, system, fallback_model, max_tokens)
            else:
                fallback_model = DEFAULT_MODELS["claude"]
                return _call_claude(messages, system, fallback_model, max_tokens)
        except Exception as e2:
            return f"❌ Both APIs failed.\nPrimary: {e}\nFallback: {e2}"


def _call_claude(messages: list[dict], system: str, model: str, max_tokens: int = 2048) -> str:
    """Call Anthropic Claude API."""
    import anthropic
    from data_manager import log_api_cost

    api_key = get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not configured")

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )

    try:
        log_api_cost(model, resp.usage.input_tokens, resp.usage.output_tokens, "chat")
    except Exception:
        pass

    return resp.content[0].text


def _call_gpt(messages: list[dict], system: str, model: str, max_tokens: int = 2048) -> str:
    """Call OpenAI GPT API."""
    import openai
    from data_manager import log_api_cost

    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured")

    client = openai.OpenAI(api_key=api_key)
    oai_messages = [{"role": "system", "content": system}] + messages
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=oai_messages,
    )

    try:
        if resp.usage:
            log_api_cost(model, resp.usage.prompt_tokens, resp.usage.completion_tokens, "chat")
    except Exception:
        pass

    return resp.choices[0].message.content


def transcribe_audio(audio_bytes: bytes, language: str = "") -> str:
    """Transcribe audio bytes using OpenAI Whisper API."""
    import io
    import openai
    from data_manager import log_api_cost

    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured")

    client = openai.OpenAI(api_key=api_key)
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "recording.wav"

    kwargs = {"model": "whisper-1", "file": audio_file}
    if language:
        kwargs["language"] = language

    transcript = client.audio.transcriptions.create(**kwargs)

    try:
        # Whisper: ~$0.006/min, estimate from audio size (~16KB/sec for WAV)
        est_seconds = len(audio_bytes) / 16000
        est_cost = est_seconds / 60 * 0.006
        log_api_cost("whisper-1", 0, 0, "voice_transcription")
    except Exception:
        pass

    return transcript.text
