from sqlalchemy import text

from app.db import make_session_factory


def _pragma(sf, name):
    with sf() as s:
        return s.execute(text(f"PRAGMA {name}")).scalar()


def test_file_sqlite_uses_wal_and_foreign_keys(tmp_path):
    sf = make_session_factory(f"sqlite:///{tmp_path / 'app.db'}")
    assert _pragma(sf, "journal_mode") == "wal"
    assert _pragma(sf, "foreign_keys") == 1


def test_in_memory_sqlite_skips_wal():
    sf = make_session_factory("sqlite://")
    assert _pragma(sf, "journal_mode") == "memory"
    assert _pragma(sf, "foreign_keys") == 1
