"""
Koach OS v2 — Interaction Logs
================================
Browsable log viewer with filters, search, and JSONL export.
"""

import streamlit as st
from datetime import datetime
from data_manager import read_jsonl, export_jsonl, LOGS_FILE

DOMAINS = {
    "teaching": ("🎓", "Teaching / 教育"),
    "research": ("📚", "Research / 研究"),
    "platform": ("💻", "Platform Dev / 開発"),
    "revenue":  ("💰", "Revenue / 収益"),
    "personal": ("🏠", "Personal / 個人"),
    "business": ("🎯", "Business Strategy / 戦略"),
}
LEVELS = {
    "L1": ("Light Structuring · 軽い構造化", "#10b981"),
    "L2": ("Structural Assist · 構造的支援", "#3b82f6"),
    "L3": ("Strategic Intervention · 戦略的介入", "#f59e0b"),
    "L4": ("High-Risk Brake · 高リスク制動", "#ef4444"),
}

logs = read_jsonl(LOGS_FILE)

st.markdown(f"### 📋 Interaction Logs — {len(logs)} entries")
st.caption("Research-ready JSONL format · Append-only · 研究用データ")

if not logs:
    st.info("No interactions logged yet. Start chatting! / まだログがありません。チャットを始めましょう！")
    st.stop()

# ─── Filters ───
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    filter_domain = st.multiselect(
        "Domain / ドメイン",
        list(DOMAINS.keys()),
        format_func=lambda x: f"{DOMAINS[x][0]} {x}",
    )
with col_f2:
    filter_level = st.multiselect(
        "Level / レベル",
        list(LEVELS.keys()),
    )
with col_f3:
    search_text = st.text_input("Search / 検索", placeholder="keyword...")

# Apply filters
filtered = logs
if filter_domain:
    filtered = [l for l in filtered if l.get("domain") in filter_domain]
if filter_level:
    filtered = [l for l in filtered if l.get("intervention_level") in filter_level]
if search_text:
    q = search_text.lower()
    filtered = [l for l in filtered if q in l.get("user_input", "").lower()]

st.caption(f"Showing {len(filtered)} of {len(logs)} entries")

# ─── Export ───
export_content = export_jsonl(LOGS_FILE)
st.download_button(
    "📥 Export All Logs as JSONL",
    export_content,
    f"koach_os_logs_{datetime.now().strftime('%Y%m%d')}.jsonl",
    "application/jsonl",
)

st.divider()

# ─── Display logs (newest first) ───
for log in reversed(filtered):
    lv = log.get("intervention_level", "L1")
    lv_color = LEVELS.get(lv, ("", "#888"))[1]
    domain_icon = DOMAINS.get(log.get("domain", ""), ("❓", ""))[0]

    ts = log.get("timestamp", "")
    try:
        ts_display = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        ts_display = ts[:16]

    # Routing info
    routing = log.get("routing", {})
    engine = routing.get("engine", "?")
    model = routing.get("model", "")[:20]
    route_class = "route-claude" if engine == "claude" else "route-gpt"

    # Bias tags
    bias_ids = log.get("cognitive_biases", {}).get("detected", [])
    # Fallback for v1 format
    if not bias_ids:
        bias_ids = log.get("detected_biases", [])
    biases_str = " ".join([f"#{b}" for b in bias_ids])

    # Action tags
    actions = log.get("ai_actions", {})
    tags = []
    if actions.get("counterpoint_provided") or log.get("has_counterpoint"):
        tags.append("⚖️CP")
    if actions.get("bias_check_provided") or log.get("has_bias_check"):
        tags.append("🧠BC")
    if actions.get("risk_assessment_provided"):
        tags.append("📊RA")
    if actions.get("five_year_check"):
        tags.append("🚨5Y")
    tags_str = " · ".join(tags) if tags else ""

    # Task type
    task_type = log.get("task_type", "")
    gradient = log.get("acceptance_gradient_used", "")

    user_preview = (log.get("user_input", "")[:120] + "...") if len(log.get("user_input", "")) > 120 else log.get("user_input", "")

    st.markdown(f"""
    <div class="log-entry">
        <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
            <div>
                <span class="level-badge" style="background:{lv_color}20; color:{lv_color}; border:1px solid {lv_color}40;">{lv}</span>
                &nbsp; {domain_icon} {log.get('domain','')}
                &nbsp; <span class="route-badge {route_class}">{engine}/{model}</span>
                {f'&nbsp; <span style="color:#475569; font-size:10px;">{task_type}</span>' if task_type else ''}
            </div>
            <span style="color:#475569; font-size:11px; font-family:'JetBrains Mono',monospace;">{ts_display}</span>
        </div>
        <div style="color:#e2e8f0;">💬 {user_preview}</div>
        <div style="color:#64748b; font-size:11px; margin-top:4px;">
            {tags_str}
            {f' &nbsp; {biases_str}' if biases_str else ''}
            {f' &nbsp; gradient:{gradient}' if gradient else ''}
        </div>
    </div>
    """, unsafe_allow_html=True)
