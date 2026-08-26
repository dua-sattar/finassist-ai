# Client Onboarding Policy

> Portfolio demonstration — fictional onboarding process for FinAssist AI.

## Onboarding Stages

New clients move through four onboarding stages, tracked in the CRM as
`onboarding_status`:

1. **Lead** — Initial inquiry received; no application submitted yet.
2. **Application Submitted** — Client has completed the application form but
   supporting documents are still outstanding.
3. **Documents Pending** — One or more required documents (see
   `required_documents.md`) have not yet been received or verified.
4. **Complete** — All required documents have been received and verified; the
   client's `account_status` is updated to Active.

## Process

1. A prospective client is added to the system as a lead and assigned a service
   interest.
2. Once the client confirms interest, an advisor sends the application form and the
   list of required documents.
3. As documents arrive, operations staff (or the FinAssist AI assistant, with human
   review) check them against the required documents checklist.
4. When all required documents are verified, the client's onboarding status is set to
   Complete and an advisor is formally assigned.
5. Any missing or incomplete documents trigger a follow-up task and a draft
   communication requesting the outstanding item.

## Timeline

FinAssist AI aims to complete onboarding within 10 business days of receiving a
signed application, contingent on the client supplying all required documents
promptly.
