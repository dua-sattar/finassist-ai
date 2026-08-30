"""AI Action Center: a prioritized "what needs attention today" digest,
aggregating open tasks, documents-pending clients, draft emails awaiting
approval, pending CRM changes awaiting approval (Phase 30), and new leads --
distinct from the AI Actions page, which is a historical audit log rather
than a forward-looking triage list (spec section 19)."""

import streamlit as st

from app.components.status_badge import render_status_badge
from tools.action_center_tools import get_action_center_summary


def render() -> None:
    st.header("AI Action Center")
    st.caption("What needs attention today, aggregated across the whole system.")

    with st.spinner("Loading action items..."):
        summary = get_action_center_summary()

    if not summary.success:
        st.error(f"Could not load the action center: {summary.error}")
        return

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("🔴 High Priority", summary.high_priority_count)
    col2.metric("🟡 Open Follow-ups", summary.followups_count)
    col3.metric("📄 Documents Pending", summary.documents_pending_count)
    col4.metric("📧 Emails Pending", summary.emails_awaiting_approval_count)
    col5.metric("✅ Approvals Pending", summary.pending_changes_count)
    col6.metric("🆕 New Leads", summary.new_leads_count)

    st.divider()

    if not summary.items:
        st.info("Nothing needs attention right now.")
        return

    for item in summary.items:
        with st.expander(f"{item.record_id} -- {item.category} -> {item.recommended_action}"):
            col_a, col_b = st.columns([1, 3])
            with col_a:
                st.markdown("**Priority:**")
                render_status_badge(item.priority)
            with col_b:
                st.markdown(f"**Recommended Action:** {item.recommended_action}")
                st.caption(item.detail)
            st.caption("Human review required before acting on this recommendation.")
