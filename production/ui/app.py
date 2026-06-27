import os
import uuid
import json
import time

import streamlit as st
import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


# ── Session init ──────────────────────────────────────────────
if "config" not in st.session_state:
    try:
        with httpx.Client() as c:
            r = c.get(f"{BACKEND_URL}/config", timeout=10)
            st.session_state.config = r.json()
    except Exception:
        st.session_state.config = {
            "client_name": "Grupo Sazón",
            "assistant_name": "María",
            "emoji": "🌶️",
            "greeting": "Hi! I'm María 🌶️ from Grupo Sazón.",
        }
    st.session_state.messages = []
    st.session_state.user_id = str(uuid.uuid4())
    greeting = st.session_state.config.get("greeting", "")
    if greeting:
        st.session_state.messages.append({"role": "assistant", "content": greeting})

if "page" not in st.session_state:
    st.session_state.page = "chat"

# ── Admin mode via ?admin=true ────────────────────────────────
qp = st.query_params
admin_mode = str(qp.get("admin", "false")).lower() in ("1", "true", "yes")
if not admin_mode:
    st.session_state.page = "chat"

config = st.session_state.config
client_name = config.get("client_name", "Client")
assistant_name = config.get("assistant_name", "Assistant")
emoji = config.get("emoji", "💬")

st.set_page_config(page_title=f"{client_name} — HR Agent", page_icon=emoji, layout="centered")

# ── Custom CSS ───────────────────────────────────────────────
st.html("""
<style>
/* ── Global — force light red background everywhere ── */
.stApp,
section.main,
div.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"] {
    background-color: #fbe5e5 !important;
}

/* ── Chat input bar — minimal floating pill ── */
.stChatInputContainer,
.stChatInput,
.stBottomInputContainer {
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding-top: 0.5rem !important;
}
.stChatInput textarea {
    border-radius: 24px !important;
    border: 1.5px solid #e8b4a0 !important;
    background-color: #ffffff !important;
    box-shadow: 0 4px 20px rgba(192, 57, 43, 0.06) !important;
    padding: 0.85rem 1.25rem !important;
    font-size: 0.95rem !important;
}
.stChatInput textarea::placeholder {
    color: #c4a89a !important;
}
.stChatInput textarea:focus {
    border-color: #c0392b !important;
    box-shadow: 0 4px 24px rgba(192, 57, 43, 0.12) !important;
}
/* Send button */
.stChatInput button {
    border-radius: 50% !important;
    background-color: #c0392b !important;
    color: #ffffff !important;
    border: none !important;
    box-shadow: 0 2px 8px rgba(192, 57, 43, 0.2) !important;
}
.stChatInput button:hover {
    background-color: #a93226 !important;
}

/* ── Chat messages ── */
.stChatMessage {
    border-radius: 14px !important;
    border: 1px solid rgba(232, 180, 160, 0.4) !important;
    box-shadow: 0 1px 4px rgba(45, 27, 14, 0.06) !important;
}

/* Assistant bubble */
.stChatMessage[data-testid="stChatMessageAvatarIcon-assistant"] {
    background-color: #fff5f0 !important;
}

/* User bubble */
.stChatMessage[data-testid="stChatMessageAvatarIcon-user"] {
    background-color: #fef0ec !important;
}

/* ── Avatars ── */
.stChatMessageAvatarIcon-assistant img,
.stChatMessageAvatarIcon-assistant svg {
    background-color: #c0392b !important;
    border-radius: 50% !important;
}
.stChatMessageAvatarIcon-user img,
.stChatMessageAvatarIcon-user svg {
    background-color: #7f8c8d !important;
    border-radius: 50% !important;
}

/* ── Pills (suggestions) ── */
.stPills .stMultiSelectPillsCheckbox {
    background-color: #ffffff !important;
    border: 1px solid #e8b4a0 !important;
    border-radius: 20px !important;
}
.stPills button {
    border-radius: 20px !important;
    color: #c0392b !important;
    border-color: #e8b4a0 !important;
}
.stPills button[aria-pressed="true"] {
    background-color: #c0392b !important;
    color: #ffffff !important;
    border-color: #c0392b !important;
}

/* ── Buttons ── */
.stButton > button {
    border-radius: 10px !important;
    border-color: #e8b4a0 !important;
    color: #c0392b !important;
}
.stButton > button:hover {
    background-color: #fce8e0 !important;
    border-color: #c0392b !important;
}
.stButton > button[kind="primary"] {
    background-color: #c0392b !important;
    color: #ffffff !important;
    border-color: #c0392b !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: #a93226 !important;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background-color: #faf0ea !important;
    border-right: 1px solid #e8b4a0 !important;
}

/* ── Metrics ── */
.stMetric {
    background-color: #ffffff !important;
    border-radius: 10px !important;
    border: 1px solid #f0d5c8 !important;
    padding: 0.5rem !important;
}

/* ── Alerts ── */
.stAlert {
    border-radius: 10px !important;
}

/* ── Dividers ── */
hr {
    border-color: #e8b4a0 !important;
}
</style>
""")

# ── Sidebar (only in admin mode) ──────────────────────────────
if admin_mode:
    with st.sidebar:
        st.markdown(f"## {emoji} {client_name}")
        st.caption(f"Assistant: {assistant_name}")
        st.divider()

        st.session_state.page = st.radio(
            "Navigate",
            options=["chat", "analytics", "voice", "admin"],
            format_func=lambda x: {
                "chat": "💬 Chat",
                "analytics": "📊 Analytics",
                "voice": "📞 Call María",
                "admin": "⚙️ Admin",
            }[x],
            label_visibility="collapsed",
        )

        st.divider()
        st.caption("Backend")
        try:
            with httpx.Client() as c:
                ping = c.get(f"{BACKEND_URL}/ping", timeout=3).json()
            st.success(f"Connected — {ping.get('llm_backend', '?')}")
        except Exception:
            st.error("Backend unreachable")

        if st.button("🔄 Reset conversation"):
            st.session_state.messages = []
            greeting = st.session_state.config.get("greeting", "")
            if greeting:
                st.session_state.messages.append({"role": "assistant", "content": greeting})
            st.rerun()


# ── Pages ─────────────────────────────────────────────────────

def _consume_sse_stream(msg: str):
    """Shared SSE consumer — yields decoded chunks with latency tracking."""
    t0 = time.perf_counter()
    first_token = None
    with httpx.Client() as c:
        with c.stream(
            "POST",
            f"{BACKEND_URL}/chat",
            json={"message": msg, "user_id": st.session_state.user_id},
            timeout=120,
        ) as r:
            for line in r.iter_lines():
                if not line:
                    continue
                if line.startswith("data: ") and line != "data: [DONE]":
                    if first_token is None:
                        first_token = time.perf_counter()
                    try:
                        yield json.loads(line[6:])
                    except json.JSONDecodeError:
                        yield line[6:]
    total = (time.perf_counter() - t0) * 1000
    ttft = (first_token - t0) * 1000 if first_token else 0
    st.session_state["last_ttft_ms"] = round(ttft, 0)
    st.session_state["last_total_ms"] = round(total, 0)


def page_chat():
    st.html(f"""
    <div style="
        display: flex; align-items: center; gap: 0.75rem;
        padding: 0.5rem 0; margin-bottom: 0.25rem;
    ">
        <span style="font-size: 2rem; line-height: 1;">{emoji}</span>
        <div>
            <div style="font-size: 1.5rem; font-weight: 600; color: #2d1b0e; line-height: 1.2;">{client_name}</div>
            <div style="font-size: 0.85rem; color: #8b6f5e;">Chatting with {assistant_name}</div>
        </div>
    </div>
    """)

    SUGGESTIONS = [
        "How does the hiring process work?",
        "What positions are available?",
        "Tell me more about the company",
    ]

    if len(st.session_state.messages) == 0:
        selected = st.pills("Examples", options=SUGGESTIONS, label_visibility="collapsed")
        user_input = st.chat_input("Ask something...")
    else:
        selected = None
        user_input = st.chat_input("Ask a follow-up...")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    msg = user_input or selected
    if msg:
        with st.chat_message("user"):
            st.markdown(msg)
        with st.chat_message("assistant"):
            reply = st.write_stream(_consume_sse_stream(msg))
        st.session_state.messages.append({"role": "user", "content": msg})
        st.session_state.messages.append({"role": "assistant", "content": reply})

        if admin_mode:
            ttft = st.session_state.get("last_ttft_ms", 0)
            total = st.session_state.get("last_total_ms", 0)
            if ttft and total:
                st.caption(f"⚡ {ttft:.0f}ms to first token · {total:.0f}ms total")


def page_analytics():
    st.title("📊 Analytics")
    st.info("Conversation metrics will appear here once the screening agent is live.")
    st.markdown("""
    **Planned metrics:**
    - Completion rate
    - Drop-off stage
    - Average conversation duration
    - Qualification funnel (qualified / disqualified / absent)
    """)


def page_voice():
    st.title(f"📞 Call {assistant_name}")
    st.info("Browser-based voice agent — coming soon.")
    st.markdown("""
    **Planned:**
    - STT: Whisper transcription
    - TTS: Natural voice synthesis
    - Same screening flow as chat
    """)


def page_admin():
    st.title("⚙️ Admin")
    st.markdown("### Backend status")

    col1, col2 = st.columns(2)
    try:
        with httpx.Client() as c:
            health = c.get(f"{BACKEND_URL}/health", timeout=3).json()
            ping = c.get(f"{BACKEND_URL}/ping", timeout=3).json()
        col1.metric("Health", health.get("status", "?"))
        col2.metric("LLM Backend", ping.get("llm_backend", "?"))
    except Exception as e:
        st.error(f"Cannot reach backend: {e}")

    st.markdown("### Latency benchmark")
    if st.button("Run benchmark", type="primary"):
        with st.spinner("Probing LLM backend..."):
            try:
                with httpx.Client() as c:
                    b = c.get(f"{BACKEND_URL}/benchmark", timeout=120).json()
                st.json(b)

                if "wall_ms" in b:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Wall time", f"{b['wall_ms']:.0f}ms")
                    if "tokens_per_second" in b:
                        c2.metric("Tokens/s", f"{b['tokens_per_second']:.1f}")
                    if "eval_count" in b:
                        c3.metric("Tokens generated", b["eval_count"])
            except Exception as e:
                st.error(f"Benchmark failed: {e}")


# ── Route ─────────────────────────────────────────────────────
page = st.session_state.page
if page == "chat":
    page_chat()
elif page == "analytics":
    page_analytics()
elif page == "voice":
    page_voice()
elif page == "admin":
    page_admin()
