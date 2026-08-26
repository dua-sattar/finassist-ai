"""Smoke-test runner for document_processing/extractor.py.

Runs process_document() against every file listed in
data/synthetic/documents/manifest.csv and reports classification, extracted
fields, missing fields, and the summary (LLM or templated fallback) per file.
Manual verification script for Phase 3, not a pytest suite (that's Phase 15).
"""

import csv
from pathlib import Path

from document_processing.extractor import process_document

DOCUMENTS_DIR = Path(__file__).parent.parent / "data" / "synthetic" / "documents"
MANIFEST_PATH = DOCUMENTS_DIR / "manifest.csv"


def main() -> None:
    with MANIFEST_PATH.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    mismatches = []
    for row in rows:
        path = DOCUMENTS_DIR / row["filename"]
        result = process_document(path, filename=row["filename"])

        expected_type = row["document_type"]
        classification_ok = (
            result.document_type == expected_type
            if expected_type != "invalid"
            else not result.success
        )
        if not classification_ok:
            mismatches.append(row["filename"])

        print(f"--- {row['filename']} ---")
        print(f"  success={result.success}  document_type={result.document_type} (expected {expected_type})")
        if result.error:
            print(f"  error={result.error!r}")
        else:
            print(f"  fields={result.extracted_fields}")
            print(f"  missing_fields={result.missing_fields}")
            print(f"  summary={result.summary!r}")
        print()

    print("=" * 60)
    if mismatches:
        print(f"MISMATCH: {len(mismatches)} file(s) classified unexpectedly: {mismatches}")
    else:
        print(f"All {len(rows)} files classified as expected.")


if __name__ == "__main__":
    main()
