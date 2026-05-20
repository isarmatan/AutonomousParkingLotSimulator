"""Database configuration (SQLite + SQLAlchemy).

Why this module exists:
- Centralizes DB connection configuration.
- Provides a shared SQLAlchemy `engine` + `SessionLocal` factory.
- Exposes `init_db()` to create tables on application startup.

We use SQLite for a simple MVP: single file DB, zero external infrastructure.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./parking_lots.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db() -> None:
    """Create DB tables (if they don't exist yet) then apply any column migrations."""
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    migrate_db()


def migrate_db() -> None:
    """Add new columns to existing tables (SQLite-safe, idempotent)."""
    _new_cols = [
        ("simulation_results", "algorithm", "TEXT"),
        ("simulation_results", "config_json", "TEXT"),
        ("simulation_results", "avg_trip_duration_steps", "REAL"),
        ("simulation_results", "max_trip_duration_steps", "INTEGER"),
        ("simulation_results", "min_trip_duration_steps", "INTEGER"),
        ("simulation_results", "total_completed_trips", "INTEGER"),
        ("simulation_results", "avg_planner_ms", "REAL"),
        ("simulation_results", "max_planner_ms", "REAL"),
        ("simulation_results", "planner_call_count", "INTEGER"),
        ("simulation_results", "cpu_usage_avg_percent", "REAL"),
        ("simulation_results", "cpu_usage_peak_percent", "REAL"),
        ("simulation_results", "memory_usage_avg_mb", "REAL"),
        ("simulation_results", "memory_usage_peak_mb", "REAL"),
        ("simulation_results", "machine_specs_json", "TEXT"),
    ]
    with engine.connect() as conn:
        for table, col, dtype in _new_cols:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {dtype}"))
                conn.commit()
            except Exception:
                pass  # column already exists
