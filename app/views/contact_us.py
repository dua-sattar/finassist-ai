"""Contact Us page: public-facing intake form (spec section 17) plus an
internal Submissions tab for staff to review AI classification and act on
the suggested response (spec section 18)."""

import pandas as pd
import streamlit as st

from agent.workflows import process_contact_submission
from app.components.status_badge import render_status_badge
from database import crud
from tools.email_tools import compose_email


def _render_submit_tab() -> None:
    st.subheader("Get in Touch")
    st.caption("Fields marked * are required.")

    name = st.text_input("Name *", key="contact-name")
    email = st.text_input("Email *", key="contact-email")
    phone = st.text_input("Phone (optional)", key="contact-phone")
    subject = st.text_input("Subject *", key="contact-subject")
    message = st.text_area("Message *", height=150, key="contact-message")

    required_filled = bool(name and email and subject and message)
    if st.button("Submit", type="primary", disabled=not required_filled):
        with st.spinner("Submitting and classifying your request..."):
            result = process_contact_submission(
                name=name, email=email, subject=subject, message=message, phone=phone or None
            )

        if not result.success:
            st.error(f"Could not submit your request: {result.error}")
            return

        st.success(f"Thank you, {name}! Your request (#{result.submission_id}) has been received.")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Category:**")
            render_status_badge(result.category)
        with col2:
            st.markdown("**Priority:**")
            render_status_badge(result.priority)

        if result.created_lead_id:
            st.info(
                f"This looks like new-business interest -- lead {result.created_lead_id} was created and "
                f"qualified as **{result.lead_qualification.priority if result.lead_qualification else 'N/A'}** "
                "priority. A member of our team will follow up."
            )
        elif result.task_id:
            st.caption(f"A follow-up task (#{result.task_id}) was created for our team.")

        st.markdown("**AI-suggested response** (for internal review -- not sent to you automatically):")
        st.info(result.suggested_response or "(none)")


def _render_submissions_tab() -> None:
    st.subheader("Submissions (Internal)")
    st.caption("Staff view of incoming Contact Us requests, their AI classification, and suggested response.")

    try:
        submissions = crud.list_contact_submissions()
    except Exception as exc:
        st.error(f"Could not load submissions: {exc}")
        return

    if not submissions:
        st.caption("No submissions yet.")
        return

    category_options = ["All"] + sorted({s.category for s in submissions if s.category})
    category_filter = st.selectbox("Filter by category", category_options)
    filtered = submissions if category_filter == "All" else [s for s in submissions if s.category == category_filter]

    rows = [
        {
            "ID": s.id,
            "Name": s.name,
            "Subject": s.subject,
            "Category": s.category,
            "Priority": s.priority,
            "Lead": s.lead_id or "",
            "Status": s.status,
            "Created": s.created_at,
        }
        for s in filtered
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    for s in filtered:
        with st.expander(f"#{s.id} -- {s.subject} ({s.category or 'Unclassified'})"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**From:** {s.name} <{s.email}>  \n**Phone:** {s.phone or 'n/a'}")
                st.markdown("**Priority:**")
                render_status_badge(s.priority)
            with col2:
                if s.lead_id:
                    st.markdown(f"**Converted to lead:** {s.lead_id}")
                st.markdown("**Status:**")
                render_status_badge(s.status)

            st.markdown("**Message**")
            st.text(s.message)
            st.markdown("**AI-suggested response**")
            st.info(s.ai_suggested_response or "(none)")

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Draft this as an email", key=f"draft-{s.id}"):
                    result = compose_email(
                        subject=f"Re: {s.subject}",
                        body=s.ai_suggested_response or "",
                        lead_id=s.lead_id,
                        to_email=None if s.lead_id else s.email,
                        source="ai_generated",
                    )
                    if result.success:
                        st.success(f"Draft #{result.followup_id} created. Review it in the Email Center.")
                    else:
                        st.error(f"Could not create draft: {result.error}")
            with col_b:
                if s.status == "New" and st.button("Mark Reviewed", key=f"review-{s.id}"):
                    try:
                        crud.update_contact_submission(s.id, status="Reviewed")
                    except Exception as exc:
                        st.error(f"Could not update status: {exc}")
                    else:
                        st.rerun()


def render() -> None:
    st.header("Contact Us")

    tabs = st.tabs(["Submit a Request", "Submissions (Internal)"])
    with tabs[0]:
        _render_submit_tab()
    with tabs[1]:
        _render_submissions_tab()
