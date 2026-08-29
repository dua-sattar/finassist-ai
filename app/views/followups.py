"""Follow-ups page: pending tasks. Follow-up email drafts (with the
Draft -> Approved -> Sent-simulated human-approval gate) now live on the
dedicated Email Center page (Phase 18)."""

import pandas as pd
import streamlit as st

from database import crud


def render() -> None:
    st.header("Follow-ups")
    st.caption("Open tasks created by the AI agent or workflows. Email drafts live in the Email Center.")

    try:
        tasks = crud.list_open_tasks()
    except Exception as exc:
        st.error(f"Could not load tasks: {exc}")
        return

    if not tasks:
        st.caption("No open tasks.")
        return

    rows = [
        {
            "Task ID": t.id,
            "Type": t.task_type,
            "Client": t.client_id or "",
            "Lead": t.lead_id or "",
            "Priority": t.priority or "",
            "Description": t.description,
            "Created": t.created_at,
        }
        for t in tasks
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
