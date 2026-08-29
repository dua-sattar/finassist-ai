"""Tests for the Phase 26 anomaly detection tool (tools/anomaly_tools.py),
against the seeded temp DB (conftest). Balance-mismatch, negative-balance,
and identity-mismatch scenarios are exercised by injecting documents
directly via database.crud, since no synthetic PDF naturally contains bad
data -- safe here because pytest's DB is an isolated temp file, unlike the
real dev database (see tools/verify_anomaly.py for why that script sticks
to read-only checks)."""

from database import crud
from tools.anomaly_tools import (
    _check_balance_math,
    _check_expired_id,
    _check_identity_consistency,
    _check_negative_balance,
    detect_anomalies,
)


def _inject_document(client_id: str, filename: str, extracted_fields: dict) -> None:
    doc = crud.add_document(client_id=client_id, filename=filename, document_type="bank_statement", status="Received")
    crud.add_document_extraction(document_id=doc.id, extracted_fields=extracted_fields, missing_fields=[], summary="test")


def test_unknown_client_returns_not_found():
    result = detect_anomalies("C9999")
    assert result.success
    assert not result.found


def test_c1001_real_government_id_is_expired():
    result = detect_anomalies("C1001")
    assert result.success and result.found
    expired = [a for a in result.anomalies if a.category == "Expired ID"]
    assert len(expired) == 1
    assert "2025-01-15" in expired[0].description
    assert "Human Review Required" in result.report


def test_c1003_has_no_anomalies():
    result = detect_anomalies("C1003")
    assert result.success and result.found
    assert result.anomalies == []
    assert "no anomalies" in result.recommended_action.lower()


def test_check_balance_math_flags_mismatch():
    anomaly = _check_balance_math(
        "f.pdf", {"opening_balance": 1000.0, "total_deposits": 500.0, "total_withdrawals": 100.0, "closing_balance": 2000.0}
    )
    assert anomaly is not None
    assert anomaly.category == "Balance Mismatch"
    assert anomaly.severity == "High"


def test_check_balance_math_accepts_reconciling_values():
    anomaly = _check_balance_math(
        "f.pdf", {"opening_balance": 1000.0, "total_deposits": 500.0, "total_withdrawals": 100.0, "closing_balance": 1400.0}
    )
    assert anomaly is None


def test_check_balance_math_skips_incomplete_data():
    anomaly = _check_balance_math("f.pdf", {"opening_balance": 1000.0})
    assert anomaly is None


def test_check_negative_balance_flags_negative_closing_balance():
    anomaly = _check_negative_balance("f.pdf", {"closing_balance": -50.0})
    assert anomaly is not None
    assert anomaly.category == "Negative Balance"


def test_check_negative_balance_ignores_positive_balance():
    assert _check_negative_balance("f.pdf", {"closing_balance": 50.0}) is None


def test_check_expired_id_flags_past_expiration_date():
    anomaly = _check_expired_id("f.pdf", {"expiration_date": "2020-01-01"})
    assert anomaly is not None
    assert anomaly.category == "Expired ID"


def test_check_expired_id_ignores_future_expiration_date():
    assert _check_expired_id("f.pdf", {"expiration_date": "2099-01-01"}) is None


def test_check_identity_consistency_flags_differing_client_ids():
    anomalies = _check_identity_consistency([("a.pdf", {"client_id": "C1001"}), ("b.pdf", {"client_id": "C9999"})])
    assert any(a.category == "Identity Mismatch" for a in anomalies)


def test_check_identity_consistency_ignores_matching_records():
    anomalies = _check_identity_consistency(
        [("a.pdf", {"client_id": "C1001", "client_name": "Allison Hill"}), ("b.pdf", {"client_id": "C1001", "client_name": "Allison Hill"})]
    )
    assert anomalies == []


def test_detect_anomalies_flags_injected_balance_mismatch():
    _inject_document(
        "C1004",
        "injected_bad_math.pdf",
        {
            "client_id": "C1004", "client_name": "Daniel Wagner", "opening_balance": 1000.0,
            "total_deposits": 500.0, "total_withdrawals": 100.0, "closing_balance": 2000.0,
        },
    )
    result = detect_anomalies("C1004")
    assert result.success and result.found
    mismatch = [a for a in result.anomalies if a.category == "Balance Mismatch"]
    assert len(mismatch) == 1
    assert mismatch[0].severity == "High"
    assert "escalate" in result.recommended_action.lower()


def test_detect_anomalies_flags_injected_negative_balance():
    _inject_document("C1005", "injected_negative.pdf", {"client_id": "C1005", "closing_balance": -250.0})
    result = detect_anomalies("C1005")
    assert result.success and result.found
    negative = [a for a in result.anomalies if a.category == "Negative Balance"]
    assert len(negative) == 1


def test_detect_anomalies_flags_injected_identity_mismatch():
    _inject_document("C1006", "injected_wrong_identity.pdf", {"client_id": "C9999", "client_name": "Someone Else"})
    result = detect_anomalies("C1006")
    assert result.success and result.found
    identity = [a for a in result.anomalies if a.category == "Identity Mismatch"]
    assert identity
