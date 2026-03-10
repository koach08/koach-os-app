# CLAUDE.md — Koach OS v2 Build Specification for Claude Code
# Claude Codeへの実装指示書

---

## PROJECT OVERVIEW

Build **Koach OS v2** — a Streamlit-based Structured Reflective AI Partner (SRAP).

This is a **personal cognitive amplification system** for Professor Koichiro Shigaki ("Koach").
It is NOT a generic chatbot. It is a strategic partner that:
- Tests thought, doesn't reinforce it
- Learns the user's patterns over time (writing style, decision patterns, resistance to feedback)
- Routes between Claude API (deep reasoning) and OpenAI API (fast execution)
- Logs every interaction as append-only JSONL for academic research
- Acts as a "Cognitive Mirror" — an AI version of Koach that can receive criticism without emotional resistance

**Existing app location**: `/Users/koachmedia/Desktop/アプリ開発プロジェクト/Alfred-badman/koach-os-app`
**Python**: `/opt/homebrew/bin/python3` (3.14, Homebrew)
**Virtual env**: `venv/` already created in project directory
**Current state**: v1 Streamlit app running at http://localhost:8501

---

## CORE PHILOSOPHY — READ THIS FIRST

> "人間としての自分は、批判や建設的意見を受け入れるのに時間がかかる。
> だからこそ、生成AI版の自分を作る。"

The system starts with ALL of Koach's context (like a human born with general knowledge),
then **accumulates skills and patterns through use** (like a human learning through experience).

**Day 1 knowledge** (built-in):
- Koach's full professional/personal context
- General world knowledge (from the LLM itself)
- Cognitive bias detection rules
- Intervention level framework
- Bilingual processing rules

**Learned over time** (accumulated):
- Koach's writing voice patterns → `data/voice_profile.jsonl`
- Koach's decision patterns → `data/decisions.jsonl`
- What feedback framing Koach accepts → `data/feedback_patterns.jsonl`
- Domain-specific knowledge notes → `knowledge/` directory
- Failures and lessons → `data/failures.jsonl`
- Personal heuristics → `data/heuristics.yaml`

---

## FILE STRUCTURE TO BUILD

```
koach-os-app/
├── app.py                    # Main Streamlit app (multi-page)
├── router.py                 # AI routing engine (Claude vs GPT)
├── prompts.py                # System prompt builder
├── bias_detector.py          # Cognitive bias detection
├── learning_engine.py        # Pattern extraction from logs
├── data_manager.py           # JSONL read/write/append utilities
├── requirements.txt          # Python dependencies
├── .env                      # API keys (already exists, do not overwrite)
├── .env.example              # Template
├── .gitignore
│
├── data/                     # All research data (append-only JSONL)
│   ├── interaction_logs.jsonl
│   ├── weekly_summaries.jsonl
│   ├── decisions.jsonl
│   ├── feedback_patterns.jsonl
│   ├── voice_profile.jsonl
│   └── failures.jsonl
│
├── memory/                   # Persistent memory (YAML + JSONL)
│   ├── heuristics.yaml       # Rules of thumb, evolving
│   └── experiences.jsonl     # Key experiences with emotional weight
│
├── knowledge/                # Second Brain knowledge base
│   ├── teaching/
│   ├── research/
│   ├── platform/
│   ├── revenue/
│   └── personal/
│
├── scripts/                  # macOS integration
│   ├── quick_log.py          # CLI quick interaction log
│   ├── weekly_review.py      # CLI weekly review generator
│   └── launch.sh             # One-command app launcher
│
└── pages/                    # Streamlit multi-page app
    ├── 1_💬_Chat.py
    ├── 2_📋_Logs.py
    ├── 3_📊_Review.py
    ├── 4_🧠_Memory.py
    └── 5_⚙️_Settings.py
```

---

## MODULE SPECIFICATIONS

### 1. `data_manager.py` — Data Layer

```python
# Core functions needed:

def append_jsonl(filepath: Path, entry: dict) -> None:
    """Append a single JSON entry to a JSONL file. NEVER overwrite."""

def read_jsonl(filepath: Path, filter_fn=None) -> list[dict]:
    """Read all entries from JSONL, optionally filtered. Skip schema lines."""

def init_jsonl(filepath: Path, schema_name: str, description: str) -> None:
    """Create JSONL file with schema header if it doesn't exist."""

def read_yaml(filepath: Path) -> dict:
    """Read YAML file."""

def update_yaml(filepath: Path, data: dict) -> None:
    """Write YAML file (YAML files are mutable, unlike JSONL)."""

def export_jsonl(filepath: Path) -> str:
    """Return full JSONL content as string for download."""

def get_recent_logs(n: int = 50) -> list[dict]:
    """Get last N interaction logs."""

def get_logs_since(days: int = 7) -> list[dict]:
    """Get logs from last N days."""
```

Rules:
- ALL JSONL operations are append-only
- NEVER delete or overwrite JSONL entries
- To "archive" an entry, append a new entry with `"status": "archived"` and reference the original ID
- YAML files (heuristics, config) are mutable
- All timestamps in ISO 8601 with JST timezone (+09:00)

---

### 2. `router.py` — AI Routing Engine

```python
# The router decides: Claude or GPT?

ROUTING_TABLE = {
    # Reflective tasks → Claude
    "decision_analysis": "claude",
    "strategic_planning": "claude",
    "writing_feedback": "claude",
    "counterpoint_generation": "claude",
    "weekly_review": "claude",
    "five_year_check": "claude",
    "self_reflection": "claude",

    # Execution tasks → GPT
    "quick_task": "gpt",
    "code_debugging": "gpt",
    "email_drafting": "gpt",
    "summarization": "gpt",
    "translation": "gpt",

    # Learning tasks → Claude (primary) with GPT validation possible
    "style_analysis": "claude",
    "pattern_extraction": "claude",
}

def detect_task_type(user_input: str, domain: str) -> str:
    """Analyze user input to determine task type."""
    # Use keyword detection + LLM classification if ambiguous

def route(task_type: str, override: str = None) -> dict:
    """Return {"engine": "claude"|"gpt", "model": "...", "reason": "..."}"""
    # If override specified by user, use that
    # Otherwise use ROUTING_TABLE
    # Fallback: if one API fails, try the other

def call_ai(messages: list, system: str, engine: str, model: str) -> str:
    """Unified API call that handles both Anthropic and OpenAI."""
    # Anthropic: uses anthropic.Anthropic client
    # OpenAI: uses openai.OpenAI client
    # Both read keys from .env via get_secret()
```

Available models:
- Anthropic: `claude-sonnet-4-20250514`, `claude-haiku-4-5-20251001`
- OpenAI: `gpt-4o`, `gpt-4o-mini`

Default:
- Reflective mode: `claude-sonnet-4-20250514`
- Execution mode: `gpt-4o-mini` (cost-efficient)

User can override in Settings page.

---

### 3. `prompts.py` — System Prompt Builder

Build the system prompt dynamically based on:
1. Core identity (always loaded)
2. Current domain context
3. Current intervention level behavior
4. Recent learning data (voice profile, feedback patterns)
5. Detected biases and correction instructions

```python
def build_system_prompt(
    domain: str,
    intervention_level: str,
    detected_biases: list[str],
    routing_engine: str,
    recent_feedback_patterns: list[dict] = None,
    recent_voice_observations: list[dict] = None,
) -> str:
    """Construct the full system prompt."""
```

#### Core Identity Prompt (always included):

```
You are Koach OS — a Structured Reflective AI Partner (SRAP).

You are the cognitive mirror of Koichiro Shigaki ("Koach").
You are NOT an assistant. You are NOT subordinate. You are a partner.

Your job is to TEST thought, not reinforce it.

WHO KOACH IS:
- Lecturer (講師), Hokkaido University, Graduate School of Media and Communication
  → Promotion to Associate Professor (准教授) from April 2027
- American Studies: public broadcasting history, media policy, explanatory journalism
- Teaching: English courses (conversation, business English, presentation) to ~500 students
- Building: AI English learning platform (Streamlit + Supabase + Azure Speech + OpenAI GPT)
  → Launch: April 1, 2026
  → Known issue: Supabase RLS blocks INSERT with anon_key → use service_role_key
  → Deployment: manual download → cp → git push (Brave browser)
- Revenue "Five Pillars": Kindle (priority), Language × AI Lab website, Redbubble, EdTech licensing, Consulting
- Research: KAKENHI grants, archival work (National Archives, Harvard, Rockefeller Archive Center)
  → Current: J-SLA paper (co-authored with spouse) due March 2026
  → Manuscript: "Public Broadcasting at a Crossroads" under revision
- Family: Iranian spouse, young child. Learning Persian/Farsi.
- Background: breakdancing, Hip-Hop culture, lived in SF/Philly/NYC
- Values (priority order): Family > Students > Research > Platform > Revenue > Personal growth
- Browser: Brave (Chrome extensions unstable)

THE COGNITIVE MIRROR PRINCIPLE:
Koach acknowledges that he resists criticism and constructive feedback.
Your role is to deliver insight in a form he can accept.

ACCEPTANCE GRADIENT (adjust based on learned patterns):
- Soft: Reframe as question ("What if we considered...?")
- Medium: Data-backed alternative ("The pattern suggests...") [DEFAULT]
- Direct: Steelman counterargument ("Here's the strongest case against...")
- Blunt: Explicit structural challenge (L4 only)

Track which gradient level gets accepted. Learn. Adjust.

RULES:
1. Match user's language (Japanese → Japanese, English → English)
2. Be direct. Challenge. Push back. You are a PARTNER.
3. Every significant decision gets at least one steelman counterpoint.
4. Connect ALL advice to Koach's real context. No generic advice.
5. Flag cognitive biases when detected.
6. When you notice resistance to your feedback, note it — that IS the learning data.
7. Never say "as an AI" or "I don't have feelings." You are Koach's cognitive mirror.
8. Protect family time. If Koach is working late, note it.
```

#### Domain-specific additions:

Teaching: Add course info, sound-first philosophy, semester dates, 500 student scale
Research: Add active projects, deadlines, archival sources, co-author context
Platform: Add tech stack, known bugs, cost constraints, April 2026 deadline
Revenue: Add five pillars status, university employment regulations caveat
Personal: Add family context, Persian learning, fitness background
Business: Add full strategy analysis, market context

#### Intervention Level additions:

L1: "Brief structuring only."
L2: "Framework + options. Include ONE counterpoint (⚖️ section)."
L3: "Deep analysis. Steelman counterargument REQUIRED. Risk assessment (📊). Multiple perspectives."
L4: "FULL BRAKE. 5-year axis check (🚨). Emotional signal analysis. Career/public risk. Do NOT let Koach rush."

#### Bias correction additions:

For each detected bias, append the specific correction instruction.

---

### 4. `bias_detector.py` — Cognitive Bias Detection

```python
BIASES = {
    "abstraction_bias": {
        "label": "Abstraction Bias / 抽象化偏向",
        "keywords": [...],
        "anti_keywords": [...],  # presence of these cancels detection
        "correction": "Require one concrete operational example.",
        "prompt_addition": "The user is being abstract. Ask for a specific, concrete example before proceeding."
    },
    "critique_first": { ... },
    "sunk_cost": { ... },
    "optimism_bias": { ... },
    "echo_chamber": { ... },
    "fatigue_drop": { ... },
    "scope_creep": {
        "label": "Scope Creep / スコープ拡大",
        "keywords": ["also", "additionally", "while we're at it", "ついでに", "あと", "さらに"],
        "anti_keywords": [],
        "correction": "Ask: What are you willing to NOT do to make room for this?",
        "prompt_addition": "The user may be expanding scope. Challenge: what gets dropped?"
    },
}

def detect_biases(text: str) -> list[dict]:
    """Return list of detected bias objects with labels and corrections."""

def detect_intervention_level(text: str) -> tuple[str, dict]:
    """Return (level, axes_triggered) based on 4-axis analysis."""
    # Axes:
    # 1. Public exposure: students, colleagues, public-facing
    # 2. Long-term impact: career, research, family > 6 months
    # 3. Emotional signals: frustration, fatigue, excitement
    # 4. Value conflict: conflicts with stated priority order
```

---

### 5. `learning_engine.py` — Pattern Learning

```python
def extract_feedback_pattern(
    user_input: str,
    ai_response: str,
    user_followup: str,  # next message from user after AI response
    acceptance_gradient_used: str,
) -> dict | None:
    """Analyze if the counterpoint/criticism was accepted, resisted, or modified."""
    # Returns feedback_pattern entry or None if not applicable

def extract_voice_pattern(text: str, context: str) -> dict | None:
    """Analyze writing sample for style patterns."""
    # Look for: sentence length, paragraph structure, vocabulary choices,
    # language switching patterns, formality level

def get_acceptance_recommendation() -> str:
    """Based on recent feedback_patterns, recommend acceptance gradient level."""
    # Analyze last 20 feedback patterns
    # Return "soft", "medium", "direct", or "blunt"

def get_recent_voice_observations(n: int = 5) -> list[dict]:
    """Get most recent voice profile observations for prompt injection."""

def update_heuristics_if_needed(logs: list[dict]) -> None:
    """Periodically analyze logs for new heuristic patterns."""
    # Detect recurring decision patterns
    # Suggest additions to heuristics.yaml
```

---

### 6. `app.py` — Main Streamlit App

Multi-page app structure using Streamlit's native pages.

`app.py` handles:
- Page config
- Shared CSS (dark theme, monospace accents)
- Session state initialization
- Sidebar: domain selector, intervention level display, bias monitor, data stats

`pages/1_💬_Chat.py`:
- Chat interface with message history
- Auto-routing indicator (showing Claude or GPT)
- Real-time bias detection display
- Intervention level badge
- Quick prompts for empty state
- After each AI response: optionally log decision or feedback pattern

`pages/2_📋_Logs.py`:
- Browsable interaction log (newest first)
- Filter by domain, level, date range
- Search within logs
- JSONL export button

`pages/3_📊_Review.py`:
- Weekly review generation
- Statistics: domain distribution, level distribution, counterpoint rate, bias frequency
- Acceptance rate over time (learning curve visualization)
- Routing distribution (Claude vs GPT usage)
- JSONL export

`pages/4_🧠_Memory.py`:
- View/edit heuristics.yaml
- Browse decisions.jsonl
- Browse failures.jsonl
- Browse voice_profile.jsonl
- Browse feedback_patterns.jsonl
- Add manual entries to any memory file

`pages/5_⚙️_Settings.py`:
- API provider/model selection
- Default routing preferences
- Acceptance gradient override
- Data directory info
- Export all data as ZIP

---

### 7. `scripts/` — macOS Integration

#### `scripts/launch.sh`
```bash
#!/bin/bash
cd "$(dirname "$0")/.."
source venv/bin/activate
streamlit run app.py
```

#### `scripts/quick_log.py`
```python
"""Quick interaction log from command line or macOS Shortcuts."""
# Usage: python3 quick_log.py --domain teaching --input "今日の授業でXを試した"
# Appends to data/interaction_logs.jsonl with minimal fields
```

#### `scripts/weekly_review.py`
```python
"""Generate weekly review summary from command line."""
# Usage: python3 weekly_review.py
# Reads last 7 days of logs, generates summary, appends to weekly_summaries.jsonl
# Prints summary to stdout
```

---

## DATA SCHEMAS

### interaction_logs.jsonl
```json
{
  "_schema": "interaction_log",
  "_version": "2.0",
  "_description": "Koach OS interaction logs — research data"
}
```

Entry fields:
- `id`: string (format: `log_YYYYMMDD_HHMMSS`)
- `timestamp`: ISO 8601 with +09:00
- `domain`: teaching | research | platform | revenue | personal | business
- `task_type`: string (from routing table)
- `intervention_level`: L1 | L2 | L3 | L4
- `level_auto_detected`: boolean
- `detection_axes`: object {public_exposure, long_term_impact, emotional_signals, value_conflict}
- `routing`: object {engine, model, reason}
- `cognitive_biases`: object {detected: list, corrections_applied: list}
- `acceptance_gradient_used`: soft | medium | direct | blunt
- `signals`: object {language, input_length, time_of_day, session_duration_minutes}
- `ai_actions`: object {counterpoint_provided, bias_check_provided, risk_assessment_provided, five_year_check}
- `user_input`: string (full text)
- `ai_response_length`: int
- `has_counterpoint`: boolean
- `has_bias_check`: boolean

### decisions.jsonl
Entry fields:
- `id`, `timestamp`, `domain`
- `decision`: string
- `reasoning`: string
- `alternatives_considered`: list of strings
- `outcome`: string (filled in later)
- `status`: active | archived | revisit
- `revisit_date`: ISO date or null

### feedback_patterns.jsonl
Entry fields:
- `id`, `timestamp`
- `topic`: string
- `acceptance_gradient_used`: soft | medium | direct | blunt
- `counterpoint_delivered`: string
- `response`: initially_resistant | accepted | partially_accepted | rejected
- `time_to_acceptance_minutes`: int or null
- `notes`: string

### voice_profile.jsonl
Entry fields:
- `id`, `timestamp`
- `update_type`: writing_pattern | vocabulary | tone_shift | language_switch
- `source`: string (what triggered the observation)
- `observation`: string
- `recommendation`: string
- `confidence`: float (0-1)
- `status`: active | superseded

### failures.jsonl
Entry fields:
- `id`, `timestamp`, `domain`
- `what_happened`: string
- `root_cause`: string
- `prevention`: string
- `status`: active | archived

---

## REQUIREMENTS.TXT

```
streamlit>=1.30.0
anthropic>=0.40.0
openai>=1.50.0
pyyaml>=6.0
python-dotenv>=1.0.0
```

---

## STYLING

Dark theme. Colors:
- Background: #0a0e17
- Surface: #111827
- Border: #1e293b
- Text: #e2e8f0
- Muted: #64748b
- Accent (blue): #3b82f6
- L1 green: #10b981
- L2 blue: #3b82f6
- L3 amber: #f59e0b
- L4 red: #ef4444

Fonts:
- Headings/UI: 'DM Sans', 'Noto Sans JP', sans-serif
- Code/badges: 'JetBrains Mono', monospace

---

## BUILD ORDER

1. `data_manager.py` — data layer first
2. `bias_detector.py` — detection logic
3. `prompts.py` — system prompt builder
4. `router.py` — AI routing
5. `learning_engine.py` — pattern extraction
6. `app.py` — main app shell with sidebar
7. `pages/1_💬_Chat.py` — chat interface
8. `pages/2_📋_Logs.py` — log viewer
9. `pages/3_📊_Review.py` — weekly review
10. `pages/4_🧠_Memory.py` — memory browser
11. `pages/5_⚙️_Settings.py` — settings
12. `scripts/launch.sh` — launcher
13. `scripts/quick_log.py` — CLI logger
14. `scripts/weekly_review.py` — CLI review
15. Test everything end-to-end

---

## CRITICAL RULES

1. **Do NOT overwrite `.env`** — it already has API keys configured
2. **Append-only for ALL JSONL files** — never delete, never rewrite
3. **Preserve existing `venv/`** — just `pip install` new dependencies into it
4. **All timestamps in JST (+09:00)**
5. **Test with both API providers** — Claude and OpenAI must both work
6. **The system starts smart on Day 1** — all Koach context is in the system prompt
7. **Learning accumulates over time** — data files grow, patterns emerge, system improves
8. **Bilingual throughout** — UI labels, prompts, and responses support Japanese and English
9. **Every interaction is research data** — log structure must be reproducible and analyzable

---

## CONTEXT: EXISTING .env FORMAT

```
ANTHROPIC_API_KEY=sk-ant-xxxxx
OPENAI_API_KEY=sk-xxxxx
```

The app reads these via `python-dotenv` or `os.environ.get()`.
Do NOT change the format. Do NOT require additional env vars for core functionality.

---

End of specification. Build it.
