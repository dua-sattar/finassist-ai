"""Typed schemas for structured fields extracted from FinAssist AI documents.

Every field besides `client_id` is Optional: a missing field should show up as
`None` in the validated model (and therefore in `missing_fields`) rather than
raising a validation error and crashing the pipeline. See extractor.py.
"""

from typing import Optional

from pydantic import BaseModel


class BankStatementData(BaseModel):
    client_id: str
    client_name: Optional[str] = None
    account_number: Optional[str] = None
    statement_period: Optional[str] = None
    opening_balance: Optional[float] = None
    total_deposits: Optional[float] = None
    total_withdrawals: Optional[float] = None
    closing_balance: Optional[float] = None


class FinancialSummaryData(BaseModel):
    client_id: str
    client_name: Optional[str] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    estimated_net_worth: Optional[float] = None


class TransactionReportData(BaseModel):
    client_id: str
    client_name: Optional[str] = None
    transactions_raw: Optional[str] = None


class ApplicationFormData(BaseModel):
    client_id: str
    full_name: Optional[str] = None
    requested_service: Optional[str] = None
    contact_email: Optional[str] = None
    signature: Optional[str] = None


class AccountSummaryData(BaseModel):
    client_id: str
    client_name: Optional[str] = None
    account_status: Optional[str] = None
    assigned_advisor: Optional[str] = None
    current_balance: Optional[float] = None


class GovernmentIdData(BaseModel):
    client_id: str
    full_name: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    issue_date: Optional[str] = None
    expiration_date: Optional[str] = None


class ProofOfAddressData(BaseModel):
    client_id: str
    full_name: Optional[str] = None
    proof_type: Optional[str] = None
    address: Optional[str] = None
    statement_date: Optional[str] = None


DOCUMENT_TYPE_SCHEMAS: dict[str, type[BaseModel]] = {
    "bank_statement": BankStatementData,
    "financial_summary": FinancialSummaryData,
    "transaction_report": TransactionReportData,
    "client_application_form": ApplicationFormData,
    "account_summary": AccountSummaryData,
    "government_id": GovernmentIdData,
    "proof_of_address": ProofOfAddressData,
}

# The four document categories required_documents.md requires for onboarding,
# and which generated document_type(s) satisfy each one. Used by
# tools.document_tools.check_required_documents (Phase 7).
REQUIRED_DOCUMENT_CATEGORIES: dict[str, tuple[str, ...]] = {
    "Government-issued ID": ("government_id",),
    "Proof of Address": ("proof_of_address",),
    "Recent Financial Statement": ("bank_statement", "financial_summary"),
    "Completed Application Form": ("client_application_form",),
}
