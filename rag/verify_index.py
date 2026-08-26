"""Smoke-test runner for the Phase 4 RAG index: build it, then confirm a
known question retrieves chunks from the right source document.

Manual verification script, not a pytest suite (that's Phase 15). The more
thorough multi-question RAG evaluation lives in rag/verify_retrieval.py
(Phase 5).
"""

from rag.retrieval import build_index, retrieve


def main() -> None:
    count = build_index()
    print(f"Indexed {count} chunks from knowledge_base/")

    query = "What documents are required for client onboarding?"
    results = retrieve(query, k=4)

    print(f"\nQuery: {query!r}")
    if not results:
        print("  No results returned.")
        return

    for r in results:
        snippet = r.text[:80].replace("\n", " ")
        print(f"  [{r.source}] (distance={r.distance:.4f}) {snippet!r}")

    sources = {r.source for r in results}
    if "required_documents.md" in sources:
        print("\nOK: required_documents.md was retrieved for the onboarding-documents question.")
    else:
        print(f"\nUNEXPECTED: expected required_documents.md in results, got sources={sources}")


if __name__ == "__main__":
    main()
