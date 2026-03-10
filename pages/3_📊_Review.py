"""
Koach OS v2 — Weekly Review
==============================
Analytics, weekly summary generation, routing & acceptance stats.
"""

import streamlit as st
from datetime import datetime, timedelta
from data_manager import (
    read_jsonl, append_jsonl, export_jsonl, now_jst,
    LOGS_FILE, WEEKLY_FILE, FEEDBACK_FILE, DECISIONS_FILE, COSTS_FILE,
    generate_id, timestamp_jst, get_costs_since, get_total_cost,
)

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
summaries = read_jsonl(WEEKLY_FILE)
feedback = read_jsonl(FEEDBACK_FILE)

st.markdown("### 📊 Weekly Review / 週次レビュー")

# ─── Quick stats ───
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""
    <div class="stat-card">
        <div style="font-size:24px;">💬</div>
        <div class="stat-number">{len(logs)}</div>
        <div class="stat-label">Total Interactions</div>
    </div>""", unsafe_allow_html=True)
with col2:
    cp_count = sum(1 for l in logs if l.get("has_counterpoint") or l.get("ai_actions", {}).get("counterpoint_provided"))
    cp_rate = f"{round(cp_count/len(logs)*100)}%" if logs else "—"
    st.markdown(f"""
    <div class="stat-card">
        <div style="font-size:24px;">⚖️</div>
        <div class="stat-number">{cp_rate}</div>
        <div class="stat-label">Counterpoint Rate</div>
    </div>""", unsafe_allow_html=True)
with col3:
    bias_count = sum(
        len(l.get("cognitive_biases", {}).get("detected", l.get("detected_biases", [])))
        for l in logs
    )
    st.markdown(f"""
    <div class="stat-card">
        <div style="font-size:24px;">🧠</div>
        <div class="stat-number">{bias_count}</div>
        <div class="stat-label">Bias Detections</div>
    </div>""", unsafe_allow_html=True)
with col4:
    st.markdown(f"""
    <div class="stat-card">
        <div style="font-size:24px;">📊</div>
        <div class="stat-number">{len(summaries)}</div>
        <div class="stat-label">Reviews Generated</div>
    </div>""", unsafe_allow_html=True)

st.divider()

# ─── Generate weekly review ───
if st.button("⚡ Generate Weekly Review / 週次レビュー生成", type="primary", use_container_width=True):
    now = now_jst()
    week_ago = now - timedelta(days=7)
    week_logs = [l for l in logs if l.get("timestamp", "") >= week_ago.isoformat()]

    domain_dist = {}
    level_dist = {"L1": 0, "L2": 0, "L3": 0, "L4": 0}
    bias_freq = {}
    cp_total = 0
    routing_dist = {"claude": 0, "gpt": 0}
    gradient_dist = {"soft": 0, "medium": 0, "direct": 0, "blunt": 0}
    time_dist = {"morning": 0, "afternoon": 0, "evening": 0}

    for l in week_logs:
        d = l.get("domain", "unknown")
        domain_dist[d] = domain_dist.get(d, 0) + 1

        lv = l.get("intervention_level", "L1")
        level_dist[lv] = level_dist.get(lv, 0) + 1

        for b in l.get("cognitive_biases", {}).get("detected", l.get("detected_biases", [])):
            bias_freq[b] = bias_freq.get(b, 0) + 1

        if l.get("has_counterpoint") or l.get("ai_actions", {}).get("counterpoint_provided"):
            cp_total += 1

        eng = l.get("routing", {}).get("engine", "")
        if eng in routing_dist:
            routing_dist[eng] += 1

        grad = l.get("acceptance_gradient_used", "medium")
        if grad in gradient_dist:
            gradient_dist[grad] += 1

        tod = l.get("signals", {}).get("time_of_day", "")
        if tod in time_dist:
            time_dist[tod] += 1

    # Acceptance rate from feedback patterns
    week_feedback = [f for f in feedback if f.get("timestamp", "") >= week_ago.isoformat()]
    accepted = sum(1 for f in week_feedback if f.get("response") in ("accepted", "partially_accepted"))
    acceptance_rate = round(accepted / len(week_feedback) * 100) if week_feedback else 0

    summary = {
        "id": generate_id("weekly"),
        "period_start": week_ago.isoformat(),
        "period_end": now.isoformat(),
        "total_interactions": len(week_logs),
        "domain_distribution": domain_dist,
        "level_distribution": level_dist,
        "bias_frequency": bias_freq,
        "counterpoint_rate_pct": round(cp_total / len(week_logs) * 100) if week_logs else 0,
        "counterpoint_acceptance_rate_pct": acceptance_rate,
        "acceptance_gradient_distribution": gradient_dist,
        "routing_distribution": routing_dist,
        "time_distribution": time_dist,
        "generated_at": timestamp_jst(),
    }

    append_jsonl(WEEKLY_FILE, summary)
    st.success(f"✅ Weekly review generated! {len(week_logs)} interactions analyzed.")
    st.rerun()

# ─── Domain distribution ───
if logs:
    st.markdown("#### Domain Distribution / ドメイン分布")
    domain_counts = {}
    for l in logs:
        d = l.get("domain", "unknown")
        domain_counts[d] = domain_counts.get(d, 0) + 1

    dcols = st.columns(len(DOMAINS))
    for i, (did, (icon, label)) in enumerate(DOMAINS.items()):
        count = domain_counts.get(did, 0)
        pct = round(count / len(logs) * 100) if logs else 0
        with dcols[i]:
            st.markdown(f"""
            <div class="stat-card">
                <div style="font-size:18px;">{icon}</div>
                <div style="font-size:20px; font-weight:700; color:#3b82f6; font-family:'JetBrains Mono',monospace;">{count}</div>
                <div style="font-size:10px; color:#64748b;">{did}</div>
                <div style="background:#1e293b; border-radius:2px; height:4px; margin-top:6px;">
                    <div style="background:#3b82f6; border-radius:2px; height:4px; width:{pct}%;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Level distribution
    st.markdown("#### Intervention Level Distribution / 介入レベル分布")
    level_counts = {"L1": 0, "L2": 0, "L3": 0, "L4": 0}
    for l in logs:
        lv = l.get("intervention_level", "L1")
        level_counts[lv] = level_counts.get(lv, 0) + 1

    lcols = st.columns(4)
    for i, (lv, (label, color)) in enumerate(LEVELS.items()):
        count = level_counts.get(lv, 0)
        with lcols[i]:
            st.markdown(f"""
            <div style="background:{color}10; border:1px solid {color}30; border-radius:10px; padding:12px; text-align:center;">
                <div style="font-size:18px; font-weight:700; color:{color}; font-family:'JetBrains Mono',monospace;">{lv}</div>
                <div style="font-size:24px; font-weight:700; color:{color};">{count}</div>
                <div style="font-size:10px; color:#64748b;">{label.split('·')[0].strip()}</div>
            </div>
            """, unsafe_allow_html=True)

    # Routing distribution
    st.markdown("#### AI Routing Distribution / AIルーティング分布")
    rcol1, rcol2 = st.columns(2)
    claude_count = sum(1 for l in logs if l.get("routing", {}).get("engine") == "claude")
    gpt_count = sum(1 for l in logs if l.get("routing", {}).get("engine") == "gpt")
    # Also count v1 logs without routing info
    no_route = len(logs) - claude_count - gpt_count
    with rcol1:
        st.markdown(f"""
        <div style="background:rgba(139,92,246,0.1); border:1px solid rgba(139,92,246,0.3); border-radius:10px; padding:12px; text-align:center;">
            <div style="font-size:14px; color:#a78bfa; font-weight:600;">Claude (Reflective)</div>
            <div style="font-size:28px; font-weight:700; color:#a78bfa; font-family:'JetBrains Mono',monospace;">{claude_count}</div>
        </div>
        """, unsafe_allow_html=True)
    with rcol2:
        st.markdown(f"""
        <div style="background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3); border-radius:10px; padding:12px; text-align:center;">
            <div style="font-size:14px; color:#6ee7b7; font-weight:600;">GPT (Execution)</div>
            <div style="font-size:28px; font-weight:700; color:#6ee7b7; font-family:'JetBrains Mono',monospace;">{gpt_count}</div>
        </div>
        """, unsafe_allow_html=True)

# ─── ROI Dashboard / 投資対効果 ───
st.divider()
st.markdown("#### 💹 ROI Dashboard / 投資対効果")

roi_period = st.selectbox("Period / 期間", [7, 30, 90], index=1, format_func=lambda x: f"Last {x} days / 過去{x}日")
costs = get_costs_since(roi_period)
total_cost_usd = sum(c.get("total_cost_usd", 0) for c in costs)
total_cost_jpy = total_cost_usd * 150  # approximate USD→JPY

# Decisions with financial impact in the period
decisions = read_jsonl(DECISIONS_FILE)
cutoff_iso = (now_jst() - timedelta(days=roi_period)).isoformat()
period_decisions = [d for d in decisions if d.get("timestamp", "") >= cutoff_iso and d.get("financial_impact_estimate_jpy", 0) != 0]
total_estimated_value = sum(d.get("financial_impact_estimate_jpy", 0) for d in period_decisions)
total_actual_value = sum(d.get("financial_impact_actual_jpy", 0) or 0 for d in period_decisions)

rcol1, rcol2, rcol3, rcol4 = st.columns(4)
with rcol1:
    st.markdown(f"""
    <div class="stat-card">
        <div style="font-size:24px;">💸</div>
        <div class="stat-number">${total_cost_usd:.2f}</div>
        <div class="stat-label">API Cost (≈¥{total_cost_jpy:,.0f})</div>
    </div>""", unsafe_allow_html=True)
with rcol2:
    st.markdown(f"""
    <div class="stat-card">
        <div style="font-size:24px;">📈</div>
        <div class="stat-number">¥{total_estimated_value:,}</div>
        <div class="stat-label">Est. Decision Value</div>
    </div>""", unsafe_allow_html=True)
with rcol3:
    roi_pct = round((total_estimated_value - total_cost_jpy) / total_cost_jpy * 100) if total_cost_jpy > 0 else 0
    roi_color = "#10b981" if roi_pct >= 0 else "#ef4444"
    st.markdown(f"""
    <div class="stat-card">
        <div style="font-size:24px;">🎯</div>
        <div class="stat-number" style="color:{roi_color};">{roi_pct:+,}%</div>
        <div class="stat-label">Est. ROI</div>
    </div>""", unsafe_allow_html=True)
with rcol4:
    st.markdown(f"""
    <div class="stat-card">
        <div style="font-size:24px;">📊</div>
        <div class="stat-number">{len(costs)}</div>
        <div class="stat-label">API Calls</div>
    </div>""", unsafe_allow_html=True)

# Cost breakdown by model
if costs:
    st.markdown("##### Cost by Model / モデル別コスト")
    model_costs = {}
    for c in costs:
        m = c.get("model", "unknown")
        model_costs[m] = model_costs.get(m, 0) + c.get("total_cost_usd", 0)
    for m, cost in sorted(model_costs.items(), key=lambda x: -x[1]):
        pct = cost / total_cost_usd * 100 if total_cost_usd else 0
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:8px; margin:4px 0;">
            <span style="font-family:'JetBrains Mono',monospace; font-size:12px; color:#e2e8f0; min-width:200px;">{m}</span>
            <div style="flex:1; background:#1e293b; border-radius:2px; height:8px;">
                <div style="background:#3b82f6; border-radius:2px; height:8px; width:{pct}%;"></div>
            </div>
            <span style="font-family:'JetBrains Mono',monospace; font-size:12px; color:#64748b; min-width:80px; text-align:right;">${cost:.4f}</span>
        </div>""", unsafe_allow_html=True)

# Active decisions with financial impact
if period_decisions:
    st.markdown("##### Tracked Decisions / 追跡中の決定")
    for d in reversed(period_decisions):
        impact = d.get("financial_impact_estimate_jpy", 0)
        impact_type = d.get("financial_impact_type", "")
        icon = {"cost_saving": "💰", "revenue_gain": "📈", "loss_avoidance": "🛡️", "time_saving": "⏱️"}.get(impact_type, "📋")
        st.markdown(f"""
        <div class="log-entry">
            <div style="display:flex; justify-content:space-between;">
                <span>{icon} {d.get('decision', '')[:80]}</span>
                <span style="color:#10b981; font-family:'JetBrains Mono',monospace;">¥{impact:,}</span>
            </div>
            <div style="font-size:11px; color:#64748b;">{d.get('domain', '')} · {impact_type} · {d.get('timestamp', '')[:10]}</div>
        </div>""", unsafe_allow_html=True)

# ─── Past summaries ───
if summaries:
    st.divider()
    st.markdown("#### Past Reviews / 過去のレビュー")

    export_content = export_jsonl(WEEKLY_FILE)
    st.download_button(
        "📥 Export Weekly Summaries as JSONL",
        export_content,
        f"koach_os_weekly_{datetime.now().strftime('%Y%m%d')}.jsonl",
        "application/jsonl",
    )

    for s in reversed(summaries):
        try:
            start = datetime.fromisoformat(s["period_start"]).strftime("%m/%d")
            end = datetime.fromisoformat(s["period_end"]).strftime("%m/%d")
        except Exception:
            start = end = "?"

        level_tags = " ".join([
            f'<span class="level-badge" style="background:{LEVELS[lv][1]}20;color:{LEVELS[lv][1]};border:1px solid {LEVELS[lv][1]}40;">{lv}:{ct}</span>'
            for lv, ct in s.get("level_distribution", {}).items() if ct > 0
        ])

        routing_info = s.get("routing_distribution", {})
        routing_text = f"Claude:{routing_info.get('claude',0)} GPT:{routing_info.get('gpt',0)}"

        st.markdown(f"""
        <div class="log-entry">
            <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                <span style="font-weight:600;">{start} — {end}</span>
                <span style="color:#64748b; font-size:11px;">{s.get('total_interactions',0)} interactions</span>
            </div>
            <div>{level_tags}
                &nbsp; <span style="color:#10b981; font-size:11px;">⚖️ {s.get('counterpoint_rate_pct',0)}% CP</span>
                &nbsp; <span style="color:#a78bfa; font-size:11px;">{routing_text}</span>
                &nbsp; <span style="color:#f59e0b; font-size:11px;">Acceptance: {s.get('counterpoint_acceptance_rate_pct',0)}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
