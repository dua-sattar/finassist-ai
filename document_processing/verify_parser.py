"""Smoke-test runner for document_processing/parser.py.

Runs extract_text() against every file listed in data/synthetic/documents/manifest.csv
and reports success/failure per file. This is a manual verification script for
Phase 2, not a pytest suite (that's Phase 15).
"""

import csv
from pathlib import Path

from document_processing.parser import extract_text

DOCUMENTS_DIR = Path(__file__).parent.parent / "data" / "synthetic" / "documents"
MANIFEST_PATH = DOCUMENTS_DIR / "manifest.csv"


def main() -> None:
    with MANIFEST_PATH.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    failures = []
    for row in rows:
        path = DOCUMENTS_DIR / row["filename"]
        result = extract_text(path)
        expected_valid = row["document_type"] != "invalid"
        snippet = result.text[:60].replace("\n", " ") if result.text else ""

        status = "OK" if result.success == expected_valid else "UNEXPECTED"
        print(
            f"[{status}] {row['filename']:<35} success={result.success!s:<5} "
            f"pages={result.page_count} error={result.error!r} text={snippet!r}"
        )

        if status == "UNEXPECTED":
            failures.append(row["filename"])

    print()
    if failures:
        print(f"FAILED: {len(failures)} file(s) did not match expected outcome: {failures}")
    else:
        print(f"All {len(rows)} files matched expected outcome.")


if __name__ == "__main__":
    main()
