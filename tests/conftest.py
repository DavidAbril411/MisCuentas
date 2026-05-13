import os
import pytest
from datetime import date

import miscuentas.db as db_mod


@pytest.fixture
def session():
    """Fresh in-memory SQLite session per test."""
    db_mod._engine = None
    db_mod._SessionFactory = None
    db_mod._Session = None
    db_mod.init_engine("sqlite:///:memory:")
    db_mod.init_db()
    s = db_mod.get_session()
    try:
        yield s
    finally:
        s.close()
        db_mod.shutdown_session()


@pytest.fixture
def seeded_session(monkeypatch, tmp_path):
    """Run the seed against a fresh in-memory engine and return its session."""
    import miscuentas.db as db_mod
    db_mod._engine = None
    db_mod._SessionFactory = None
    db_mod._Session = None
    db_mod.init_engine("sqlite:///:memory:")
    db_mod.init_db()
    s = db_mod.get_session()
    import seed as seed_mod
    seed_mod.run(session=s)
    try:
        yield s
    finally:
        s.close()
        db_mod.shutdown_session()
