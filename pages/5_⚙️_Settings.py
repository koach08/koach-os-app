"""
Koach OS v2 — Settings
========================
API provider/model selection, routing prefs, acceptance gradient, data export.
"""

import json
import zipfile
import io
import streamlit as st
from datetime import datetime
from data_manager import (
    get_secret, read_jsonl, export_jsonl,
    LOGS_FILE, WEEKLY_FILE, DECISIONS_FILE, FEEDBACK_FILE, VOICE_FILE,
    FAILURES_FILE, EXPERIENCES_FILE, HEURISTICS_FILE,
    DATA_DIR, MEMORY_DIR,
)

# Ensure session state
for key, val in [
    ("custom_models", None),
    ("acceptance_gradient", "medium"),
    ("routing_override", None),
]:
    if key not in st.session_state:
        st.session_state[key] = val


st.markdown("### ⚙️ Settings / 設定")

# ─── API Configuration ───
st.markdown("#### 🔑 API Keys")

anthropic_key = get_secret("ANTHROPIC_API_KEY")
openai_key = get_secret("OPENAI_API_KEY")

col1, col2 = st.columns(2)
with col1:
    status = "✅ Configured" if anthropic_key else "❌ Not set"
    st.markdown(f"**Anthropic (Claude)**: {status}")
    if anthropic_key:
        st.caption(f"Key: {anthropic_key[:12]}...{anthropic_key[-4:]}")
with col2:
    status = "✅ Configured" if openai_key else "❌ Not set"
    st.markdown(f"**OpenAI (GPT)**: {status}")
    if openai_key:
        st.caption(f"Key: {openai_key[:12]}...{openai_key[-4:]}")

st.caption("API keys are read from `.env` file. Edit `.env` to change them.")

st.divider()

# ─── Model Selection ───
st.markdown("#### 🤖 Model Configuration")

from router import AVAILABLE_MODELS, DEFAULT_MODELS

col_c, col_g = st.columns(2)
with col_c:
    claude_options = AVAILABLE_MODELS["claude"]
    claude_model = st.selectbox(
        "Claude Model (Reflective)",
        [m[0] for m in claude_options],
        format_func=lambda x: next((m[1] for m in claude_options if m[0] == x), x),
        index=0,
    )
with col_g:
    gpt_options = AVAILABLE_MODELS["gpt"]
    gpt_model = st.selectbox(
        "GPT Model (Execution)",
        [m[0] for m in gpt_options],
        format_func=lambda x: next((m[1] for m in gpt_options if m[0] == x), x),
        index=0,
    )

st.session_state.custom_models = {"claude": claude_model, "gpt": gpt_model}

st.divider()

# ─── Acceptance Gradient ───
st.markdown("#### 🎚️ Acceptance Gradient Override")
st.caption("Controls how counterpoints and criticism are framed. Normally auto-adjusted from feedback patterns.")

gradient = st.radio(
    "Default gradient",
    ["auto", "soft", "medium", "direct", "blunt"],
    format_func=lambda x: {
        "auto": "Auto (from learning data)",
        "soft": "Soft — Reframe as questions",
        "medium": "Medium — Data-backed alternatives (default)",
        "direct": "Direct — Steelman counterarguments",
        "blunt": "Blunt — Explicit challenges (L4 only)",
    }[x],
    index=0,
    horizontal=True,
)
if gradient != "auto":
    st.session_state.acceptance_gradient = gradient

st.divider()

# ─── Data Info ───
st.markdown("#### 💾 Data Files")

files_info = [
    ("interaction_logs.jsonl", LOGS_FILE),
    ("weekly_summaries.jsonl", WEEKLY_FILE),
    ("decisions.jsonl", DECISIONS_FILE),
    ("feedback_patterns.jsonl", FEEDBACK_FILE),
    ("voice_profile.jsonl", VOICE_FILE),
    ("failures.jsonl", FAILURES_FILE),
    ("heuristics.yaml", HEURISTICS_FILE),
    ("experiences.jsonl", EXPERIENCES_FILE),
]

for name, path in files_info:
    count = len(read_jsonl(path)) if path.suffix == ".jsonl" else "—"
    size = f"{path.stat().st_size / 1024:.1f} KB" if path.exists() else "0 KB"
    st.caption(f"📄 `{name}` — {count} entries · {size}")

st.divider()

# ─── Export All Data ───
st.markdown("#### 📦 Export All Data")

if st.button("📦 Download All Data as ZIP", type="primary", use_container_width=True):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, path in files_info:
            if path.exists():
                zf.write(path, f"koach_os_export/{name}")

    st.download_button(
        "⬇️ Download ZIP",
        buf.getvalue(),
        f"koach_os_data_{datetime.now().strftime('%Y%m%d')}.zip",
        "application/zip",
        use_container_width=True,
    )

st.divider()

# ─── System Info ───
st.markdown("#### ℹ️ System Info")
st.caption(f"Data directory: `{DATA_DIR}`")
st.caption(f"Memory directory: `{MEMORY_DIR}`")
st.caption("Version: Koach OS v2.1")
st.caption("Architecture: Streamlit + Claude/GPT dual routing + JSONL append-only + ChromaDB RAG")

try:
    from memory_engine import get_memory_stats
    mem_stats = get_memory_stats()
    st.caption(f"Vector memories: {mem_stats['total_memories']} stored ({mem_stats['status']})")
except Exception:
    st.caption("Vector memories: not initialized")
