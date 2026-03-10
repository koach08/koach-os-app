# Alfred OS — Project Specification
Version: v1.0
Status: Active (Year 1 — Pilot Phase)
Last Updated: 2026-02-25

---

## 1. Project Vision

Alfred OS (branded as **Koach OS** in-app) is a structured reflective AI partner (SRAP) designed to function as:

- A strategic co-reasoning system
- A reflective amplifier
- A cognitive correction mechanism
- A research instrument

It is **NOT**:
- A subordinate tool
- A generic AI assistant
- A productivity hack

Core philosophical position: Alfred is designed to **test** thought, not reinforce it.

---

## 2. System Architecture

### 2.1 Tech Stack

| Layer        | Technology                        |
|------------- |-----------------------------------|
| Frontend/UI  | Streamlit (Python)                |
| AI Backend   | Anthropic Claude / OpenAI GPT    |
| Data Storage | Local JSONL (append-only)         |
| Runtime      | Python 3.14, venv                 |
| Deployment   | Local (macOS) / Streamlit Cloud   |

### 2.2 File Structure

```
koach-os-app/
├── app.py                          # Monolithic application (all logic)
├── requirements.txt                # Python dependencies
├── .env                            # API keys (not tracked)
├── data/
│   ├── interaction_logs.jsonl      # Every chat interaction (research data)
│   ├── weekly_summaries.jsonl      # Weekly aggregated reviews
│   └── decisions.jsonl             # Key decisions with reasoning
└── README.md
```

### 2.3 Application Entry Point

```bash
streamlit run app.py
```

Accessible at `http://localhost:8501` (local) or via Network URL on same WiFi.

---

## 3. Core Design Principles

### 3.1 Resident Mode
Alfred operates as a persistent intellectual partner for a single user (Professor Koichiro Shigaki, Hokkaido University). No repeated context explanation required — system prompt contains full user profile.

### 3.2 Auto-adjusted Intervention Levels

| Level | Name                   | Color   | Behavior                                                     |
|-------|------------------------|---------|--------------------------------------------------------------|
| L1    | Light Structuring      | #10b981 | Brief structuring. Organize the thought. Minimal commentary.  |
| L2    | Structural Assist      | #3b82f6 | Framework + options + light analysis. ONE counterpoint.        |
| L3    | Strategic Intervention | #f59e0b | Deep strategic analysis. Multiple perspectives. Risk assessment. |
| L4    | High-Risk Brake        | #ef4444 | Full brake check. 5-year axis check. Do NOT let user rush.     |

**Detection method**: Keyword matching against user input text (lowercase).
- L4 triggers: career, resign, quit, public statement, etc.
- L3 triggers: strategy, decision, compare, tradeoff, launch, invest, etc.
- L2 triggers: plan, structure, organize, outline, prepare, etc.
- L1: default fallback

Auto-detection is toggleable in sidebar. Manual override available.

### 3.3 Mandatory Counterpoint
At L2+, the AI must include a `⚖️ Counterpoint:` section with a genuine steelman argument against the user's position.

### 3.4 Cognitive Bias Detection & Correction

| Bias ID               | Label (JP)         | Detection Method            | Correction Rule                              |
|------------------------|--------------------|-----------------------------|----------------------------------------------|
| `abstraction_bias`     | 抽象化偏向          | Keywords present, no anti-keywords | Require one concrete operational example      |
| `critique_first`       | 批判優先            | Keywords present, no anti-keywords | Generate constructive alternative alongside   |
| `sunk_cost`            | 埋没費用            | Keywords present             | Evaluate from zero-base, ignore past investment |
| `optimism_bias`        | 楽観偏向            | Keywords present             | Request worst-case scenario analysis          |
| `echo_chamber`         | エコーチェンバー     | Keywords present             | Surface opposing evidence                     |
| `fatigue_drop`         | 疲労低下            | Keywords present             | Invoke 5-year axis check                      |

Detection runs on every user message. Results shown in sidebar and injected into system prompt for AI correction.

### 3.5 Bilingual Cognitive Design

- English: conceptual/theoretical precision
- Japanese: normative alignment & nuance verification
- System prompt instructs AI: "Match user's language (Japanese input → Japanese response, English → English)"

---

## 4. Domain Model

Six operational domains, selectable in sidebar:

| Key        | Icon | Label                       |
|------------|------|-----------------------------|
| `teaching` | 🎓   | Teaching / 教育              |
| `research` | 📚   | Research / 研究              |
| `platform` | 💻   | Platform Dev / 開発          |
| `revenue`  | 💰   | Revenue / 収益               |
| `personal` | 🏠   | Personal / 個人              |
| `business` | 🎯   | Business Strategy / 戦略     |

Domain selection is logged per interaction for research analysis.

---

## 5. AI Integration

### 5.1 Supported Providers

| Provider   | Models Available                           |
|------------|--------------------------------------------|
| Anthropic  | claude-sonnet-4, claude-haiku-4.5           |
| OpenAI     | gpt-4o, gpt-4o-mini                        |

Switchable in sidebar. API keys loaded from: Streamlit secrets → env vars → `.env` file (in order of precedence).

### 5.2 System Prompt Construction

The system prompt is dynamically assembled per message from:
1. **Base prompt** — User profile, role definition, behavioral rules
2. **Context injection** — Current domain, intervention level
3. **Bias corrections** — If biases detected, correction instructions appended
4. **Level-specific behavior** — Formatting requirements per intervention level

### 5.3 Response Formatting Requirements

| Condition         | Required Section              |
|-------------------|-------------------------------|
| L2+               | `⚖️ Counterpoint:`            |
| Biases detected   | `🧠 Bias Check:`              |
| L3+               | `📊 Risk/Opportunity:`        |
| L4                | `🚨 5-Year Axis Check:`       |
| Always            | `→ Next Action:` (one step)   |

### 5.4 Parameters

- `max_tokens`: 2048
- Full conversation history sent (no truncation currently)

---

## 6. Data Architecture (Append-only Design)

### 6.1 Principle
All data is append-only JSONL. No destructive updates. No deletion.

### 6.2 Schema: `interaction_logs.jsonl`

Each entry records:

```json
{
  "id": "log_20260225_143000",
  "timestamp": "2026-02-25T14:30:00",
  "domain": "teaching",
  "intervention_level": "L3",
  "auto_detected_level": true,
  "detected_biases": ["abstraction_bias"],
  "bias_corrections_applied": ["Require one concrete operational example."],
  "provider": "anthropic",
  "model": "claude-sonnet-4-20250514",
  "user_input": "...",
  "user_input_length": 150,
  "ai_response_length": 800,
  "has_counterpoint": true,
  "has_bias_check": true,
  "has_risk_assessment": true,
  "has_5year_check": false
}
```

### 6.3 Schema: `weekly_summaries.jsonl`

Aggregated weekly metrics:

```json
{
  "id": "weekly_20260225_143000",
  "period_start": "2026-02-18T14:30:00",
  "period_end": "2026-02-25T14:30:00",
  "total_interactions": 42,
  "domain_distribution": {"teaching": 15, "research": 10, ...},
  "level_distribution": {"L1": 8, "L2": 20, "L3": 12, "L4": 2},
  "bias_frequency": {"abstraction_bias": 5, "critique_first": 3},
  "counterpoint_rate_pct": 85,
  "generated_at": "2026-02-25T14:30:00"
}
```

### 6.4 Schema: `decisions.jsonl`

Key decisions with reasoning (initialized but not yet populated via UI).

### 6.5 File Initialization

Each JSONL file starts with a schema header line:
```json
{"_schema": "interaction_log", "_version": "1.0", "_description": "..."}
```
Schema lines are filtered out on read.

---

## 7. UI Structure

### 7.1 Layout
- **Sidebar**: Settings (provider, model, domain, intervention level, bias monitor, data export)
- **Main area**: Three tabs

### 7.2 Tabs

| Tab                | Purpose                                           |
|--------------------|---------------------------------------------------|
| 💬 Chat            | Primary interaction. Welcome screen with quick prompts. |
| 📋 Interaction Logs | Browse all logged interactions (newest first).     |
| 📊 Weekly Review   | Aggregate stats, generate weekly summaries.         |

### 7.3 Visual Design
- Dark theme (`#0a0e17` background)
- JetBrains Mono for code/stats, Noto Sans JP for Japanese text
- Color-coded intervention levels
- Custom CSS injected via `st.markdown(unsafe_allow_html=True)`

---

## 8. Research Positioning (2-Year Strategy)

### Primary Axis
Educational research: Instructor reflective practice

### Core Research Question
> "How does a structured reflective AI partner influence an instructor's reflective practice and decision structure?"

### Methodology
Mixed methods design:
- **Quantitative**: Interaction frequency, intervention level distribution, counterpoint rate, bias detection frequency, domain distribution, response metrics
- **Qualitative**: Thematic analysis of interaction content
- **Mechanism tracing**: How AI interventions map to behavioral changes

### Timeline

| Phase   | Period   | Focus                              |
|---------|----------|------------------------------------|
| Year 1  | Current  | N-of-1 longitudinal pilot, domestic presentation |
| Year 2  | 2027     | Expanded study, English publication target        |

### Data Collection Points (per interaction)
- Timestamp, domain, intervention level (auto vs manual)
- Detected biases and corrections applied
- AI provider and model
- User input text and length
- Response metrics: length, presence of counterpoint/bias check/risk assessment/5-year check

---

## 9. Operational Rules

1. **Log every meaningful intervention** — Automatic on every chat send.
2. **Run weekly review** — Generate via Weekly Review tab.
3. **Do not over-engineer** — Current architecture is monolithic single-file by design.
4. **Maintain append-only discipline** — No deletion, no destructive updates to data files.
5. **Preserve reproducibility** — JSONL format, schema-versioned, exportable.

---

## 10. Future Expansion Plan

### Phase 1 (Current): Research-first Architecture
- Single-file Streamlit app
- Local JSONL storage
- Dual AI provider support

### Phase 2: Persistent Cloud Storage
- Database integration for Streamlit Cloud deployment
- Data survives redeployment

### Phase 3: Node.js / Electron UI Layer
- Design principle: Node layer calls Python core only
- Core logic remains single-source-of-truth in Python

### Research Expansion Possibilities
- Multi-instructor comparative study
- Student-level deployment
- AI-mediated reflective practice theory
- Publicness and AI-mediated cognition

---

## 11. Dependencies

```
streamlit
anthropic
openai
```

(As specified in requirements.txt)

---

## 12. Known Limitations & Technical Debt

1. **No conversation history truncation** — Full history sent to API on every call; will hit token limits on long sessions.
2. **Keyword-based detection** — Bias and level detection use simple keyword matching, not semantic analysis.
3. **No authentication** — App is open to anyone with the URL.
4. **Session-bound chat** — Chat history lives in `st.session_state`, lost on page refresh.
5. **decisions.jsonl unused** — File initialized but no UI to populate it.
6. **No error retry** — API calls fail silently with error message in chat.
7. **Data resets on Streamlit Cloud redeploy** — No persistent storage integration yet.

---

End of specification.
