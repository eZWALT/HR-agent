import os

import streamlit as st
import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

if "config" not in st.session_state:
    with httpx.Client() as c:
        r = c.get(f"{BACKEND_URL}/config", timeout=10)
        st.session_state.config = r.json()
        st.session_state.messages = []
        greeting = st.session_state.config.get("greeting", "")
        if greeting:
            st.session_state.messages.append({"role": "assistant", "content": greeting})

config = st.session_state.config
client_name = config.get("client_name", "Client")
assistant_name = config.get("assistant_name", "Assistant")
emoji = config.get("emoji", "💬")

st.set_page_config(page_title=f"{client_name} — HR Agent", page_icon=emoji)
st.html(f'<div style="font-size:3rem;line-height:1">{emoji}</div>')
st.title(client_name, anchor=False)

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
        def stream():
            with httpx.Client() as c:
                with c.stream("POST", f"{BACKEND_URL}/chat", json={"message": msg}, timeout=60) as r:
                    for line in r.iter_lines():
                        if not line:
                            continue
                        if line.startswith("data: ") and line != "data: [DONE]":
                            yield line[6:]
        reply = st.write_stream(stream())
    st.session_state.messages.append({"role": "user", "content": msg})
    st.session_state.messages.append({"role": "assistant", "content": reply})
