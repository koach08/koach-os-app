"""
Koach OS v2 — Strategic AI Partner
====================================
Structured Reflective AI Partner (SRAP) for Koach.

Run:  streamlit run app.py
"""

import streamlit as st
from data_manager import init_all_data_files

# ─── PAGE CONFIG ───
st.set_page_config(
    page_title="Koach OS",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Initialize data files ───
init_all_data_files()

# ─── SHARED CSS ───
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

.stApp { background-color: #0a0e17; }

/* Header */
.koach-header {
    background: linear-gradient(135deg, #111827, #1a2235);
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 16px;
}
.koach-logo {
    width: 48px; height: 48px; border-radius: 12px;
    background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    display: flex; align-items: center; justify-content: center;
    font-size: 24px; font-weight: 700; color: white;
    font-family: 'JetBrains Mono', monospace;
}
.koach-title { font-size: 22px; font-weight: 700; color: #e2e8f0; font-family: 'DM Sans', sans-serif; }
.koach-subtitle { font-size: 11px; color: #64748b; font-family: 'JetBrains Mono', monospace; letter-spacing: 0.1em; }

/* Chat messages */
.msg-user {
    background: rgba(59,130,246,0.1);
    border: 1px solid rgba(59,130,246,0.2);
    border-radius: 12px; padding: 14px 18px; margin: 8px 0;
    color: #e2e8f0; font-size: 14px; line-height: 1.7;
}
.msg-ai {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 12px; padding: 14px 18px; margin: 8px 0;
    color: #e2e8f0; font-size: 14px; line-height: 1.7;
}
.msg-ai h3 { color: #3b82f6; font-size: 15px; margin: 12px 0 6px; }

/* Level badges */
.level-badge {
    display: inline-block; padding: 2px 10px; border-radius: 6px;
    font-size: 11px; font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
}

/* Stat cards */
.stat-card {
    background: #111827; border: 1px solid #1e293b;
    border-radius: 12px; padding: 16px; text-align: center;
}
.stat-number { font-size: 28px; font-weight: 700; color: #3b82f6; font-family: 'JetBrains Mono', monospace; }
.stat-label { font-size: 11px; color: #64748b; margin-top: 4px; }

/* Log entry */
.log-entry {
    background: #111827; border: 1px solid #1e293b;
    border-radius: 10px; padding: 12px 16px; margin: 6px 0;
    font-size: 13px; color: #e2e8f0;
}

/* Routing badge */
.route-badge {
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 10px; font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
}
.route-claude { background: rgba(139,92,246,0.15); color: #a78bfa; border: 1px solid rgba(139,92,246,0.3); }
.route-gpt { background: rgba(16,185,129,0.15); color: #6ee7b7; border: 1px solid rgba(16,185,129,0.3); }

/* Sidebar styling */
section[data-testid="stSidebar"] { background-color: #111827; }
section[data-testid="stSidebar"] .stMarkdown { color: #e2e8f0; }

/* Override Streamlit defaults */
.stTextArea textarea { background-color: #111827 !important; color: #e2e8f0 !important; border-color: #1e293b !important; }
.stTextArea textarea:focus { border-color: #3b82f6 !important; }
div[data-testid="stMetric"] { background: #111827; border: 1px solid #1e293b; border-radius: 10px; padding: 12px; }
</style>
""", unsafe_allow_html=True)


# ─── CONSTANTS (shared across pages) ───
DOMAINS = {
    "teaching":  ("🎓", "Teaching / 教育"),
    "research":  ("📚", "Research / 研究"),
    "platform":  ("💻", "Platform Dev / 開発"),
    "revenue":   ("💰", "Revenue / 収益"),
    "personal":  ("🏠", "Personal / 個人"),
    "business":  ("🎯", "Business Strategy / 戦略"),
}

LEVELS = {
    "L1": ("Light Structuring · 軽い構造化", "#10b981"),
    "L2": ("Structural Assist · 構造的支援", "#3b82f6"),
    "L3": ("Strategic Intervention · 戦略的介入", "#f59e0b"),
    "L4": ("High-Risk Brake · 高リスク制動", "#ef4444"),
}


# ─── SESSION STATE INIT ───
defaults = {
    "messages": [],
    "current_level": "L2",
    "auto_level": True,
    "detected_biases": [],
    "domain": "teaching",
    "routing_override": None,
    "acceptance_gradient": "medium",
    "custom_models": None,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ─── HEADER ───
st.markdown("""
<div class="koach-header">
    <div class="koach-logo">K</div>
    <div>
        <div class="koach-title">Koach OS v2</div>
        <div class="koach-subtitle">STRUCTURED REFLECTIVE AI PARTNER · 構造化された反省的AIパートナー</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ─── SIDEBAR ───
with st.sidebar:
    st.markdown("### ⚙️ Settings / 設定")

    # Domain
    st.markdown("##### 🏷️ Domain / ドメイン")
    domain = st.radio(
        "Current domain",
        list(DOMAINS.keys()),
        format_func=lambda x: f"{DOMAINS[x][0]} {DOMAINS[x][1]}",
        label_visibility="collapsed",
        index=list(DOMAINS.keys()).index(st.session_state.domain),
    )
    st.session_state.domain = domain

    st.divider()

    # Intervention Level
    st.markdown("##### 📊 Intervention Level / 介入レベル")
    st.session_state.auto_level = st.toggle("Auto-detect / 自動検出", value=st.session_state.auto_level)

    if not st.session_state.auto_level:
        level_choice = st.radio(
            "Level",
            list(LEVELS.keys()),
            format_func=lambda x: f"{x} — {LEVELS[x][0]}",
            index=list(LEVELS.keys()).index(st.session_state.current_level),
            label_visibility="collapsed",
        )
        st.session_state.current_level = level_choice

    lv = st.session_state.current_level
    lv_color = LEVELS[lv][1]
    st.markdown(f"""
    <div style="background:{lv_color}15; border:1px solid {lv_color}40; border-radius:8px; padding:10px; text-align:center;">
        <div style="font-size:20px; font-weight:700; color:{lv_color}; font-family:'JetBrains Mono',monospace;">{lv}</div>
        <div style="font-size:11px; color:#94a3b8;">{LEVELS[lv][0]}</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # AI Routing
    st.markdown("##### 🔀 AI Routing")
    routing_mode = st.radio(
        "Routing",
        ["auto", "claude", "gpt"],
        format_func=lambda x: {"auto": "Auto-route / 自動", "claude": "Claude (Reflective)", "gpt": "GPT (Execution)"}[x],
        label_visibility="collapsed",
    )
    st.session_state.routing_override = None if routing_mode == "auto" else routing_mode

    st.divider()

    # Bias monitor
    st.markdown("##### 🧠 Bias Monitor / バイアス監視")
    if st.session_state.detected_biases:
        for b in st.session_state.detected_biases:
            st.markdown(f"⚡ **{b['label']}**")
            st.caption(b["correction"])
    else:
        st.caption("No biases detected / バイアス未検出")

    st.divider()

    # Calendar
    from gcal import is_configured, get_events, format_events_html
    if is_configured():
        st.markdown("##### 📅 Today / 今日")
        today_events = get_events(days_ahead=0)
        st.markdown(format_events_html(today_events), unsafe_allow_html=True)
        st.divider()

    # Data stats
    from data_manager import read_jsonl, get_total_cost, LOGS_FILE
    logs = read_jsonl(LOGS_FILE)
    cost_30d = get_total_cost(30)
    st.caption(f"📋 {len(logs)} interactions · 💸 ${cost_30d:.2f}/30d")

    if st.button("🗑️ Clear Chat / チャットクリア", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


# ─── DAILY BRIEFING (Landing Page) ───
from data_manager import read_jsonl, get_total_cost, now_jst, LOGS_FILE, DECISIONS_FILE
from content_pipeline import get_pipeline_summary, get_actionable_ideas, STAGE_ICONS

_now = now_jst()
_hour = _now.hour
if _hour < 12:
    _greeting = "Good morning"
elif _hour < 18:
    _greeting = "Good afternoon"
else:
    _greeting = "Good evening"

st.markdown(f"""
<div style="text-align:center; padding:20px;">
    <div style="font-size:36px; margin-bottom:8px;">🧠</div>
    <div style="font-size:18px; font-weight:600; color:#e2e8f0;">{_greeting}, Koach</div>
    <div style="font-size:12px; color:#64748b; font-family:'JetBrains Mono',monospace;">{_now.strftime('%Y-%m-%d %A %H:%M')} JST</div>
</div>
""", unsafe_allow_html=True)

# ─── Today's Schedule ───
from gcal import is_configured as _gcal_ok, get_events as _gcal_events, format_events_html as _gcal_html
if _gcal_ok():
    st.markdown("##### 📅 Today's Schedule / 今日の予定")
    _today_ev = _gcal_events(days_ahead=0)
    if _today_ev:
        st.markdown(f'<div class="log-entry">{_gcal_html(_today_ev)}</div>', unsafe_allow_html=True)
    else:
        st.caption("No events scheduled today.")
else:
    st.info("📅 Google Calendar未接続。`python scripts/setup_gcal.py` で設定できます。")

# ─── Quick Stats Row ───
_all_logs = read_jsonl(LOGS_FILE)
_decisions = read_jsonl(DECISIONS_FILE)
_active_dec = [d for d in _decisions if d.get("status") == "active"]
_cost_7d = get_total_cost(7)

bc1, bc2, bc3, bc4 = st.columns(4)
with bc1:
    st.markdown(f"""<div class="stat-card">
        <div class="stat-number" style="font-size:22px;">{len(_all_logs)}</div>
        <div class="stat-label">Total Interactions</div>
    </div>""", unsafe_allow_html=True)
with bc2:
    st.markdown(f"""<div class="stat-card">
        <div class="stat-number" style="font-size:22px;">{len(_active_dec)}</div>
        <div class="stat-label">Active Decisions</div>
    </div>""", unsafe_allow_html=True)
with bc3:
    _pipeline = get_pipeline_summary()
    _pipeline_total = sum(_pipeline.values())
    st.markdown(f"""<div class="stat-card">
        <div class="stat-number" style="font-size:22px;">{_pipeline_total}</div>
        <div class="stat-label">Content Pipeline</div>
    </div>""", unsafe_allow_html=True)
with bc4:
    st.markdown(f"""<div class="stat-card">
        <div class="stat-number" style="font-size:22px;">${_cost_7d:.2f}</div>
        <div class="stat-label">API Cost (7d)</div>
    </div>""", unsafe_allow_html=True)

# ─── Pending Decisions ───
if _active_dec:
    st.markdown("##### 📝 Pending Decisions / 保留中の決定")
    for _d in _active_dec[-5:]:
        _dom_icon = {"teaching": "🎓", "research": "📚", "platform": "💻",
                     "revenue": "💰", "personal": "🏠", "business": "🎯"}.get(_d.get("domain", ""), "📋")
        st.markdown(f"""<div class="log-entry">
            {_dom_icon} {_d.get('decision', '')[:100]}
            <span style="color:#64748b; font-size:11px; float:right;">{_d.get('timestamp', '')[:10]}</span>
        </div>""", unsafe_allow_html=True)

# ─── Content Pipeline ───
if _pipeline_total > 0:
    st.markdown("##### 📚 Content Pipeline / コンテンツパイプライン")
    _pcols = st.columns(len(STAGE_ICONS))
    for i, (stage, icon) in enumerate(STAGE_ICONS.items()):
        count = _pipeline.get(stage, 0)
        with _pcols[i]:
            _color = "#3b82f6" if count > 0 else "#1e293b"
            st.markdown(f"""<div style="text-align:center; padding:6px;">
                <div style="font-size:16px;">{icon}</div>
                <div style="font-size:16px; font-weight:700; color:{_color}; font-family:'JetBrains Mono',monospace;">{count}</div>
                <div style="font-size:9px; color:#64748b;">{stage}</div>
            </div>""", unsafe_allow_html=True)

    _actionable = get_actionable_ideas()
    if _actionable:
        st.caption(f"🟢 {len(_actionable)} ideas ready to execute (score >= 15)")

# ─── Navigation ───
st.divider()
st.markdown("##### Navigate / ページ選択")
st.markdown("""
| Page | Description |
|------|-------------|
| 💬 Chat | Strategic co-reasoning partner |
| 📋 Logs | Interaction log browser |
| 📊 Review | Weekly review & ROI analytics |
| 🧠 Memory | Memory, content pipeline & patterns |
| ⚙️ Settings | API & model configuration |
""")
