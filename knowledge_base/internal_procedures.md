# Internal Procedures

> Portfolio demonstration — fictional internal operations procedures for FinAssist AI
> staff (and the FinAssist AI assistant acting on their behalf).

## Document Review Procedure

1. When a document is uploaded, identify the associated client by client ID.
2. Classify the document type (e.g., bank statement, ID, application form).
3. Extract key structured information relevant to that document type.
4. Compare the client's full document set against `required_documents.md`.
5. Record which required documents are present vs. missing.
6. If any are missing, create a follow-up task and draft a request email — do not
   send without advisor approval.
7. If all required documents are present and valid, update `onboarding_status` to
   Complete.

## Lead Follow-Up Procedure

1. Retrieve the lead's stored information (service interest, engagement level,
   information completeness, source).
2. Apply the qualification criteria to assign a priority: High, Medium, or Low.
3. Log the reasoning behind the assigned priority.
4. Update the lead's status in the CRM.
5. Draft a follow-up email and create a follow-up task for the assigned advisor.

## Recommended Next Actions

Whenever the FinAssist AI assistant completes an analysis (document review, lead
qualification, or a general inquiry), it should end with a clearly labeled
"Recommended Next Action" and a reminder that human review is required before any
communication is sent or any status change is treated as final.
