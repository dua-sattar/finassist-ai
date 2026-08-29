"""Manual verification for Phase 26 (Anomaly Detection): confirms
detect_anomalies finds a real expired government ID (C1001, expiration
2025-01-15 vs. today) and stays clean for a client with no issues.
Read-only against the real dev database on purpose -- injecting synthetic
bad-data documents (balance mismatch, negative balance, identity mismatch)
would permanently pollute database/finassist.db, so those scenarios are
covered instead in tests/test_anomaly_tools.py against pytest's isolated
temp DB (see conftest.py)."""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from database.seed import main as seed_main  # noqa: E402
from tools.anomaly_tools import detect_anomalies  # noqa: E402


def main() -> None:
    seed_main()

    print("=== Unknown client fails gracefully ===")
    result = detect_anomalies("C9999")
    assert result.success
    assert not result.found
    print("OK\n")

    print("=== C1001's real government ID is expired (expiration 2025-01-15) ===")
    result = detect_anomalies("C1001")
    assert result.success and result.found
    expired = [a for a in result.anomalies if a.category == "Expired ID"]
    assert expired, result.anomalies
    assert "2025-01-15" in expired[0].description
    assert expired[0].severity == "Medium"
    assert result.ai_observation
    assert result.recommended_action
    assert "Human Review Required" in result.report
    print(f"anomalies={[(a.category, a.severity) for a in result.anomalies]}")
    print(f"ai_observation={result.ai_observation}")
    print(f"recommended_action={result.recommended_action}")
    print("OK\n")

    print("=== C1003 has no anomalies (consistent bank statement + valid, unexpired ID) ===")
    result = detect_anomalies("C1003")
    assert result.success and result.found
    assert result.anomalies == []
    assert "no anomalies" in result.recommended_action.lower()
    print("OK\n")

    print("=== C1004 has no anomalies (bank statement math reconciles) ===")
    result = detect_anomalies("C1004")
    assert result.success and result.found
    assert result.anomalies == []
    print("OK\n")

    print("All Anomaly Detection checks passed.")


if __name__ == "__main__":
    main()
