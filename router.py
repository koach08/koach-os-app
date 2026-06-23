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

    # New routes (multi-engine)
    "realtime_query": "groq",        # 爆速応答が欲しい単発質問
    "web_search": "perplexity",       # 最新情報・Web検索
    "long_context": "gemini",         # 長文・PDF・大量資料
    "uncensored": "venice",           # 制約なし対話・brainstorm
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
    "realtime_query": [
        "fast", "instant", "right now", "asap",
        "爆速", "即答", "今すぐ", "急ぎで",
    ],
    "web_search": [
        "search the web", "latest news", "recent", "what's new",
        "最新", "今", "ニュース", "調べて", "検索して", "現在",
    ],
    "long_context": [
        "long document", "entire paper", "whole pdf", "this book",
        "長文", "全文", "丸ごと", "一冊", "ドキュメント全体",
    ],
    "uncensored": [
        "uncensored", "no filter", "honestly", "without restrictions",
        "制約なし", "本音", "忖度なしで", "包み隠さず",
    ],
}

# Default models per engine
DEFAULT_MODELS = {
    "claude": "claude-opus-4-8",
    "gpt": "gpt-5.5",
    "grok": "grok-4",
    "gemini": "gemini-2.5-pro",
    "venice": "venice-uncensored",
    "perplexity": "sonar-pro",
    "groq": "llama-3.3-70b-versatile",
    "fugu": "fugu",
    "fugu-ultra": "fugu-ultra",
}

# Available models for settings UI
AVAILABLE_MODELS = {
    "claude": [
        ("claude-opus-4-8", "Claude Opus 4.8 (最新・最高性能 $5/$25)"),
        ("claude-opus-4-7", "Claude Opus 4.7 (前世代 $5/$25)"),
        ("claude-sonnet-4-6", "Claude Sonnet 4.6 (バランス $3/$15)"),
        ("claude-haiku-4-5", "Claude Haiku 4.5 (高速・低コスト $1/$5)"),
    ],
    "gpt": [
        ("gpt-5.5", "GPT-5.5 (最新・最高性能)"),
        ("gpt-5.4", "GPT-5.4 (前世代 $2.50/$15)"),
        ("gpt-5.2", "GPT-5.2 (コード・エージェント向け $1.75/$14)"),
        ("gpt-5", "GPT-5 (コスパ良好 $1.25/$10)"),
        ("gpt-4.1", "GPT-4.1 (非推論・安定 $2.00/$8)"),
        ("gpt-4.1-mini", "GPT-4.1 Mini (低コスト $0.40/$1.60)"),
        ("gpt-4.1-nano", "GPT-4.1 Nano (超低コスト $0.10/$0.40)"),
    ],
    "grok": [
        ("grok-4", "Grok 4 (推論・最高性能)"),
        ("grok-4-mini", "Grok 4 Mini (軽量)"),
        ("grok-3", "Grok 3 (前世代)"),
    ],
    "gemini": [
        ("gemini-2.5-pro", "Gemini 2.5 Pro (推論・長文 2M context)"),
        ("gemini-2.5-flash", "Gemini 2.5 Flash (高速)"),
        ("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite (低コスト)"),
    ],
    "venice": [
        ("venice-uncensored", "Venice Uncensored (制約なし)"),
        ("llama-3.3-70b", "Llama 3.3 70B"),
        ("qwen3-235b", "Qwen3 235B"),
        ("deepseek-r1-llama-70b", "DeepSeek R1 (推論)"),
    ],
    "perplexity": [
        ("sonar-pro", "Sonar Pro (Web検索・高性能)"),
        ("sonar", "Sonar (Web検索・軽量)"),
        ("sonar-reasoning-pro", "Sonar Reasoning Pro (推論+検索)"),
        ("sonar-reasoning", "Sonar Reasoning (推論+検索・軽量)"),
    ],
    "groq": [
        ("llama-3.3-70b-versatile", "Llama 3.3 70B (汎用・高速)"),
        ("llama-3.1-8b-instant", "Llama 3.1 8B (爆速・軽量)"),
        ("llama-4-scout-17b-16e-instruct", "Llama 4 Scout (新・高速)"),
        ("deepseek-r1-distill-llama-70b", "DeepSeek R1 Distill (推論)"),
        ("qwen/qwen3-32b", "Qwen3 32B"),
        ("openai/gpt-oss-120b", "GPT-OSS 120B"),
    ],
    "fugu": [
        ("fugu", "Sakana Fugu (高速・既定 / 複数フロンティアを自動編成)"),
        ("fugu-ultra", "Sakana Fugu Ultra (難問・多段 / 研究・論文再現・文献調査)"),
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
    """Unified API call across Claude, GPT, Grok, Gemini."""
    dispatch = {
        "claude": _call_claude,
        "gpt": _call_gpt,
        "grok": _call_grok,
        "gemini": _call_gemini,
        "venice": _call_venice,
        "perplexity": _call_perplexity,
        "groq": _call_groq,
        "fugu": _call_fugu,
        "fugu-ultra": _call_fugu,
    }
    fn = dispatch.get(engine, _call_gpt)
    try:
        return fn(messages, system, model, max_tokens)
    except Exception as e:
        # Fallback: prefer Claude if not the failing engine, else GPT
        try:
            if engine != "claude":
                return _call_claude(messages, system, DEFAULT_MODELS["claude"], max_tokens)
            else:
                return _call_gpt(messages, system, DEFAULT_MODELS["gpt"], max_tokens)
        except Exception as e2:
            return f"❌ Both APIs failed.\nPrimary ({engine}): {e}\nFallback: {e2}"


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


def _call_grok(messages: list[dict], system: str, model: str, max_tokens: int = 2048) -> str:
    """Call xAI Grok via OpenAI-compatible API."""
    import openai
    from data_manager import log_api_cost

    api_key = get_secret("XAI_API_KEY")
    if not api_key:
        raise ValueError("XAI_API_KEY not configured")

    client = openai.OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
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


def _call_gemini(messages: list[dict], system: str, model: str, max_tokens: int = 2048) -> str:
    """Call Google Gemini API."""
    import google.generativeai as genai
    from data_manager import log_api_cost

    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not configured")

    genai.configure(api_key=api_key)
    model_obj = genai.GenerativeModel(model_name=model, system_instruction=system)

    # Convert OpenAI-style messages to Gemini format
    if not messages:
        raise ValueError("messages must not be empty")

    history = []
    for m in messages[:-1]:
        role = "user" if m.get("role") == "user" else "model"
        history.append({"role": role, "parts": [m.get("content", "")]})

    chat = model_obj.start_chat(history=history)
    last_msg = messages[-1].get("content", "")
    resp = chat.send_message(
        last_msg,
        generation_config={"max_output_tokens": max_tokens},
    )

    try:
        usage = getattr(resp, "usage_metadata", None)
        if usage:
            log_api_cost(
                model,
                getattr(usage, "prompt_token_count", 0),
                getattr(usage, "candidates_token_count", 0),
                "chat",
            )
    except Exception:
        pass

    return resp.text


def _call_venice(messages: list[dict], system: str, model: str, max_tokens: int = 2048) -> str:
    """Call Venice AI via OpenAI-compatible API."""
    import openai
    from data_manager import log_api_cost

    api_key = get_secret("VENICE_API_KEY")
    if not api_key:
        raise ValueError("VENICE_API_KEY not configured")

    client = openai.OpenAI(api_key=api_key, base_url="https://api.venice.ai/api/v1")
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


def _call_perplexity(messages: list[dict], system: str, model: str, max_tokens: int = 2048) -> str:
    """Call Perplexity Sonar via OpenAI-compatible API."""
    import openai
    from data_manager import log_api_cost

    api_key = get_secret("PERPLEXITY_API_KEY")
    if not api_key:
        raise ValueError("PERPLEXITY_API_KEY not configured")

    client = openai.OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")
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


def _call_groq(messages: list[dict], system: str, model: str, max_tokens: int = 2048) -> str:
    """Call Groq via OpenAI-compatible API (LPU-accelerated inference)."""
    import openai
    from data_manager import log_api_cost

    api_key = get_secret("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not configured")

    client = openai.OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
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


def _call_fugu(messages: list[dict], system: str, model: str, max_tokens: int = 2048) -> str:
    """Call Sakana Fugu via OpenAI-compatible API.

    Fugu はオーケストレーションモデル (内部で複数フロンティア LLM を自動編成)。
    model: "fugu" (高速・既定) / "fugu-ultra" (難問・多段)。
    base_url は SAKANA_BASE_URL で上書き可 (既定 https://api.sakana.ai/v1)。
    """
    import openai
    from data_manager import log_api_cost

    api_key = get_secret("SAKANA_API_KEY")
    if not api_key:
        raise ValueError("SAKANA_API_KEY not configured")

    base_url = get_secret("SAKANA_BASE_URL") or "https://api.sakana.ai/v1"
    client = openai.OpenAI(api_key=api_key, base_url=base_url)
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
