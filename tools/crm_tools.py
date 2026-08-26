"""get_client, get_lead, update_client, update_lead tools -- wrap
database/crud.py's client and lead functions with typed, never-raising
results."""

import logging
from datetime import date

from pydantic import BaseModel

from database import crud
from tools.common import log_action

logger = logging.getLogger(__name__)


class ClientResult(BaseModel):
    success: bool
    client_id: str
    found: bool = False
    name: str | None = None
    email: str | None = None
    service: str | None = None
    account_status: str | None = None
    onboarding_status: str | None = None
    assigned_advisor: str | None = None
    last_contact: date | None = None
    created_date: date | None = None
    error: str | None = None


def get_client(client_id: str) -> ClientResult:
    """Look up a client record by client_id."""
    try:
        client = crud.get_client(client_id)
        if client is None:
            log_action("get_client", f"client_id={client_id}", "not found")
            return ClientResult(success=True, client_id=client_id, found=False)

        log_action("get_client", f"client_id={client_id}", f"found: {client.name}")
        return ClientResult(
            success=True,
            client_id=client.client_id,
            found=True,
            name=client.name,
            email=client.email,
            service=client.service,
            account_status=client.account_status,
            onboarding_status=client.onboarding_status,
            assigned_advisor=client.assigned_advisor,
            last_contact=client.last_contact,
            created_date=client.created_date,
        )
    except Exception as exc:
        logger.warning("get_client failed for %s: %s", client_id, exc)
        log_action("get_client", f"client_id={client_id}", str(exc), status="error")
        return ClientResult(success=False, client_id=client_id, error=str(exc))


class LeadResult(BaseModel):
    success: bool
    lead_id: str
    found: bool = False
    name: str | None = None
    email: str | None = None
    company: str | None = None
    service_interest: str | None = None
    engagement_level: str | None = None
    information_complete: bool | None = None
    source: str | None = None
    status: str | None = None
    created_date: date | None = None
    last_contact: date | None = None
    error: str | None = None


def get_lead(lead_id: str) -> LeadResult:
    """Look up a lead record by lead_id."""
    try:
        lead = crud.get_lead(lead_id)
        if lead is None:
            log_action("get_lead", f"lead_id={lead_id}", "not found")
            return LeadResult(success=True, lead_id=lead_id, found=False)

        log_action("get_lead", f"lead_id={lead_id}", f"found: {lead.name}")
        return LeadResult(
            success=True,
            lead_id=lead.lead_id,
            found=True,
            name=lead.name,
            email=lead.email,
            company=lead.company,
            service_interest=lead.service_interest,
            engagement_level=lead.engagement_level,
            information_complete=lead.information_complete,
            source=lead.source,
            status=lead.status,
            created_date=lead.created_date,
            last_contact=lead.last_contact,
        )
    except Exception as exc:
        logger.warning("get_lead failed for %s: %s", lead_id, exc)
        log_action("get_lead", f"lead_id={lead_id}", str(exc), status="error")
        return LeadResult(success=False, lead_id=lead_id, error=str(exc))


class UpdateResult(BaseModel):
    success: bool
    record_id: str
    found: bool = False
    updated_fields: dict = {}
    error: str | None = None


def update_client(
    client_id: str,
    account_status: str | None = None,
    onboarding_status: str | None = None,
    assigned_advisor: str | None = None,
) -> UpdateResult:
    """Update mutable fields on a client record. Only non-None arguments are applied."""
    fields = {
        k: v
        for k, v in {
            "account_status": account_status,
            "onboarding_status": onboarding_status,
            "assigned_advisor": assigned_advisor,
        }.items()
        if v is not None
    }
    try:
        if not fields:
            log_action("update_client", f"client_id={client_id}", "no fields provided")
            return UpdateResult(success=True, record_id=client_id, found=True, updated_fields={})

        client = crud.update_client(client_id, **fields)
        if client is None:
            log_action("update_client", f"client_id={client_id} fields={fields}", "not found")
            return UpdateResult(success=True, record_id=client_id, found=False)

        log_action(
            "update_client", f"client_id={client_id} fields={fields}", "updated", human_approval_status="N/A"
        )
        return UpdateResult(success=True, record_id=client_id, found=True, updated_fields=fields)
    except Exception as exc:
        logger.warning("update_client failed for %s: %s", client_id, exc)
        log_action("update_client", f"client_id={client_id} fields={fields}", str(exc), status="error")
        return UpdateResult(success=False, record_id=client_id, error=str(exc))


def update_lead(
    lead_id: str,
    status: str | None = None,
    engagement_level: str | None = None,
    information_complete: bool | None = None,
) -> UpdateResult:
    """Update mutable fields on a lead record. Only non-None arguments are applied."""
    fields = {
        k: v
        for k, v in {
            "status": status,
            "engagement_level": engagement_level,
            "information_complete": information_complete,
        }.items()
        if v is not None
    }
    try:
        if not fields:
            log_action("update_lead", f"lead_id={lead_id}", "no fields provided")
            return UpdateResult(success=True, record_id=lead_id, found=True, updated_fields={})

        lead = crud.update_lead(lead_id, **fields)
        if lead is None:
            log_action("update_lead", f"lead_id={lead_id} fields={fields}", "not found")
            return UpdateResult(success=True, record_id=lead_id, found=False)

        log_action("update_lead", f"lead_id={lead_id} fields={fields}", "updated", human_approval_status="N/A")
        return UpdateResult(success=True, record_id=lead_id, found=True, updated_fields=fields)
    except Exception as exc:
        logger.warning("update_lead failed for %s: %s", lead_id, exc)
        log_action("update_lead", f"lead_id={lead_id} fields={fields}", str(exc), status="error")
        return UpdateResult(success=False, record_id=lead_id, error=str(exc))
