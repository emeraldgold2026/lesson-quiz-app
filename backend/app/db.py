from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

SQLITE_BUSY_TIMEOUT_S = 30


class Base(DeclarativeBase):
    pass


def _enable_wal(dbapi_conn, _record) -> None:
    # WAL lets readers proceed while a writer is active; writers still serialise.
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.close()


def _enable_foreign_keys(dbapi_conn, _record) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


def make_session_factory(url: str) -> sessionmaker:
    kwargs = {}
    if url == "sqlite://":  # in-memory: share one connection across threads
        kwargs = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    elif url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False, "timeout": SQLITE_BUSY_TIMEOUT_S}}
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_foreign_keys)
    if url.startswith("sqlite:///"):
        event.listen(engine, "connect", _enable_wal)
    from app import models  # noqa: F401  (register tables)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
