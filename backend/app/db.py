from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def make_session_factory(url: str) -> sessionmaker:
    kwargs = {}
    if url == "sqlite://":  # in-memory: share one connection across threads
        kwargs = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    elif url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
    engine = create_engine(url, **kwargs)
    from app import models  # noqa: F401  (register tables)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
