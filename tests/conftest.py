"""Shared pytest fixtures.

Points the database at an isolated temp SQLite file (via SQLITE_DB_PATH,
set before any `database.*` module is imported) rather than the real
database/finassist.db, so the test suite never touches or depends on local
dev state. Seeds it once per session with the same synthetic fixtures the
rest of the project uses (data/synthetic/*.csv, data/synthetic/documents/).
"""

import os
import tempfile
from pathlib import Path

_TEST_DB_DIR = tempfile.mkdtemp(prefix="finassist_test_")
os.environ["SQLITE_DB_PATH"] = str(Path(_TEST_DB_DIR) / "test.db")

import pytest  # noqa: E402

PROJECT_ROOT = Path(__file__).parent.parent
DOCUMENTS_DIR = PROJECT_ROOT / "data" / "synthetic" / "documents"


@pytest.fixture(scope="session", autouse=True)
def _seeded_test_db():
    from database.seed import main as seed_main

    seed_main()
    yield
