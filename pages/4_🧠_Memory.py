"""
Koach OS v2 — Memory Browser
===============================
View/edit heuristics, browse decisions, failures, voice profile, feedback patterns.
"""

import streamlit as st
from data_manager import (
    read_jsonl, append_jsonl, read_yaml, update_yaml,
    DECISIONS_FILE, FAILURES_FILE, VOICE_FILE, FEEDBACK_FILE,
    HEURISTICS_FILE, EXPERIENCES_FILE,
    generate_id, timestamp_jst,
)
from content_pipeline import (
    add_idea, get_ideas, advance_stage, get_pipeline_summary,
    PLATFORMS, STAGES, STAGE_ICONS,
)

st.markdown("### 🧠 Memory / メモリ")
st.caption("Second Brain — accumulated knowledge, patterns, and lessons")

mem_tab1, mem_tab2, mem_tab3, mem_tab4, mem_tab5, mem_tab6 = st.tabs([
    "📏 Heuristics",
    "📝 Decisions",
    "📚 Content Pipeline",
    "💔 Failures",
    "🎙️ Voice Profile",
    "🔄 Feedback Patterns",
])

# ━━━ Heuristics ━━━
with mem_tab1:
    st.markdown("#### Heuristics / 経験則")
    st.caption("Personal rules of thumb — mutable, evolving")

    heuristics = read_yaml(HEURISTICS_FILE)
    rules = heuristics.get("rules_of_thumb", [])

    if rules:
        for i, r in enumerate(rules):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"**{r.get('rule', '')}**")
                st.caption(f"Source: {r.get('source', '?')} · Confidence: {r.get('confidence', '?')}")
            with col2:
                if st.button("🗑️", key=f"del_h_{i}"):
                    rules.pop(i)
                    heuristics["rules_of_thumb"] = rules
                    heuristics["last_updated"] = timestamp_jst()
                    update_yaml(HEURISTICS_FILE, heuristics)
                    st.rerun()
    else:
        st.info("No heuristics yet.")

    st.divider()
    st.markdown("##### Add Heuristic / 追加")
    new_rule = st.text_input("Rule / ルール", key="new_h_rule")
    new_source = st.text_input("Source / ソース", value="manual", key="new_h_src")
    new_conf = st.slider("Confidence / 確信度", 0.0, 1.0, 0.5, key="new_h_conf")
    if st.button("Add / 追加", key="add_h"):
        if new_rule.strip():
            rules.append({"rule": new_rule.strip(), "source": new_source, "confidence": new_conf})
            heuristics["rules_of_thumb"] = rules
            heuristics["last_updated"] = timestamp_jst()
            update_yaml(HEURISTICS_FILE, heuristics)
            st.success("✅ Heuristic added")
            st.rerun()

# ━━━ Decisions ━━━
with mem_tab2:
    st.markdown("#### Decisions / 意思決定記録")
    decisions = read_jsonl(DECISIONS_FILE)

    if decisions:
        for d in reversed(decisions):
            status = d.get("status", "active")
            status_icon = {"active": "🟢", "archived": "📦", "revisit": "🔄"}.get(status, "❓")
            st.markdown(f"""
            <div class="log-entry">
                <div style="display:flex; justify-content:space-between;">
                    <span style="font-weight:600;">{status_icon} {d.get('decision','')[:80]}</span>
                    <span style="color:#64748b; font-size:11px;">{d.get('timestamp','')[:10]}</span>
                </div>
                <div style="color:#94a3b8; font-size:12px; margin-top:4px;">
                    Reasoning: {d.get('reasoning','')[:150]}
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No decisions logged. Use the Chat page to log decisions.")

    st.divider()
    st.markdown("##### Add Decision / 追加")
    dec = st.text_area("Decision / 決定", key="mem_dec", height=60)
    reas = st.text_area("Reasoning / 理由", key="mem_reas", height=60)
    dom = st.selectbox("Domain", list({
        "teaching": "Teaching", "research": "Research", "platform": "Platform",
        "revenue": "Revenue", "personal": "Personal", "business": "Business",
    }.items()), format_func=lambda x: x[1], key="mem_dom")
    if st.button("Save Decision / 保存", key="save_mem_dec"):
        if dec.strip():
            append_jsonl(DECISIONS_FILE, {
                "id": generate_id("d"),
                "timestamp": timestamp_jst(),
                "domain": dom[0],
                "decision": dec.strip(),
                "reasoning": reas.strip(),
                "alternatives_considered": [],
                "outcome": "",
                "status": "active",
                "revisit_date": None,
            })
            st.success("✅ Saved")
            st.rerun()

# ━━━ Content Pipeline ━━━
with mem_tab3:
    st.markdown("#### Content Pipeline / コンテンツパイプライン")
    st.caption("Ideas to Publication — Kindle, papers, blog, SNS")

    # Pipeline overview
    summary = get_pipeline_summary()
    pcols = st.columns(len(STAGES))
    for i, stage in enumerate(STAGES):
        count = summary.get(stage, 0)
        icon = STAGE_ICONS.get(stage, "")
        with pcols[i]:
            _c = "#3b82f6" if count > 0 else "#64748b"
            st.markdown(f"""<div style="text-align:center; padding:4px;">
                <div>{icon}</div>
                <div style="font-size:18px; font-weight:700; color:{_c}; font-family:'JetBrains Mono',monospace;">{count}</div>
                <div style="font-size:9px; color:#64748b;">{stage}</div>
            </div>""", unsafe_allow_html=True)

    # List items by stage
    st.divider()
    view_stage = st.selectbox("Filter by stage / ステージで絞り込み", ["all"] + STAGES, key="pipe_stage")
    items = get_ideas(stage=view_stage if view_stage != "all" else None)

    if items:
        for item in reversed(items):
            s = item.get("stage", "idea")
            s_icon = STAGE_ICONS.get(s, "")
            score = item.get("total_score", 0)
            score_color = "#10b981" if score >= 15 else "#f59e0b" if score >= 10 else "#64748b"
            st.markdown(f"""<div class="log-entry">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-weight:600;">{s_icon} {item.get('title', '')}</span>
                    <span style="font-size:11px;">
                        <span style="color:{score_color}; font-family:'JetBrains Mono',monospace;">{score}pt</span>
                        · {item.get('platform', '')} · {item.get('timestamp', '')[:10]}
                    </span>
                </div>
                <div style="color:#94a3b8; font-size:12px; margin-top:4px;">{item.get('description', '')[:150]}</div>
            </div>""", unsafe_allow_html=True)

            # Advance button
            s_idx = STAGES.index(s) if s in STAGES else 0
            if s_idx < len(STAGES) - 1:
                next_s = STAGES[s_idx + 1]
                if st.button(f"→ Move to {STAGE_ICONS.get(next_s, '')} {next_s}", key=f"adv_{item['id']}"):
                    advance_stage(item["id"])
                    st.rerun()
    else:
        st.info("No content in pipeline yet. Add ideas below.")

    # Add new idea
    st.divider()
    st.markdown("##### Add Idea / アイデア追加")
    idea_title = st.text_input("Title / タイトル", key="idea_title")
    idea_desc = st.text_area("Description / 説明", key="idea_desc", height=60)
    ic1, ic2 = st.columns(2)
    with ic1:
        idea_platform = st.selectbox("Platform", PLATFORMS, key="idea_plat")
    with ic2:
        idea_domain = st.selectbox("Domain", ["teaching", "research", "platform", "revenue", "personal", "business"], key="idea_dom")

    st.markdown("**Scoring / スコアリング** (各1-5点、合計15点以上で実行推奨)")
    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    with sc1:
        s_align = st.number_input("Alignment", 0, 5, 3, key="s_align")
    with sc2:
        s_insight = st.number_input("Insight", 0, 5, 3, key="s_ins")
    with sc3:
        s_audience = st.number_input("Audience", 0, 5, 3, key="s_aud")
    with sc4:
        s_timely = st.number_input("Timeliness", 0, 5, 3, key="s_time")
    with sc5:
        s_effort = st.number_input("Effort/Impact", 0, 5, 3, key="s_eff")

    if st.button("Add Idea / 追加", key="add_idea"):
        if idea_title.strip():
            scores = {
                "alignment": s_align, "insight": s_insight, "audience": s_audience,
                "timeliness": s_timely, "effort_impact": s_effort,
            }
            add_idea(idea_title.strip(), idea_desc.strip(), idea_platform, idea_domain, scores)
            st.success("✅ Idea added to pipeline")
            st.rerun()

# ━━━ Failures ━━━
with mem_tab4:
    st.markdown("#### Failures & Lessons / 失敗と教訓")
    failures = read_jsonl(FAILURES_FILE)

    if failures:
        for f in reversed(failures):
            st.markdown(f"""
            <div class="log-entry">
                <div style="font-weight:600; color:#ef4444;">💔 {f.get('what_happened','')[:80]}</div>
                <div style="color:#94a3b8; font-size:12px; margin-top:4px;">
                    Root cause: {f.get('root_cause','')[:100]}<br>
                    Prevention: {f.get('prevention','')[:100]}
                </div>
                <div style="color:#64748b; font-size:10px; margin-top:2px;">{f.get('timestamp','')[:10]} · {f.get('domain','')}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No failures logged yet. Learning from mistakes requires recording them first.")

    st.divider()
    st.markdown("##### Log Failure / 失敗を記録")
    f_what = st.text_area("What happened / 何が起きたか", key="f_what", height=60)
    f_root = st.text_area("Root cause / 根本原因", key="f_root", height=60)
    f_prev = st.text_area("Prevention / 予防策", key="f_prev", height=60)
    f_dom = st.selectbox("Domain", ["teaching", "research", "platform", "revenue", "personal", "business"], key="f_dom")
    if st.button("Save Failure / 保存", key="save_f"):
        if f_what.strip():
            append_jsonl(FAILURES_FILE, {
                "id": generate_id("fail"),
                "timestamp": timestamp_jst(),
                "domain": f_dom,
                "what_happened": f_what.strip(),
                "root_cause": f_root.strip(),
                "prevention": f_prev.strip(),
                "status": "active",
            })
            st.success("✅ Failure logged")
            st.rerun()

# ━━━ Voice Profile ━━━
with mem_tab5:
    st.markdown("#### Voice Profile / 文体プロファイル")
    st.caption("Writing style observations — accumulated from interactions")

    voice = read_jsonl(VOICE_FILE)
    active = [v for v in voice if v.get("status") == "active"]
    superseded = [v for v in voice if v.get("status") == "superseded"]

    if active:
        st.markdown(f"**{len(active)} active observations**")
        for v in reversed(active):
            st.markdown(f"""
            <div class="log-entry">
                <div style="font-weight:500;">🎙️ {v.get('observation','')}</div>
                <div style="color:#64748b; font-size:11px; margin-top:4px;">
                    Type: {v.get('update_type','')} · Source: {v.get('source','')} · Confidence: {v.get('confidence','')}
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No voice observations yet. The system learns your style from chat interactions.")

    if superseded:
        with st.expander(f"📦 {len(superseded)} superseded observations"):
            for v in reversed(superseded):
                st.caption(f"🎙️ {v.get('observation','')} [{v.get('timestamp','')[:10]}]")

# ━━━ Feedback Patterns ━━━
with mem_tab6:
    st.markdown("#### Feedback Patterns / フィードバック反応パターン")
    st.caption("How counterpoints were received — the learning data")

    fb = read_jsonl(FEEDBACK_FILE)
    if fb:
        # Summary stats
        responses = [f.get("response", "") for f in fb]
        total = len(responses)
        accepted = responses.count("accepted") + responses.count("partially_accepted")
        resistant = responses.count("initially_resistant")
        rate = round(accepted / total * 100) if total else 0

        st.markdown(f"""
        <div style="display:flex; gap:12px; margin-bottom:16px;">
            <div class="stat-card" style="flex:1;">
                <div class="stat-number" style="font-size:20px;">{rate}%</div>
                <div class="stat-label">Acceptance Rate</div>
            </div>
            <div class="stat-card" style="flex:1;">
                <div class="stat-number" style="font-size:20px; color:#10b981;">{accepted}</div>
                <div class="stat-label">Accepted</div>
            </div>
            <div class="stat-card" style="flex:1;">
                <div class="stat-number" style="font-size:20px; color:#ef4444;">{resistant}</div>
                <div class="stat-label">Resistant</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        for f in reversed(fb):
            resp = f.get("response", "")
            resp_color = {"accepted": "#10b981", "partially_accepted": "#f59e0b",
                          "initially_resistant": "#ef4444", "rejected": "#ef4444"}.get(resp, "#64748b")
            st.markdown(f"""
            <div class="log-entry">
                <div style="display:flex; justify-content:space-between;">
                    <span>{f.get('topic','')}</span>
                    <span style="color:{resp_color}; font-weight:600; font-size:11px;">{resp}</span>
                </div>
                <div style="color:#64748b; font-size:11px; margin-top:4px;">
                    Gradient: {f.get('acceptance_gradient_used','')} · {f.get('timestamp','')[:10]}
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No feedback patterns yet. These accumulate as you chat and the system delivers counterpoints.")
