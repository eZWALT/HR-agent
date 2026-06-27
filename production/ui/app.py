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

has_messages = len(st.session_state.messages) > 0

if not has_messages:
    user_input = st.chat_input("Ask something...", key="first_message")
    selected = st.pills("Examples", options=SUGGESTIONS, label_visibility="collapsed")
    if selected or user_input:
        msg = selected or user_input
        st.rerun()
    st.stop()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if user_input := st.chat_input("Ask a follow-up..."):
    with st.chat_message("user"):
        st.markdown(user_input)

    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        def stream_response():
            with httpx.Client() as client:
                with client.stream(
                    "POST",
                    f"{BACKEND_URL}/chat",
                    json={"message": user_input},
                    timeout=60,
                ) as r:
                    for line in r.iter_lines():
                        if not line:
                            continue
                        if line.startswith("data: ") and line != "data: [DONE]":
                            yield line[6:]

        reply = st.write_stream(stream_response())

    st.session_state.messages.append({"role": "assistant", "content": reply})
