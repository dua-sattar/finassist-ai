"""global_search tool -- searches across clients, leads, documents, tasks,
follow-up emails, the knowledge base, and AI-generated document summaries
(spec section 22), with a uniform result shape so callers don't need to
know each source's underlying storage."""

import logging

from pydantic import BaseModel

from database import crud
from rag.retrieval import retrieve
from tools.common import log_action

logger = logging.getLogger(__name__)

ALL_CATEGORIES = ["Clients", "Leads", "Documents", "Tasks", "Follow-ups", "Knowledge Base", "AI Summaries"]

# Chroma L2 distance cutoff for the Knowledge Base category: semantic
# nearest-neighbor search always returns *something*, even for a query with
# no real match (e.g. a client ID) -- unlike the other categories' exact
# substring matches, so a loose relevance cutoff keeps unrelated policy
# fragments out of a keyword-style search's results.
KB_RELEVANCE_THRESHOLD = 0.8


class SearchResultItem(BaseModel):
    category: str
    key: str
    title: str
    snippet: str


class GlobalSearchResult(BaseModel):
    success: bool
    query: str
    results: list[SearchResultItem] = []
    counts_by_category: dict[str, int] = {}
    error: str | None = None


def global_search(query: str, categories: list[str] | None = None, limit_per_category: int = 5) -> GlobalSearchResult:
    """Search across clients, leads, documents, tasks, follow-up emails, the
    knowledge base, and AI-generated document summaries in one call. Pass
    `categories` (a subset of Clients/Leads/Documents/Tasks/Follow-ups/
    Knowledge Base/AI Summaries) to narrow the search; omit for all of them."""
    query = query.strip()
    if not query:
        return GlobalSearchResult(success=True, query=query, results=[])

    active = set(categories) if categories else set(ALL_CATEGORIES)
    results: list[SearchResultItem] = []
    counts: dict[str, int] = {}

    try:
        if "Clients" in active:
            clients = crud.search_clients(query, limit=limit_per_category)
            counts["Clients"] = len(clients)
            for c in clients:
                results.append(
                    SearchResultItem(
                        category="Clients",
                        key=c.client_id,
                        title=f"{c.client_id} -- {c.name}",
                        snippet=f"{c.service} · {c.account_status} · {c.onboarding_status}",
                    )
                )

        if "Leads" in active:
            leads = crud.search_leads(query, limit=limit_per_category)
            counts["Leads"] = len(leads)
            for lead in leads:
                results.append(
                    SearchResultItem(
                        category="Leads",
                        key=lead.lead_id,
                        title=f"{lead.lead_id} -- {lead.name}",
                        snippet=f"{lead.company} · {lead.service_interest} · {lead.status}",
                    )
                )

        if "Documents" in active:
            documents = crud.search_documents(query, limit=limit_per_category)
            counts["Documents"] = len(documents)
            for d in documents:
                client_part = f" · client {d.client_id}" if d.client_id else ""
                results.append(
                    SearchResultItem(
                        category="Documents",
                        key=str(d.id),
                        title=d.filename,
                        snippet=f"{d.document_type} · {d.status}{client_part}",
                    )
                )

        if "Tasks" in active:
            tasks = crud.search_tasks(query, limit=limit_per_category)
            counts["Tasks"] = len(tasks)
            for t in tasks:
                results.append(
                    SearchResultItem(
                        category="Tasks",
                        key=str(t.id),
                        title=t.description[:80],
                        snippet=f"{t.task_type} · {t.status} · priority={t.priority or 'n/a'}",
                    )
                )

        if "Follow-ups" in active:
            followups = crud.search_followups(query, limit=limit_per_category)
            counts["Follow-ups"] = len(followups)
            for f in followups:
                to = f.client_id or f.lead_id or f.to_email or "unknown"
                results.append(
                    SearchResultItem(
                        category="Follow-ups", key=str(f.id), title=f.subject, snippet=f"{f.status} · to {to}"
                    )
                )

        if "Knowledge Base" in active:
            chunks = [c for c in retrieve(query, k=limit_per_category) if c.distance <= KB_RELEVANCE_THRESHOLD]
            counts["Knowledge Base"] = len(chunks)
            for c in chunks:
                results.append(
                    SearchResultItem(
                        category="Knowledge Base",
                        key=c.source,
                        title=c.source,
                        snippet=c.text[:160].replace("\n", " "),
                    )
                )

        if "AI Summaries" in active:
            extractions = crud.search_document_extractions(query, limit=limit_per_category)
            counts["AI Summaries"] = len(extractions)
            for extraction, document in extractions:
                results.append(
                    SearchResultItem(
                        category="AI Summaries",
                        key=str(extraction.id),
                        title=document.filename,
                        snippet=extraction.summary[:160],
                    )
                )

        log_action("global_search", f"query={query!r} categories={sorted(active)}", f"{len(results)} results")
        return GlobalSearchResult(success=True, query=query, results=results, counts_by_category=counts)
    except Exception as exc:
        logger.warning("global_search failed for %r: %s", query, exc)
        log_action("global_search", f"query={query!r}", str(exc), status="error")
        return GlobalSearchResult(success=False, query=query, error=str(exc))
