"""Tests for rag/retrieval.py. Uses the real local embedding model (no API
key needed) -- slower than the rest of the suite on first run while the
sentence-transformers model loads, but fully offline."""

import pytest

from rag.retrieval import build_index, retrieve


@pytest.fixture(scope="module", autouse=True)
def _built_index():
    count = build_index()
    assert count > 0


def test_retrieve_onboarding_question_returns_required_documents_source():
    results = retrieve("What documents are required for client onboarding?", k=4)

    assert results
    assert any(r.source == "required_documents.md" for r in results)


def test_retrieve_refund_question_returns_refund_policy_source():
    results = retrieve("What is FinAssist AI's refund policy?", k=4)

    assert any(r.source == "refund_policy.md" for r in results)


def test_retrieve_returns_requested_k():
    results = retrieve("What services does FinAssist AI offer?", k=2)

    assert len(results) == 2
