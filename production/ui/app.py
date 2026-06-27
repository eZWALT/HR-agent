import os

import streamlit as st
import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Sazoncito — HR Agent", page_icon="🎯")

SUGGESTIONS = [
    "How does the hiring process work?",
    "What positions are available?",
    "Help me screen a candidate",
]

st.html('<div style="font-size:3rem;line-height:1">🎯</div>')
st.title("Sazoncito", anchor=False)

if "messages" not in st.session_state:
    st.session_state.messages = []

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
