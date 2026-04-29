"""FastAPI DB dependencies.

Why this module exists:
- FastAPI endpoints can `Depends(get_db)` to get a SQLAlchemy Session.
- Ensures sessions are always closed, even if a request fails.
"""

from typing import Generator

from sqlalchemy.orm import Session

from .database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Yield a DB session for a single request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
