"""SQLAlchemy engine/session setup for the FinAssist AI mock CRM."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base

load_dotenv()

BASE_DIR = Path(__file__).parent.parent


def _resolve_db_path() -> Path:
    raw = os.getenv("SQLITE_DB_PATH", "./database/finassist.db")
    path = Path(raw)
    return path if path.is_absolute() else BASE_DIR / path


DB_PATH = _resolve_db_path()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}")

# expire_on_commit=False: returned ORM objects stay usable after their
# short-lived session (see database/crud.py's session_scope) closes, without
# needing to re-query the database on every attribute access.
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
