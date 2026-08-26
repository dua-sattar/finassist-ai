"""Follow-ups page: pending tasks, plus follow-up email drafts with the
Draft -> Approved -> Sent-simulated human-approval gate (Phase 12)."""

import pandas as pd
import streamlit as st

from app.components.status_badge import render_status_badge
from database import crud


def render() -> None:
    st.header("Follow-ups")

    st.subheader("Open Tasks")
    try:
        tasks = crud.list_open_tasks()
    except Exception as exc:
        st.error(f"Could not load tasks: {exc}")
        return

    if tasks:
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
    else:
        st.caption("No open tasks.")

    st.divider()
    st.subheader("Follow-up Email Drafts")
    st.caption(
        "Emails are drafted by the AI but never sent automatically. A human must approve a draft "
        "before it can be marked sent (simulated only -- no real email is ever sent)."
    )

    try:
        followups = crud.list_followups()
    except Exception as exc:
        st.error(f"Could not load follow-up emails: {exc}")
        return

    if not followups:
        st.caption("No follow-up emails yet.")
        return

    status_filter = st.selectbox("Filter by status", ["All", "Draft", "Approved", "Sent-simulated"])
    filtered = followups if status_filter == "All" else [f for f in followups if f.status == status_filter]

    for f in filtered:
        with st.expander(f"#{f.id} -- {f.subject} ({f.status})"):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**To:** {f.client_id or f.lead_id or 'unknown'}  \n**Channel:** {f.channel}")
                st.text(f.body)
            with col2:
                render_status_badge(f.status)

            if f.status == "Draft":
                if st.button("Approve", key=f"approve-{f.id}"):
                    crud.approve_followup(f.id)
                    st.rerun()
            elif f.status == "Approved":
                if st.button("Send (Simulated)", key=f"send-{f.id}"):
                    crud.simulate_send(f.id)
                    st.rerun()
            else:
                st.caption("This follow-up has been sent (simulated).")
