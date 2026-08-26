"""Knowledge Base page: ask a question about company policy, get a grounded
answer with its source documents shown."""

import streamlit as st

from rag.answer import answer_question

EXAMPLE_QUESTIONS = [
    "What documents are required for client onboarding?",
    "What is FinAssist AI's refund policy?",
    "How do I close my account?",
    "What services does FinAssist AI offer?",
]


def render() -> None:
    st.header("Knowledge Base")
    st.caption(
        "Ask a question about FinAssist AI's internal policies. Answers are grounded in the "
        "knowledge base -- if the answer isn't in the docs, the assistant will say so rather "
        "than invent one."
    )

    with st.expander("Example questions"):
        for q in EXAMPLE_QUESTIONS:
            st.markdown(f"- {q}")

    query = st.text_input("Your question", placeholder="e.g. What documents are required for onboarding?")
    ask_clicked = st.button("Ask", type="primary", disabled=not query)

    if not ask_clicked:
        return

    with st.spinner("Searching the knowledge base..."):
        try:
            result = answer_question(query)
        except Exception as exc:
            st.error(f"Something went wrong: {exc}")
            return

    if not result.success:
        st.error(result.error or "Could not generate an answer.")
        if result.sources:
            st.caption(f"Retrieved sources: {', '.join(result.sources)}")
        return

    st.markdown(result.answer)

    if result.sources:
        st.caption("Source document(s): " + ", ".join(f"`{s}`" for s in result.sources))
    else:
        st.caption("No matching source documents were found in the knowledge base.")
