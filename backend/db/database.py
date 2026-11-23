"""PostgreSQL connection, session handling and schema creation."""

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

load_dotenv()

DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://postgres:postgres@localhost:5432/knowledge_assistant"
)

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_database_url() -> str:
    """Return DATABASE_URL, normalized to the psycopg 3 driver."""
    url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL).strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def get_engine() -> Engine:
    global _engine, _session_factory
    if _engine is None:
        _engine = create_engine(
            get_database_url(),
            pool_pre_ping=True,
            # Fail fast instead of hanging when PostgreSQL is down.
            connect_args={"connect_timeout": int(os.getenv("DATABASE_CONNECT_TIMEOUT", "5"))},
        )
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def _sessions() -> sessionmaker[Session]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Session that commits on success and rolls back on error."""
    session = _sessions()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a transactional session."""
    with session_scope() as session:
        yield session


def init_db() -> None:
    """Create any missing tables. Fails fast if PostgreSQL is unreachable."""
    from backend.db import models  # noqa: F401  (registers the tables)

    engine = get_engine()
    models.Base.metadata.create_all(engine)
    logger.info("PostgreSQL schema ready at %s", engine.url.render_as_string(hide_password=True))


def check_db() -> bool:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - health check reports any failure as down
        logger.exception("PostgreSQL health check failed")
        return False


def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
