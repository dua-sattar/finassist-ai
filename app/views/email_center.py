"""Email Center: compose, AI-generate, or template-fill email drafts, then
move them through the Draft -> Follow-ups (Approved) -> Sent/Simulated
human-approval lifecycle. No real email is ever sent."""

import pandas as pd
import streamlit as st

from database import crud
from tools.email_templates import EMAIL_TEMPLATES, render_template
from tools.email_tools import compose_email, edit_email_draft, generate_followup_email, regenerate_email_draft


def _recipient_picker(key_prefix: str) -> tuple[str | None, str | None, str | None, str]:
    """Renders a recipient-type + recipient selectbox.
    Returns (client_id, lead_id, recipient_name, service_or_interest)."""
    recipient_type = st.radio("Recipient type", ["Client", "Lead"], key=f"{key_prefix}-type", horizontal=True)

    if recipient_type == "Client":
        clients = crud.list_clients()
        if not clients:
            st.warning("No clients found.")
            return None, None, None, ""
        options = {f"{c.client_id} -- {c.name}": c for c in clients}
        label = st.selectbox("Client", list(options.keys()), key=f"{key_prefix}-client")
        c = options[label]
        return c.client_id, None, c.name, c.service

    leads = crud.list_leads()
    if not leads:
        st.warning("No leads found.")
        return None, None, None, ""
    options = {f"{lead.lead_id} -- {lead.name}": lead for lead in leads}
    label = st.selectbox("Lead", list(options.keys()), key=f"{key_prefix}-lead")
    lead = options[label]
    return None, lead.lead_id, lead.name, lead.service_interest


def _render_compose_tab() -> None:
    st.subheader("Compose Email")
    client_id, lead_id, recipient_name, _service = _recipient_picker("compose")
    subject = st.text_input("Subject", key="compose-subject")
    body = st.text_area("Body", height=200, key="compose-body")

    if st.button(
        "Save as Draft", key="compose-save", type="primary", disabled=not (recipient_name and subject and body)
    ):
        result = compose_email(subject=subject, body=body, client_id=client_id, lead_id=lead_id, source="manual")
        if result.success:
            st.success(f"Draft #{result.followup_id} saved. Review it in the Drafts tab.")
        else:
            st.error(f"Could not save draft: {result.error}")


def _render_ai_generate_tab() -> None:
    st.subheader("AI Generate Email")
    client_id, lead_id, recipient_name, _service = _recipient_picker("aigen")
    reason = st.text_input("Reason for this email", placeholder="e.g. Missing government ID", key="aigen-reason")
    context = st.text_area("Additional context (optional)", key="aigen-context")

    if st.button("Generate Draft", key="aigen-generate", type="primary", disabled=not (recipient_name and reason)):
        with st.spinner("Drafting with AI..."):
            result = generate_followup_email(
                reason=reason, recipient_name=recipient_name, context=context, client_id=client_id, lead_id=lead_id
            )
        if result.success:
            st.success(f"Draft #{result.followup_id} generated.")
            st.markdown(f"**Subject:** {result.subject}")
            st.text(result.body)
            st.caption("Review, edit, or regenerate it in the Drafts tab before approving.")
        else:
            st.error(f"Could not generate draft: {result.error}")


def _render_templates_tab() -> None:
    st.subheader("Templates")
    template_name = st.selectbox("Template", list(EMAIL_TEMPLATES.keys()), key="tmpl-name")
    client_id, lead_id, recipient_name, service = _recipient_picker("tmpl")
    details = st.text_input("Details to fill in", placeholder="e.g. Proof of Address", key="tmpl-details")

    if not recipient_name:
        return

    subject, body = render_template(template_name, recipient_name=recipient_name, service=service or "", details=details)
    st.markdown("**Preview**")
    st.markdown(f"**Subject:** {subject}")
    st.text(body)

    if st.button("Save as Draft", key="tmpl-save", type="primary"):
        result = compose_email(subject=subject, body=body, client_id=client_id, lead_id=lead_id, source="template")
        if result.success:
            st.success(f"Draft #{result.followup_id} saved. Review it in the Drafts tab.")
        else:
            st.error(f"Could not save draft: {result.error}")


def _render_drafts_tab() -> None:
    st.subheader("Drafts")
    st.caption("Emails are drafted here but never sent automatically. Review, edit, or regenerate, then approve.")
    try:
        drafts = crud.list_followups(status="Draft")
    except Exception as exc:
        st.error(f"Could not load drafts: {exc}")
        return

    if not drafts:
        st.caption("No drafts.")
        return

    for f in drafts:
        with st.expander(f"#{f.id} -- {f.subject} ({f.source})"):
            st.markdown(f"**To:** {f.client_id or f.lead_id or 'unknown'}  \n**Source:** {f.source}")
            edit_key = f"draft-editing-{f.id}"

            if st.session_state.get(edit_key, False):
                new_subject = st.text_input("Subject", value=f.subject, key=f"subject-{f.id}")
                new_body = st.text_area("Body", value=f.body, height=200, key=f"body-{f.id}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Save Changes", key=f"save-{f.id}", type="primary"):
                        result = edit_email_draft(f.id, new_subject, new_body)
                        if result.success:
                            st.session_state[edit_key] = False
                            st.rerun()
                        else:
                            st.error(result.error)
                with col2:
                    if st.button("Cancel", key=f"cancel-{f.id}"):
                        st.session_state[edit_key] = False
                        st.rerun()
            else:
                st.text(f.body)
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("Edit", key=f"editbtn-{f.id}"):
                        st.session_state[edit_key] = True
                        st.rerun()
                with col2:
                    if f.source == "ai_generated" and st.button("Regenerate", key=f"regen-{f.id}"):
                        with st.spinner("Regenerating..."):
                            result = regenerate_email_draft(
                                f.id,
                                reason=f.reason or "",
                                recipient_name=f.recipient_name or "",
                                context=f.context or "",
                            )
                        if result.success:
                            st.rerun()
                        else:
                            st.error(result.error)
                with col3:
                    if st.button("Approve", key=f"approve-{f.id}", type="primary"):
                        try:
                            crud.approve_followup(f.id)
                        except Exception as exc:
                            st.error(f"Could not approve: {exc}")
                        else:
                            st.rerun()


def _render_followups_tab() -> None:
    st.subheader("Follow-ups (Approved, awaiting send)")
    try:
        approved = crud.list_followups(status="Approved")
    except Exception as exc:
        st.error(f"Could not load approved follow-ups: {exc}")
        return

    if not approved:
        st.caption("No approved follow-ups awaiting send.")
        return

    for f in approved:
        with st.expander(f"#{f.id} -- {f.subject}"):
            st.markdown(f"**To:** {f.client_id or f.lead_id or 'unknown'}")
            st.text(f.body)
            if st.button("Send (Simulated)", key=f"send-{f.id}", type="primary"):
                try:
                    crud.simulate_send(f.id)
                except Exception as exc:
                    st.error(f"Could not send: {exc}")
                else:
                    st.rerun()


def _render_sent_tab() -> None:
    st.subheader("Sent / Simulated")
    st.caption("No real email is ever sent -- this reflects simulated delivery only.")
    try:
        sent = crud.list_followups(status="Sent-simulated")
    except Exception as exc:
        st.error(f"Could not load sent follow-ups: {exc}")
        return

    if not sent:
        st.caption("None yet.")
        return

    rows = [
        {"ID": f.id, "Subject": f.subject, "To": f.client_id or f.lead_id or "", "Created": f.created_at}
        for f in sent
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render() -> None:
    st.header("Email Center")

    tabs = st.tabs(["Compose", "AI Generate", "Templates", "Drafts", "Follow-ups", "Sent / Simulated"])
    with tabs[0]:
        _render_compose_tab()
    with tabs[1]:
        _render_ai_generate_tab()
    with tabs[2]:
        _render_templates_tab()
    with tabs[3]:
        _render_drafts_tab()
    with tabs[4]:
        _render_followups_tab()
    with tabs[5]:
        _render_sent_tab()
