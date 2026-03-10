"""
Koach OS v2 — Learning Engine
================================
Pattern extraction from interaction logs.
Learns: feedback acceptance, voice patterns, decision patterns, heuristics.
"""

from data_manager import (
    read_jsonl, append_jsonl, read_yaml, update_yaml,
    write_style_guide, read_style_guide,
    FEEDBACK_FILE, VOICE_FILE, HEURISTICS_FILE, LOGS_FILE,
    generate_id, timestamp_jst, get_recent_logs,
)


def extract_feedback_pattern(
    user_input: str,
    ai_response: str,
    user_followup: str,
    acceptance_gradient_used: str,
    topic: str = "",
) -> dict | None:
    """Analyze if the counterpoint/criticism was accepted, resisted, or modified.

    Returns feedback_pattern entry or None if no counterpoint was delivered.
    """
    # Only log if AI delivered a counterpoint
    if "⚖️" not in ai_response:
        return None

    followup_lower = user_followup.lower()

    # Classify response based on followup signals
    resistance_signals = [
        "no", "disagree", "but", "however", "wrong", "don't think",
        "いや", "違う", "でも", "しかし", "それは違", "そうじゃない",
    ]
    acceptance_signals = [
        "good point", "you're right", "fair", "true", "makes sense", "hadn't considered",
        "確かに", "そうだね", "なるほど", "いい指摘", "考えてなかった", "そうか",
    ]
    partial_signals = [
        "partly", "some", "maybe", "sort of", "in a way",
        "一部は", "まあ", "ある意味", "部分的に",
    ]

    resistance = sum(1 for s in resistance_signals if s in followup_lower)
    acceptance = sum(1 for s in acceptance_signals if s in followup_lower)
    partial = sum(1 for s in partial_signals if s in followup_lower)

    if acceptance > resistance and acceptance > partial:
        response = "accepted"
    elif partial > 0 or (acceptance > 0 and resistance > 0):
        response = "partially_accepted"
    elif resistance > acceptance:
        response = "initially_resistant"
    else:
        response = "neutral"

    entry = {
        "id": generate_id("fp"),
        "timestamp": timestamp_jst(),
        "topic": topic,
        "acceptance_gradient_used": acceptance_gradient_used,
        "counterpoint_delivered": _extract_counterpoint(ai_response),
        "response": response,
        "time_to_acceptance_minutes": None,
        "notes": "",
    }

    append_jsonl(FEEDBACK_FILE, entry)
    return entry


def _extract_counterpoint(ai_response: str) -> str:
    """Extract the counterpoint section from AI response."""
    lines = ai_response.split("\n")
    capture = False
    result = []
    for line in lines:
        if "⚖️" in line:
            capture = True
            result.append(line)
            continue
        if capture:
            if line.strip().startswith(("→", "📊", "🧠", "🚨", "---")):
                break
            result.append(line)
    return "\n".join(result).strip()[:500] if result else ""


def extract_voice_pattern(text: str, context: str) -> dict | None:
    """Analyze writing sample for style patterns.

    Returns a voice profile entry or None if text is too short.
    """
    if len(text) < 50:
        return None

    observations = []

    # Sentence length analysis
    sentences = [s.strip() for s in text.replace("。", ".").split(".") if s.strip()]
    if sentences:
        avg_len = sum(len(s) for s in sentences) / len(sentences)
        if avg_len > 100:
            observations.append("Tends toward long sentences")
        elif avg_len < 30:
            observations.append("Uses short, punchy sentences")

    # Language switching detection
    has_jp = any(ord(c) > 0x3000 for c in text)
    has_en = any(c.isascii() and c.isalpha() for c in text)
    if has_jp and has_en:
        observations.append("Mixes Japanese and English in same message")

    # Formality detection
    casual_markers = ["lol", "haha", "btw", "tbh", "笑", "www", "w"]
    if any(m in text.lower() for m in casual_markers):
        observations.append("Using casual/informal tone")

    if not observations:
        return None

    entry = {
        "id": generate_id("vp"),
        "timestamp": timestamp_jst(),
        "update_type": "writing_pattern",
        "source": context,
        "observation": "; ".join(observations),
        "recommendation": "",
        "confidence": 0.5,
        "status": "active",
    }

    append_jsonl(VOICE_FILE, entry)
    return entry


def get_acceptance_recommendation() -> str:
    """Based on recent feedback_patterns, recommend acceptance gradient level."""
    patterns = read_jsonl(FEEDBACK_FILE)
    if not patterns:
        return "medium"

    recent = patterns[-20:]

    # Count responses per gradient
    gradient_acceptance = {}
    for p in recent:
        grad = p.get("acceptance_gradient_used", "medium")
        resp = p.get("response", "neutral")
        if grad not in gradient_acceptance:
            gradient_acceptance[grad] = {"accepted": 0, "total": 0}
        gradient_acceptance[grad]["total"] += 1
        if resp in ("accepted", "partially_accepted"):
            gradient_acceptance[grad]["accepted"] += 1

    # Find gradient with highest acceptance rate
    best_gradient = "medium"
    best_rate = 0
    for grad, stats in gradient_acceptance.items():
        if stats["total"] >= 3:
            rate = stats["accepted"] / stats["total"]
            if rate > best_rate:
                best_rate = rate
                best_gradient = grad

    return best_gradient


def get_recent_voice_observations(n: int = 5) -> list[dict]:
    """Get most recent active voice profile observations."""
    all_obs = read_jsonl(VOICE_FILE, filter_fn=lambda x: x.get("status") == "active")
    return all_obs[-n:]


def get_recent_feedback_patterns(n: int = 5) -> list[dict]:
    """Get most recent feedback patterns."""
    return read_jsonl(FEEDBACK_FILE)[-n:]


def update_heuristics_if_needed(min_new_logs: int = 10) -> str | None:
    """Check if enough new data exists to suggest heuristic updates.

    Returns suggestion string or None.
    """
    logs = get_recent_logs(50)
    if len(logs) < min_new_logs:
        return None

    heuristics = read_yaml(HEURISTICS_FILE)

    # Analyze patterns
    suggestions = []

    # Check domain concentration
    domain_counts = {}
    for log in logs:
        d = log.get("domain", "unknown")
        domain_counts[d] = domain_counts.get(d, 0) + 1

    total = len(logs)
    for domain, count in domain_counts.items():
        pct = count / total * 100
        if pct > 60:
            suggestions.append(
                f"Heavy focus on {domain} ({pct:.0f}% of interactions). Consider rebalancing."
            )

    # Check bias frequency
    bias_counts = {}
    for log in logs:
        for b in log.get("cognitive_biases", {}).get("detected", []):
            bias_counts[b] = bias_counts.get(b, 0) + 1

    for bias, count in bias_counts.items():
        if count >= 5:
            suggestions.append(
                f"Recurring bias: {bias} detected {count} times in last {total} interactions."
            )

    if suggestions:
        return "\n".join(suggestions)
    return None


# ─── Writing Style Analysis ───

STYLE_ANALYSIS_PROMPT = """You are a linguistic analyst specializing in writing style profiling.

Analyze the following text sample and produce a detailed JSON analysis with these 8 dimensions:

1. **voice_summary**: A 2-3 sentence description of the overall writing voice
2. **sentence_structure**: Patterns in sentence length, complexity, paragraph structure
3. **vocabulary**: Word choice tendencies, register level, technical vs casual
4. **tone**: Attitude, formality level, emotional coloring
5. **language_mixing**: How Japanese and English are mixed (if applicable)
6. **rhetorical_patterns**: Argumentation style, use of examples, persuasion techniques
7. **genre_notes**: Style observations specific to the genre ({genre})
8. **anti_patterns**: Things this author does NOT do (overly formal AI-like phrasing, etc.)

Context about this text: {context}
Genre: {genre}

Respond ONLY with a valid JSON object (no markdown code fences) with these exact keys:
voice_summary, sentence_structure, vocabulary, tone, language_mixing, rhetorical_patterns, genre_notes, anti_patterns

Each value should be a string with 2-4 sentences of analysis.

TEXT TO ANALYZE:
{text}"""


def analyze_writing_style(text: str, context: str = "", genre: str = "general") -> dict:
    """Analyze a text sample for writing style patterns using Claude.

    Returns the voice profile entry that was saved, or error dict.
    """
    from router import call_ai

    if len(text.strip()) < 50:
        return {"error": "Text too short (minimum 50 characters)"}

    prompt = STYLE_ANALYSIS_PROMPT.format(
        text=text[:5000],
        context=context or "User-provided text sample",
        genre=genre,
    )

    response = call_ai(
        messages=[{"role": "user", "content": prompt}],
        system="You are a precise linguistic analyst. Return only valid JSON.",
        engine="claude",
        model="claude-sonnet-4-6",
        max_tokens=4096,
    )

    # Parse JSON from response
    import json
    try:
        # Handle potential markdown code fences
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1]
            clean = clean.rsplit("```", 1)[0]
        analysis = json.loads(clean)
    except json.JSONDecodeError:
        return {"error": "Failed to parse analysis response", "raw": response}

    entry = {
        "id": generate_id("vp"),
        "timestamp": timestamp_jst(),
        "update_type": "style_analysis",
        "source": context or "manual_analysis",
        "genre": genre,
        "analysis": analysis,
        "observation": analysis.get("voice_summary", ""),
        "recommendation": "",
        "confidence": 0.8,
        "status": "active",
        "text_length": len(text),
    }

    append_jsonl(VOICE_FILE, entry)
    return entry


STYLE_GUIDE_PROMPT = """You are creating a comprehensive writing style guide for Professor Koichiro Shigaki ("Koach").

Based on the following voice profile observations collected over time, synthesize a single coherent style guide in Markdown format.

This style guide will be pasted into AI systems (ChatGPT, Claude, etc.) so they can write in Koach's authentic voice instead of generic AI style.

VOICE PROFILE DATA:
{observations}

Generate the style guide in this exact format:

# Writing Style Guide: Professor Koichiro Shigaki (Koach)
> Generated by Koach OS | Last updated: {timestamp}
> Based on {count} text samples analyzed

## How to Use This Guide
このドキュメントをAIのプロンプトに貼り付けて使用してください。
Paste this document into your AI prompt to replicate Koach's writing voice.

## Voice Summary
[Synthesized overall voice description]

## Sentence Structure / 文構造
[Patterns in sentence length, complexity, paragraph organization]

## Vocabulary & Word Choice / 語彙
[Word choice tendencies, register, technical terms]

## Tone & Attitude / トーン
[Overall attitude, formality, emotional register]

## Language Mixing / 日英コードスイッチング
[How Japanese and English are combined]

## Rhetorical Patterns / 論証パターン
[Argumentation style, persuasion, evidence use]

## Genre-Specific Notes / ジャンル別
[Different styles for different contexts: academic, SNS, business, etc.]

## Anti-Patterns / やらないこと
[Things Koach does NOT do — help AI avoid generic patterns]

Make the guide practical and specific. Use concrete examples where the data supports them.
Write the guide content primarily in English with Japanese section headers as shown."""


def regenerate_style_guide() -> str:
    """Regenerate the style guide from all active voice profile entries.

    Returns the generated markdown content.
    """
    from router import call_ai

    entries = read_jsonl(VOICE_FILE, filter_fn=lambda x: x.get("status") == "active")

    if not entries:
        content = "# Writing Style Guide: Professor Koichiro Shigaki (Koach)\n\n> No text samples analyzed yet. Use the Style page to analyze your writing.\n"
        write_style_guide(content)
        return content

    # Build observations summary from entries
    observations_parts = []
    for e in entries:
        analysis = e.get("analysis")
        if analysis and isinstance(analysis, dict):
            observations_parts.append(
                f"--- Sample ({e.get('genre', 'general')}, {e.get('timestamp', '?')}) ---\n"
                + "\n".join(f"  {k}: {v}" for k, v in analysis.items() if isinstance(v, str))
            )
        elif e.get("observation"):
            observations_parts.append(
                f"--- Observation ({e.get('timestamp', '?')}) ---\n  {e['observation']}"
            )

    observations_text = "\n\n".join(observations_parts)

    prompt = STYLE_GUIDE_PROMPT.format(
        observations=observations_text[:8000],
        timestamp=timestamp_jst(),
        count=len(entries),
    )

    response = call_ai(
        messages=[{"role": "user", "content": prompt}],
        system="You are a writing style analyst. Generate the style guide in clean Markdown.",
        engine="claude",
        model="claude-sonnet-4-6",
        max_tokens=4096,
    )

    write_style_guide(response)
    return response
