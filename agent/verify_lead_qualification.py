"""Phase 11 verification: run the lead qualification workflow against 3
leads chosen to land High/Medium/Low priority, confirming priority,
reasoning, CRM update, and draft follow-up are all correct. Not a pytest
suite (that's Phase 15)."""

import sys

from database.seed import main as seed_main

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent.workflows import qualify_lead  # noqa: E402
from tools.crm_tools import get_lead  # noqa: E402

# (lead_id, expected priority) -- chosen from leads.csv to hit each bucket
# under the documented scoring rules in agent/workflows.py.
CASES = [
    ("L1001", "High"),  # Medium engagement + complete info -> score 3
    ("L1004", "Medium"),  # Low engagement + complete info -> score 2
    ("L1002", "Low"),  # Low engagement + incomplete info -> score 1
]


def main() -> None:
    seed_main()

    for lead_id, expected_priority in CASES:
        print(f"=== {lead_id} (expect {expected_priority}) ===")
        result = qualify_lead(lead_id)
        print(result.report)
        print()

        assert result.success and result.found
        assert result.priority == expected_priority, f"expected {expected_priority}, got {result.priority}"
        assert result.task_id is not None, "expected a follow-up task"
        assert result.followup_id is not None, "expected a draft follow-up email"

        # Confirm the CRM update round-trips.
        lead = get_lead(lead_id)
        expected_status = "Qualified" if expected_priority in ("High", "Medium") else "Unqualified"
        assert lead.status == expected_status, f"expected status {expected_status}, got {lead.status}"

        print(f"OK: {lead_id} -> priority={result.priority} status={lead.status} "
              f"task_id={result.task_id} followup_id={result.followup_id}\n")

    print("=== L9999 (unknown lead) ===")
    result = qualify_lead("L9999")
    print(f"success={result.success} found={result.found}")
    assert result.success and not result.found
    print("OK: unknown lead handled gracefully, no crash.")


if __name__ == "__main__":
    main()
