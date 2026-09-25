"""SQLAlchemy engine/session setup.

Defaults to a local SQLite file so the whole app runs with zero external
services. Point DATABASE_URL at a PostgreSQL+PostGIS instance (see
docker-compose.yml) for production-parity deployments; the ORM models use
plain lat/lon columns plus a JSON-encoded geometry field so both backends
work without code changes (PostGIS geometry columns are an additive
migration, not a rewrite).
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

settings = get_settings()

_is_sqlite = settings.database_url.startswith("sqlite")
_is_sqlite_memory = _is_sqlite and ":memory:" in settings.database_url
_engine_kwargs: dict = {"future": True}
if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
if _is_sqlite_memory:
    # A ":memory:" SQLite database is per-connection by default. FastAPI/
    # Starlette dispatch sync request handlers onto a worker thread pool, so
    # without a single shared connection, each request could see its own
    # empty, table-less database. StaticPool pins everyone to one connection.
    _engine_kwargs["poolclass"] = StaticPool

engine = create_engine(settings.database_url, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from app.storage import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()


_ADDITIVE_COLUMNS = {
    "events": {"facility_context_quality": "VARCHAR"},
    "observations": {"satellite": "VARCHAR", "instrument": "VARCHAR", "scan": "FLOAT", "track": "FLOAT", "source_product": "VARCHAR"},
}


def _add_missing_columns() -> None:
    """create_all() never alters existing tables. These nullable columns were added after first release, so add them
    in place (idempotent) instead of requiring the analyst to delete their database."""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in _ADDITIVE_COLUMNS.items():
            if not insp.has_table(table):
                continue
            have = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols.items():
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
