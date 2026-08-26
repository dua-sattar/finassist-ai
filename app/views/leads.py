"""Lead Management page: browse leads and run the qualification workflow."""

import pandas as pd
import streamlit as st

from agent.workflows import qualify_lead
from app.components.status_badge import render_status_badge
from database import crud


def render() -> None:
    st.header("Lead Management")

    try:
        all_leads = crud.list_leads()
    except Exception as exc:
        st.error(f"Could not load leads: {exc}")
        return

    status_filter = st.selectbox("Filter by status", ["All", "New", "Contacted", "Qualified", "Unqualified"])
    filtered = all_leads if status_filter == "All" else [lead for lead in all_leads if lead.status == status_filter]

    st.caption(f"{len(filtered)} of {len(all_leads)} leads")
    rows = [
        {
            "Lead ID": lead.lead_id,
            "Name": lead.name,
            "Company": lead.company,
            "Service Interest": lead.service_interest,
            "Engagement": lead.engagement_level,
            "Info Complete": "Yes" if lead.information_complete else "No",
            "Status": lead.status,
        }
        for lead in filtered
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if not filtered:
        return

    st.divider()
    st.subheader("Lead Detail")
    options = {f"{lead.lead_id} -- {lead.name}": lead.lead_id for lead in filtered}
    selected_label = st.selectbox("Select a lead", list(options.keys()))
    lead_id = options[selected_label]
    lead = next(item for item in filtered if item.lead_id == lead_id)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Company:** {lead.company}")
        st.markdown(f"**Service Interest:** {lead.service_interest}")
        st.markdown(f"**Source:** {lead.source}")
    with col2:
        st.markdown("**Status:**")
        render_status_badge(lead.status)
        st.markdown("**Engagement Level:**")
        render_status_badge(lead.engagement_level)

    report_key = f"last_qualification_report_{lead_id}"
    if st.button("Qualify Lead", type="primary", key=f"qualify-{lead_id}"):
        with st.spinner("Applying qualification rules..."):
            result = qualify_lead(lead_id)
        st.session_state[report_key] = result.report
        st.rerun()

    if st.session_state.get(report_key):
        st.text(st.session_state[report_key])
