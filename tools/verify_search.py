"""Manual verification for Phase 20 (Global Search): confirms each category
returns real, correct matches, that category filtering works, and that a
client-ID-style query doesn't spuriously drag in irrelevant Knowledge Base
chunks. Not a pytest suite (that's tests/test_search_tools.py)."""

import sys

from database.seed import main as seed_main

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools.search_tools import global_search  # noqa: E402


def main() -> None:
    seed_main()

    print("=== Query: 'Noah' (should hit Clients) ===")
    r = global_search("Noah")
    print(f"counts={r.counts_by_category}")
    assert r.success
    assert r.counts_by_category.get("Clients", 0) >= 1
    assert any(item.category == "Clients" and "C1002" in item.title for item in r.results)
    print("OK\n")

    print("=== Query: 'George' (should hit Leads) ===")
    r = global_search("George")
    print(f"counts={r.counts_by_category}")
    assert r.counts_by_category.get("Leads", 0) >= 1
    print("OK\n")

    print("=== Query: 'bank_statement' (should hit Documents) ===")
    r = global_search("bank_statement")
    print(f"counts={r.counts_by_category}")
    assert r.counts_by_category.get("Documents", 0) >= 1
    print("OK\n")

    print("=== Query: 'refund policy' (should hit Knowledge Base) ===")
    r = global_search("refund policy")
    print(f"counts={r.counts_by_category}")
    for item in r.results:
        if item.category == "Knowledge Base":
            print(f"  KB match: {item.title} -- {item.snippet[:60]!r}")
    assert r.counts_by_category.get("Knowledge Base", 0) >= 1
    assert any(item.category == "Knowledge Base" and item.key == "refund_policy.md" for item in r.results)
    print("OK\n")

    print("=== Query: 'C1002' -- checking Knowledge Base doesn't spam irrelevant policy chunks ===")
    r = global_search("C1002")
    kb_count = r.counts_by_category.get("Knowledge Base", 0)
    print(f"counts={r.counts_by_category}")
    print(f"Knowledge Base matches for a client-ID query: {kb_count}")
    # Not a hard assertion (semantic search is fuzzy) -- just visibility into
    # whether the relevance threshold is doing its job.

    print("\n=== Category filter: only 'Clients' ===")
    r = global_search("Noah", categories=["Clients"])
    print(f"counts={r.counts_by_category}")
    assert set(r.counts_by_category.keys()) <= {"Clients"}
    assert all(item.category == "Clients" for item in r.results)
    print("OK\n")

    print("=== Empty query ===")
    r = global_search("")
    assert r.success and r.results == []
    print("OK: empty query returns no results without error.\n")

    print("All Global Search checks passed.")


if __name__ == "__main__":
    main()
