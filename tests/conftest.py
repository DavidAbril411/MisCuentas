import pytest
from werkzeug.security import generate_password_hash

import miscuentas.db as db_mod
from miscuentas.models import User


def _reset_db_module():
    db_mod._engine = None
    db_mod._SessionFactory = None
    db_mod._Session = None


@pytest.fixture
def session():
    """Fresh in-memory DB. Also creates a default user 'tester' for convenience.
    Use `user_id` fixture to access its id."""
    _reset_db_module()
    db_mod.init_engine("sqlite:///:memory:")
    db_mod.init_db()
    s = db_mod.get_session()
    u = User(username="tester", password_hash=generate_password_hash("password123"))
    s.add(u)
    s.commit()
    try:
        yield s
    finally:
        s.close()
        db_mod.shutdown_session()


@pytest.fixture
def user_id(session):
    return session.query(User).filter_by(username="tester").one().id


@pytest.fixture
def seeded_session():
    """Fresh in-memory DB seeded with seed.py (creates davidabril01 user)."""
    _reset_db_module()
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


@pytest.fixture
def seeded_user_id(seeded_session):
    return seeded_session.query(User).filter_by(username="davidabril01").one().id
