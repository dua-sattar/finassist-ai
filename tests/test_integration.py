"""Phase 31 cross-feature integration tests: each phase (17-30) already has
its own dedicated test file exercising it in isolation. These instead check
that features actually agree with each other once wired together -- e.g.
that an approved pending change is reflected in a report, not just in the
underlying table -- since that's exactly the kind of thing unit-level tests
per phase can miss."""

from database import crud
from tools.action_center_tools import get_action_center_summary
from tools.anomaly_tools import detect_anomalies
from tools.crm_tools import propose_client_update
from tools.meeting_tools import summarize_meeting_notes
from tools.report_tools import generate_anomaly_summary_report, generate_client_portfolio_report, generate_task_report
from tools.task_tools import create_followup_task


def test_approved_client_update_is_reflected_in_portfolio_report():
    before = crud.get_client("C1007").assigned_advisor
    proposed = "Integration Test Advisor"
    result = propose_client_update("C1007", "Integration test.", assigned_advisor=proposed)
    assert result.success

    # Not applied yet -- the portfolio report should still show the old value.
    report_before = generate_client_portfolio_report()
    row_before = next(r for r in report_before.rows if r["Client ID"] == "C1007")
    assert row_before["Advisor"] == before

    approved = crud.approve_pending_change(result.change_id)
    assert approved is not None

    report_after = generate_client_portfolio_report()
    row_after = next(r for r in report_after.rows if r["Client ID"] == "C1007")
    assert row_after["Advisor"] == proposed


def test_meeting_summary_persists_and_any_created_tasks_appear_in_task_report():
    # summarize_meeting_notes only creates tasks from AI-extracted action
    # items -- with no GROQ_API_KEY (or a failed call) it honestly falls
    # back to an empty structure rather than fabricating action items, so
    # this doesn't assert task_ids_created is non-empty. What it does check,
    # deterministically regardless of Groq availability: the meeting is
    # persisted, and *if* any tasks were created, they show up in the task
    # report -- exercising the same task-creation -> task-report path that
    # a real action item would use, via a task created directly for
    # certainty.
    result = summarize_meeting_notes(
        "Call with the client. She needs to send her updated bank statement.", client_id="C1008"
    )
    assert result.success
    assert result.meeting_id is not None
    stored = crud.list_meeting_summaries(client_id="C1008")
    assert any(s.id == result.meeting_id for s in stored)

    task = create_followup_task(description="Integration test action item", client_id="C1008")
    assert task.success

    task_report = generate_task_report()
    report_task_ids = {r["Task ID"] for r in task_report.rows}
    assert task.task_id in report_task_ids
    for task_id in result.task_ids_created:
        assert task_id in report_task_ids


def test_detect_anomalies_agrees_with_anomaly_summary_report():
    doc = crud.add_document(client_id="C1009", filename="integration_bad_math.pdf", document_type="bank_statement", status="Received")
    crud.add_document_extraction(
        document_id=doc.id,
        extracted_fields={
            "client_id": "C1009", "opening_balance": 1000.0, "total_deposits": 200.0,
            "total_withdrawals": 100.0, "closing_balance": 5000.0,
        },
        missing_fields=[],
        summary="test",
    )

    single_client_result = detect_anomalies("C1009")
    assert single_client_result.success
    assert any(a.category == "Balance Mismatch" for a in single_client_result.anomalies)

    company_wide_result = generate_anomaly_summary_report()
    assert company_wide_result.success
    assert any(
        r["Client ID"] == "C1009" and r["Category"] == "Balance Mismatch" for r in company_wide_result.rows
    )


def test_pending_change_appears_and_clears_in_action_center():
    result = propose_client_update("C1010", "Integration test.", account_status="Closed")
    assert result.success

    summary_before = get_action_center_summary()
    assert summary_before.success
    assert any(item.key == f"pending-change-{result.change_id}" for item in summary_before.items)

    crud.reject_pending_change(result.change_id)

    summary_after = get_action_center_summary()
    assert not any(item.key == f"pending-change-{result.change_id}" for item in summary_after.items)
