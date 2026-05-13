"""DB engine and session management. Uses SQLAlchemy Core/ORM with SQLite,
but executes the raw schema.sql so CHECK constraints stay the source of truth."""

from pathlib import Path
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, scoped_session

from .config import Config

_engine = None
_SessionFactory = None
_Session = None  # scoped_session for the Flask app

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _enable_fk(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON")
    cur.close()


def init_engine(url: str | None = None):
    global _engine, _SessionFactory, _Session
    if url is None:
        url = Config.SQLALCHEMY_URL
    _engine = create_engine(url, future=True)
    event.listen(_engine, "connect", _enable_fk)
    _SessionFactory = sessionmaker(bind=_engine, future=True, autoflush=False)
    _Session = scoped_session(_SessionFactory)
    return _engine


def get_engine():
    if _engine is None:
        init_engine()
    return _engine


def get_session():
    if _Session is None:
        init_engine()
    return _Session()


def shutdown_session(*_):
    if _Session is not None:
        _Session.remove()


def init_db():
    """Create schema from schema.sql. Idempotent (uses IF NOT EXISTS)."""
    engine = get_engine()
    sql = SCHEMA_PATH.read_text()
    raw = engine.raw_connection()
    try:
        raw.executescript(sql)
        raw.commit()
    finally:
        raw.close()


def _split_sql(sql: str):
    """Legacy splitter kept for reference; init_db now uses executescript."""
    out = []
    buf = []
    for line in sql.splitlines():
        s = line.strip()
        if not s or s.startswith("--"):
            continue
        buf.append(line)
        if s.endswith(";"):
            out.append("\n".join(buf))
            buf = []
    if buf:
        out.append("\n".join(buf))
    return out
