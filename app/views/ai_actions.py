"""AI Actions page: audit log of every tool call the agent/workflows made."""

import pandas as pd
import streamlit as st

from database import crud


def render() -> None:
    st.header("AI Actions")
    st.caption("Every tool the AI agent or a workflow invokes is logged here for transparency.")

    try:
        actions = crud.list_ai_actions(limit=500)
    except Exception as exc:
        st.error(f"Could not load the AI action log: {exc}")
        return

    if not actions:
        st.info("No AI actions logged yet.")
        return

    tool_names = sorted({a.tool_name for a in actions})
    col1, col2 = st.columns(2)
    with col1:
        tool_filter = st.selectbox("Filter by tool", ["All"] + tool_names)
    with col2:
        status_filter = st.selectbox("Filter by status", ["All", "success", "error"])

    filtered = actions
    if tool_filter != "All":
        filtered = [a for a in filtered if a.tool_name == tool_filter]
    if status_filter != "All":
        filtered = [a for a in filtered if a.status == status_filter]

    st.caption(f"{len(filtered)} of {len(actions)} actions")
    rows = [
        {
            "Timestamp": a.created_at,
            "Tool": a.tool_name,
            "Input": a.input_summary,
            "Result": a.result_summary,
            "Status": a.status,
            "Human Approval": a.human_approval_status or "N/A",
        }
        for a in filtered
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
