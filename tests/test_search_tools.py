"""Tests for the Phase 20 Global Search tool (tools/search_tools.py),
against the seeded temp DB (conftest)."""

from tools.search_tools import global_search


def test_global_search_finds_client_by_name():
    result = global_search("Noah")
    assert result.success
    assert result.counts_by_category.get("Clients", 0) >= 1
    assert any(item.category == "Clients" and "C1002" in item.title for item in result.results)


def test_global_search_finds_lead_by_company():
    result = global_search("George")
    assert result.success
    assert result.counts_by_category.get("Leads", 0) >= 1


def test_global_search_finds_document_by_type():
    result = global_search("bank_statement")
    assert result.success
    assert result.counts_by_category.get("Documents", 0) >= 1


def test_global_search_finds_knowledge_base_policy():
    result = global_search("refund policy")
    assert result.success
    assert any(item.category == "Knowledge Base" and item.key == "refund_policy.md" for item in result.results)


def test_global_search_client_id_query_excludes_irrelevant_kb_chunks():
    result = global_search("C1002")
    assert result.success
    assert result.counts_by_category.get("Clients", 0) >= 1
    assert result.counts_by_category.get("Knowledge Base", 0) == 0


def test_global_search_category_filter_narrows_results():
    result = global_search("Noah", categories=["Clients"])
    assert result.success
    assert set(result.counts_by_category.keys()) <= {"Clients"}
    assert all(item.category == "Clients" for item in result.results)


def test_global_search_empty_query_returns_no_results_without_error():
    result = global_search("")
    assert result.success
    assert result.results == []


def test_global_search_no_match_returns_empty_not_error():
    result = global_search("zzz-totally-nonexistent-zzz")
    assert result.success
    assert result.results == []
