"""Database configuration (SQLite + SQLAlchemy).

Why this module exists:
- Centralizes DB connection configuration.
- Provides a shared SQLAlchemy `engine` + `SessionLocal` factory.
- Exposes `init_db()` to create tables on application startup.

We use SQLite for a simple MVP: single file DB, zero external infrastructure.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./parking_lots.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db() -> None:
    """Create DB tables (if they don't exist yet)."""
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
