"""Dashboard page: top-line metrics and a recent AI actions log."""

import pandas as pd
import streamlit as st

from database import crud


def render() -> None:
    st.header("Dashboard")

    try:
        clients = crud.list_clients()
        leads = crud.list_leads()
        open_tasks = crud.list_open_tasks()
        recent_actions = crud.list_ai_actions(limit=10)
    except Exception as exc:
        st.error(f"Could not load dashboard data: {exc}")
        return

    pending_documents = sum(1 for c in clients if c.onboarding_status == "Documents Pending")
    active_leads = sum(1 for lead in leads if lead.status in ("New", "Contacted", "Qualified"))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Clients", len(clients))
    col2.metric("Active Leads", active_leads)
    col3.metric("Pending Documents", pending_documents)
    col4.metric("Pending Follow-ups", len(open_tasks))

    st.subheader("Recent AI Actions")
    if not recent_actions:
        st.info("No AI actions logged yet. Try the AI Assistant or run a workflow.")
        return

    rows = [
        {
            "Timestamp": a.created_at,
            "Tool": a.tool_name,
            "Result": a.result_summary,
            "Status": a.status,
            "Human Approval": a.human_approval_status or "N/A",
        }
        for a in recent_actions
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
