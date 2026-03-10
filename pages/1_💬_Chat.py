"""
Koach OS v2 — Chat Page
=========================
Strategic co-reasoning with auto-routing, bias detection, and learning.
"""

import streamlit as st
from data_manager import (
    append_jsonl, read_jsonl, LOGS_FILE, DECISIONS_FILE,
    generate_id, timestamp_jst, now_jst,
)
from bias_detector import detect_biases, detect_intervention_level
from prompts import build_system_prompt
from router import detect_task_type, route, call_ai
from learning_engine import (
    extract_feedback_pattern, extract_voice_pattern,
    get_acceptance_recommendation, get_recent_voice_observations,
    get_recent_feedback_patterns,
)
from memory_engine import store_conversation, get_memory_context

# ─── Import shared state from app.py ───
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

# Ensure session state
for key, val in [
    ("messages", []), ("current_level", "L2"), ("auto_level", True),
    ("detected_biases", []), ("domain", "teaching"),
    ("routing_override", None), ("acceptance_gradient", "medium"),
    ("custom_models", None), ("last_routing", None),
]:
    if key not in st.session_state:
        st.session_state[key] = val


# ─── Welcome message when empty ───
if not st.session_state.messages:
    st.markdown("""
    <div style="text-align:center; padding:30px 20px;">
        <div style="font-size:48px; margin-bottom:12px;">🧠</div>
        <div style="font-size:18px; font-weight:600; color:#e2e8f0; margin-bottom:8px;">Koach OS Ready</div>
        <div style="font-size:13px; color:#64748b; max-width:500px; margin:0 auto;">
            Strategic AI Partner — 構造化された反省的AIパートナー<br>
            I challenge, I test, I amplify your thinking.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("##### Quick Start / クイックスタート")
    qcols = st.columns(2)
    quick_prompts = [
        "4月ローンチまでに何を優先すべき？",
        "Kindle出版の戦略を壁打ちしたい",
        "J-SLA論文の構成を相談",
        "Platform cost analysis for 500 students",
    ]
    for i, qp in enumerate(quick_prompts):
        with qcols[i % 2]:
            if st.button(qp, key=f"qp_{i}", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": qp})
                st.rerun()

    st.markdown("##### Thinking Recipes / 思考テンプレート")
    recipes = {
        "Pre-Mortem": "これから始めるプロジェクトについてプレモーテム分析をしたい。「もし失敗したとしたら、原因は何か？」を先に考えて、予防策を立てたい。対象: ",
        "Decision Matrix": "意思決定マトリクスで選択肢を比較したい。評価軸を提案して、各選択肢をスコアリングしてほしい。決めたいこと: ",
        "5 Whys": "なぜなぜ分析で問題の根本原因を探りたい。5回の「なぜ？」で深掘りしてほしい。問題: ",
        "Weekly Reflection": "今週を振り返りたい。何がうまくいったか、何がうまくいかなかったか、来週何を変えるべきか。今週の出来事: ",
        "Eisenhower Matrix": "今抱えているタスクをアイゼンハワーマトリクス（緊急/重要の4象限）で整理したい。タスク一覧: ",
        "Steelman Challenge": "自分の考えに対して最も強い反論を構築してほしい。スティールマン手法で徹底的に反論してから、どう対応すべきかを議論したい。自分の主張: ",
    }
    rcols = st.columns(3)
    for i, (name, prompt) in enumerate(recipes.items()):
        with rcols[i % 3]:
            if st.button(f"🧪 {name}", key=f"recipe_{i}", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": prompt})
                st.rerun()


# ─── Display conversation ───
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f'<div class="msg-user">🧑‍💻 {msg["content"]}</div>', unsafe_allow_html=True)
    else:
        # Show routing info if available
        routing_info = msg.get("_routing", {})
        route_engine = routing_info.get("engine", "")
        route_class = "route-claude" if route_engine == "claude" else "route-gpt"
        route_label = routing_info.get("model", route_engine)[:25] if routing_info else ""
        badge = f'<span class="route-badge {route_class}">{route_label}</span> ' if route_label else ""
        st.markdown(f'<div class="msg-ai">{badge}⚡ {msg["content"]}</div>', unsafe_allow_html=True)


# ─── Voice Input ───
voice_input_text = None
try:
    from audio_recorder_streamlit import audio_recorder
    if "_prev_audio_hash" not in st.session_state:
        st.session_state._prev_audio_hash = None

    vcol1, vcol2 = st.columns([1, 11])
    with vcol1:
        audio_bytes = audio_recorder(
            text="", pause_threshold=2.0,
            recording_color="#ef4444", neutral_color="#64748b",
            icon_size="1x", key="voice_rec",
        )
    if audio_bytes:
        audio_hash = hash(audio_bytes[:200])
        if audio_hash != st.session_state._prev_audio_hash:
            st.session_state._prev_audio_hash = audio_hash
            from router import transcribe_audio
            with st.spinner("🎤 Transcribing / 音声認識中..."):
                voice_input_text = transcribe_audio(audio_bytes)
            with vcol2:
                st.caption(f"🎤 {voice_input_text}")
except ImportError:
    st.caption("💡 音声入力を有効にするには: `pip install audio-recorder-streamlit`")

# ─── Input ───
st.markdown("---")
input_col, btn_col = st.columns([6, 1])
with input_col:
    user_input = st.text_area(
        "Message",
        placeholder="Ask Koach OS... / Koach OSに聞く... (🎤 or type)",
        height=80,
        label_visibility="collapsed",
        key="chat_input",
    )
with btn_col:
    st.markdown("<br>", unsafe_allow_html=True)
    send_clicked = st.button("Send ➤", use_container_width=True, type="primary")


# ─── Process message ───
_should_process = (send_clicked and user_input.strip()) or voice_input_text
if _should_process:
    user_text = voice_input_text or user_input.strip()
    domain = st.session_state.domain

    # 1. Detect intervention level
    if st.session_state.auto_level:
        level, axes = detect_intervention_level(user_text)
        st.session_state.current_level = level
    else:
        level = st.session_state.current_level
        axes = {"public_exposure": False, "long_term_impact": False,
                "emotional_signals": False, "value_conflict": False}

    # 2. Detect biases
    biases = detect_biases(user_text)
    st.session_state.detected_biases = biases

    # 3. Route to engine
    task_type = detect_task_type(user_text, domain)
    routing = route(task_type, override=st.session_state.routing_override,
                    custom_models=st.session_state.custom_models)
    st.session_state.last_routing = routing

    # 4. Get learning recommendations
    acceptance_gradient = get_acceptance_recommendation()
    st.session_state.acceptance_gradient = acceptance_gradient
    recent_feedback = get_recent_feedback_patterns(3)
    recent_voice = get_recent_voice_observations(3)

    # 5. Recall relevant memories
    memory_context = ""
    try:
        memory_context = get_memory_context(user_text, n=3, domain=domain)
    except Exception:
        pass

    # 6. Build system prompt
    system_prompt = build_system_prompt(
        domain=domain,
        intervention_level=level,
        detected_biases=biases,
        routing_engine=routing["engine"],
        acceptance_gradient=acceptance_gradient,
        recent_feedback_patterns=recent_feedback,
        recent_voice_observations=recent_voice,
        memory_context=memory_context,
    )

    # 7. Add user message
    st.session_state.messages.append({"role": "user", "content": user_text})

    # 8. Call AI
    with st.spinner(f"⚡ {level} · {routing['engine'].upper()} processing..."):
        api_messages = [{"role": m["role"], "content": m["content"]}
                        for m in st.session_state.messages]
        response = call_ai(api_messages, system_prompt, routing["engine"], routing["model"])

    # 9. Store response with routing metadata
    st.session_state.messages.append({
        "role": "assistant",
        "content": response,
        "_routing": routing,
    })

    # 10. Store in vector memory for RAG recall
    try:
        mem_id = generate_id("mem")
        store_conversation(
            conversation_id=mem_id,
            user_message=user_text,
            ai_response=response,
            domain=domain,
            task_type=task_type,
            intervention_level=level,
        )
    except Exception:
        pass  # Don't break chat flow

    # 11. Learn from interaction
    # Voice pattern extraction
    extract_voice_pattern(user_text, f"chat_{domain}")

    # Feedback pattern (if there was a previous exchange)
    if len(st.session_state.messages) >= 4:
        prev_ai = st.session_state.messages[-3].get("content", "")
        if "⚖️" in prev_ai:
            extract_feedback_pattern(
                user_input=st.session_state.messages[-4].get("content", ""),
                ai_response=prev_ai,
                user_followup=user_text,
                acceptance_gradient_used=acceptance_gradient,
                topic=f"{domain}_{task_type}",
            )

    # 10. Log interaction
    time_of_day = now_jst().hour
    if time_of_day < 12:
        tod = "morning"
    elif time_of_day < 18:
        tod = "afternoon"
    else:
        tod = "evening"

    log_entry = {
        "id": generate_id("log"),
        "timestamp": timestamp_jst(),
        "domain": domain,
        "task_type": task_type,
        "intervention_level": level,
        "level_auto_detected": st.session_state.auto_level,
        "detection_axes": axes,
        "routing": routing,
        "cognitive_biases": {
            "detected": [b["id"] for b in biases],
            "corrections_applied": [b["correction"] for b in biases],
        },
        "acceptance_gradient_used": acceptance_gradient,
        "signals": {
            "language": "japanese" if any(ord(c) > 0x3000 for c in user_text) else "english",
            "input_length": len(user_text),
            "time_of_day": tod,
        },
        "ai_actions": {
            "counterpoint_provided": "⚖️" in response,
            "bias_check_provided": "🧠" in response,
            "risk_assessment_provided": "📊" in response,
            "five_year_check": "🚨" in response,
        },
        "user_input": user_text,
        "ai_response_length": len(response),
        "has_counterpoint": "⚖️" in response,
        "has_bias_check": "🧠" in response,
    }
    append_jsonl(LOGS_FILE, log_entry)

    st.rerun()


# ─── Decision logging (expandable section) ───
if st.session_state.messages:
    with st.expander("📝 Log a Decision / 決定を記録"):
        dec_text = st.text_area("Decision made / 決定内容", key="dec_input", height=60)
        dec_reasoning = st.text_area("Reasoning / 理由", key="dec_reason", height=60)
        dec_alts = st.text_input("Alternatives considered (comma-separated) / 検討した代替案")
        dec_impact_col1, dec_impact_col2 = st.columns(2)
        with dec_impact_col1:
            dec_impact = st.number_input(
                "推定金銭的影響 (¥) / Est. financial impact",
                value=0, step=10000, key="dec_impact",
            )
        with dec_impact_col2:
            dec_impact_type = st.selectbox(
                "影響タイプ / Impact type",
                ["cost_saving", "revenue_gain", "loss_avoidance", "time_saving", "other"],
                key="dec_impact_type",
            )
        if st.button("Save Decision / 保存", key="save_dec"):
            if dec_text.strip():
                entry = {
                    "id": generate_id("d"),
                    "timestamp": timestamp_jst(),
                    "domain": st.session_state.domain,
                    "decision": dec_text.strip(),
                    "reasoning": dec_reasoning.strip(),
                    "alternatives_considered": [a.strip() for a in dec_alts.split(",") if a.strip()],
                    "financial_impact_estimate_jpy": dec_impact,
                    "financial_impact_type": dec_impact_type,
                    "financial_impact_actual_jpy": None,
                    "outcome": "",
                    "status": "active",
                    "revisit_date": None,
                }
                append_jsonl(DECISIONS_FILE, entry)
                st.success("✅ Decision logged / 決定を記録しました")
