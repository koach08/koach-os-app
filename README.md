# 🧠 Koach OS — Strategic AI Partner

A Streamlit-based structured reflective AI partner (SRAP) designed for Koach.

## Features

- **💬 AI Chat** — Claude or GPT as a strategic co-reasoning partner (not an assistant)
- **📊 Auto Intervention Levels (L1–L4)** — Automatically adjusts depth based on conversation stakes
- **🧠 Cognitive Bias Detection** — Real-time detection of abstraction bias, critique-first, sunk cost, etc.
- **⚖️ Mandatory Counterpoint** — Steelman counterarguments for every significant decision
- **📋 Research Logging** — All interactions logged as append-only JSONL for research analysis
- **📊 Weekly Review** — Aggregated metrics: domain distribution, intervention levels, counterpoint rate
- **🌐 Bilingual** — Japanese/English, responds in the language you write in

## Quick Start (Mac Local)

```bash
# 1. Clone or download this folder
cd koach-os-app

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up API keys
cp .env.example .env
# Edit .env with your actual API keys

# 4. Run
streamlit run app.py
```

Opens at `http://localhost:8501`

## Phone Access (Same Network)

When running locally, Streamlit shows:
```
Local URL:    http://localhost:8501
Network URL:  http://192.168.x.x:8501
```

Access the Network URL from your phone's browser (same WiFi).

## Streamlit Cloud Deployment (Phone from Anywhere)

```bash
# 1. Push to GitHub (private repo)
git init && git add . && git commit -m "init"
# Create private repo on GitHub, push

# 2. Go to share.streamlit.io
# Connect your repo

# 3. Add secrets in Streamlit Cloud dashboard:
#    ANTHROPIC_API_KEY = "sk-ant-xxxxx"
#    OPENAI_API_KEY = "sk-xxxxx"
```

## Data Storage

All data stored locally as JSONL files (append-only):
```
data/
├── interaction_logs.jsonl   # Every chat interaction (research data)
└── weekly_summaries.jsonl   # Weekly aggregated reviews
```

**No external database needed.** Export anytime as JSONL for research analysis.

When deployed to Streamlit Cloud, note that data resets on redeployment.
For persistent cloud storage, a database integration can be added later.

## File Structure

```
koach-os-app/
├── app.py              # Main application
├── requirements.txt    # Python dependencies
├── .env.example        # API key template → copy to .env
├── .gitignore
├── .streamlit/
│   └── secrets.toml.example  # For Streamlit Cloud
├── data/               # Auto-created on first run
│   ├── interaction_logs.jsonl
│   └── weekly_summaries.jsonl
└── README.md
```

## Research Use

Interaction logs capture:
- Timestamp, domain, intervention level
- Whether level was auto-detected
- Detected cognitive biases and corrections applied
- AI provider and model used
- Full user input text
- Response metrics (length, counterpoint presence, bias check, risk assessment)

Export logs anytime via the sidebar button or Logs tab.

## Architecture Notes

- **Append-only JSONL**: Data integrity — no destructive updates
- **No database dependency**: Zero cost, portable, git-trackable
- **Dual API support**: Switch between Anthropic and OpenAI in the sidebar
- **Progressive enhancement**: Start local → add Streamlit Cloud → add database later if needed
