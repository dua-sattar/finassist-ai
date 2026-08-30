"""Reports page (spec section 24): generate and download one of five
aggregate reports built from data already tracked elsewhere in the app --
client portfolio, lead pipeline, document compliance, tasks & follow-ups,
and a company-wide anomaly summary."""

import pandas as pd
import streamlit as st

from tools.report_tools import (
    generate_anomaly_summary_report,
    generate_client_portfolio_report,
    generate_document_compliance_report,
    generate_lead_pipeline_report,
    generate_task_report,
)

_REPORT_GENERATORS = {
    "Client Portfolio Report": generate_client_portfolio_report,
    "Lead Pipeline Report": generate_lead_pipeline_report,
    "Document Compliance Report": generate_document_compliance_report,
    "Task & Follow-up Report": generate_task_report,
    "Anomaly Summary Report": generate_anomaly_summary_report,
}


def render() -> None:
    st.header("Reports")
    st.caption("Generate a report from current data and download it as a CSV file.")

    report_label = st.selectbox("Report type", list(_REPORT_GENERATORS.keys()))

    if st.button("Generate Report", type="primary"):
        with st.spinner(f"Generating {report_label}..."):
            result = _REPORT_GENERATORS[report_label]()
        st.session_state["last_report"] = result

    result = st.session_state.get("last_report")
    if result is None:
        return

    if not result.success:
        st.error(f"Could not generate report: {result.error}")
        return

    st.subheader(result.title)
    st.caption(f"Generated {result.generated_at} -- {result.row_count} row(s)")

    st.markdown("**AI Overview**")
    st.info(result.ai_summary or "(no overview available)")

    if result.rows:
        st.dataframe(pd.DataFrame(result.rows), use_container_width=True, hide_index=True)
        st.download_button(
            "Download CSV",
            data=result.csv_text,
            file_name=f"{result.report_type}.csv",
            mime="text/csv",
        )
    else:
        st.caption("No rows to display for this report.")
