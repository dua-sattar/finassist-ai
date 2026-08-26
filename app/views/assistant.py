"""AI Assistant page: chat interface backed by the LangGraph agent."""

import uuid

import streamlit as st

from agent.graph import run_agent
from database import crud


def _get_session_id() -> str:
    if "chat_session_id" not in st.session_state:
        st.session_state.chat_session_id = f"streamlit-{uuid.uuid4().hex[:12]}"
    return st.session_state.chat_session_id


def render() -> None:
    st.header("AI Assistant")
    st.caption(
        "Ask about company policies, look up clients or leads, review documents, or request "
        "follow-ups. All AI-generated recommendations require human review."
    )

    session_id = _get_session_id()

    try:
        history = crud.list_conversation_turns(session_id)
    except Exception as exc:
        st.error(f"Could not load conversation history: {exc}")
        return

    for turn in history:
        role = "user" if turn.role == "user" else "assistant"
        with st.chat_message(role):
            st.markdown(turn.content)

    prompt = st.chat_input("Ask a question or request an action...")
    if not prompt:
        return

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = run_agent(session_id, prompt)
            except Exception as exc:
                response = f"Sorry, something went wrong: {exc}"
        st.markdown(response)
