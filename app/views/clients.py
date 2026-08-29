"""Client Management page: search/browse clients and view a full profile
(info, documents, onboarding status, open tasks/follow-ups)."""

import pandas as pd
import streamlit as st

from agent.workflows import review_client_documents
from app.components.status_badge import render_status_badge
from database import crud
from tools.summary_tools import generate_case_summary


def render() -> None:
    st.header("Client Management")

    try:
        all_clients = crud.list_clients()
    except Exception as exc:
        st.error(f"Could not load clients: {exc}")
        return

    search = st.text_input("Search by client ID or name", placeholder="e.g. C1002 or Noah")
    filtered = all_clients
    if search:
        needle = search.strip().lower()
        filtered = [c for c in all_clients if needle in c.client_id.lower() or needle in c.name.lower()]

    st.caption(f"{len(filtered)} of {len(all_clients)} clients")
    rows = [
        {
            "Client ID": c.client_id,
            "Name": c.name,
            "Service": c.service,
            "Account Status": c.account_status,
            "Onboarding Status": c.onboarding_status,
            "Advisor": c.assigned_advisor,
        }
        for c in filtered
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if not filtered:
        return

    st.divider()
    st.subheader("Client Detail")
    options = {f"{c.client_id} -- {c.name}": c.client_id for c in filtered}
    selected_label = st.selectbox("Select a client", list(options.keys()))
    client_id = options[selected_label]
    client = next(c for c in filtered if c.client_id == client_id)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**Email:** {client.email}")
        st.markdown(f"**Service:** {client.service}")
    with col2:
        st.markdown("**Account Status:**")
        render_status_badge(client.account_status)
        st.markdown("**Onboarding Status:**")
        render_status_badge(client.onboarding_status)
    with col3:
        st.markdown(f"**Advisor:** {client.assigned_advisor}")
        st.markdown(f"**Last Contact:** {client.last_contact}")

    try:
        docs = crud.list_documents_for_client(client_id)
        open_tasks = crud.list_open_tasks(client_id=client_id)
        followups = [f for f in crud.list_followups() if f.client_id == client_id]
    except Exception as exc:
        st.error(f"Could not load client activity: {exc}")
        return

    st.markdown("**Documents on file**")
    if docs:
        doc_rows = [{"Filename": d.filename, "Type": d.document_type, "Status": d.status} for d in docs]
        st.dataframe(pd.DataFrame(doc_rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No documents on file yet.")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Open Tasks**")
        if open_tasks:
            for t in open_tasks:
                st.markdown(f"- [{t.priority or 'Normal'}] {t.description}")
        else:
            st.caption("None.")
    with col_b:
        st.markdown("**Follow-up Emails**")
        if followups:
            for f in followups:
                st.markdown(f"- *{f.subject}* -- {f.status}")
        else:
            st.caption("None.")

    st.divider()
    review_key = f"last_review_report_{client_id}"
    summary_key = f"last_case_summary_{client_id}"

    col_review, col_summary = st.columns(2)
    with col_review:
        if st.button("Run Document Review Workflow", key=f"review-{client_id}"):
            with st.spinner("Reviewing required documents..."):
                result = review_client_documents(client_id)
            st.session_state[review_key] = result.report
            st.session_state.pop(summary_key, None)
            st.rerun()
    with col_summary:
        if st.button("Generate Case Summary", key=f"summary-{client_id}"):
            with st.spinner("Generating AI case summary..."):
                result = generate_case_summary(client_id)
            if result.success:
                st.session_state[summary_key] = result.report
                st.session_state.pop(review_key, None)
            else:
                st.error(f"Could not generate case summary: {result.error}")
            st.rerun()

    if st.session_state.get(review_key):
        st.text(st.session_state[review_key])
    elif st.session_state.get(summary_key):
        st.text(st.session_state[summary_key])
