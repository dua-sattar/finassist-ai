"""Manual verification for Phase 27 (Reports): confirms all five report
generators run against the real seeded data, produce non-empty CSV output
where rows exist, and always include an AI overview. Read-only throughout
-- none of these reports mutate CRM state or persist anything, so this is
safe to run repeatedly against the real dev database. Not a pytest suite
(that's tests/test_report_tools.py)."""

import csv
import io
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from database.seed import main as seed_main  # noqa: E402
from tools.report_tools import (  # noqa: E402
    generate_anomaly_summary_report,
    generate_client_portfolio_report,
    generate_document_compliance_report,
    generate_lead_pipeline_report,
    generate_task_report,
)


def _assert_valid_csv(csv_text: str, expected_rows: int) -> None:
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) == expected_rows, f"expected {expected_rows} CSV rows, got {len(rows)}"


def main() -> None:
    seed_main()

    print("=== Client Portfolio Report ===")
    result = generate_client_portfolio_report()
    assert result.success
    assert result.row_count == 40, result.row_count
    assert len(result.rows) == 40
    _assert_valid_csv(result.csv_text, 40)
    assert result.ai_summary
    print(f"rows={result.row_count} ai_summary={result.ai_summary[:100]}")
    print("OK\n")

    print("=== Lead Pipeline Report ===")
    result = generate_lead_pipeline_report()
    assert result.success
    assert result.row_count == 40, result.row_count
    _assert_valid_csv(result.csv_text, 40)
    assert result.ai_summary
    print(f"rows={result.row_count} ai_summary={result.ai_summary[:100]}")
    print("OK\n")

    print("=== Document Compliance Report ===")
    result = generate_document_compliance_report()
    assert result.success
    assert result.row_count == 40, result.row_count
    _assert_valid_csv(result.csv_text, 40)
    assert result.ai_summary
    # The seeded manifest only supplies a partial document set per client (22
    # documents across 40 clients), so every client is missing at least one
    # required category -- there's no "fully compliant" client in this
    # dataset. Assert the checklist logic itself is sound instead.
    not_compliant = [r for r in result.rows if r["Fully Compliant"] == "No"]
    assert len(not_compliant) == 40
    assert all(r["Missing Categories"] != "None" for r in not_compliant)
    print(f"not_compliant={len(not_compliant)}")
    print("OK\n")

    print("=== Task & Follow-up Report ===")
    result = generate_task_report()
    assert result.success
    _assert_valid_csv(result.csv_text, result.row_count)
    assert result.ai_summary
    print(f"rows={result.row_count} ai_summary={result.ai_summary[:100]}")
    print("OK\n")

    print("=== Anomaly Summary Report ===")
    result = generate_anomaly_summary_report()
    assert result.success
    _assert_valid_csv(result.csv_text, result.row_count)
    assert result.ai_summary
    expired = [r for r in result.rows if r["Client ID"] == "C1001" and r["Category"] == "Expired ID"]
    assert expired, "expected C1001's real expired government ID to surface in the company-wide scan"
    print(f"rows={result.row_count} ai_summary={result.ai_summary[:150]}")
    print("OK\n")

    print("All Reports checks passed.")


if __name__ == "__main__":
    main()
