from datetime import date

from miscuentas.models import Meta, User, Account, Debt, RecurringRule, FxRate


def test_seed_creates_default_user(seeded_session):
    u = seeded_session.query(User).filter_by(username="davidabril01").one_or_none()
    assert u is not None
    from werkzeug.security import check_password_hash
    assert check_password_hash(u.password_hash, "Admin123")


def test_seed_loads_expected_rows(seeded_session, seeded_user_id):
    s = seeded_session
    assert s.query(Meta).filter_by(key="seeded_v2").one_or_none() is not None
    assert s.query(Account).filter_by(user_id=seeded_user_id).count() == 3
    assert s.query(Debt).filter_by(user_id=seeded_user_id).count() == 4
    assert s.query(RecurringRule).filter_by(user_id=seeded_user_id).count() == 7
    rate = s.query(FxRate).filter_by(user_id=seeded_user_id).one()
    assert rate.rate_to_ars_micro == 1_400_000_000
    assert rate.effective_on == date(2026, 5, 13)


def test_seed_idempotent(seeded_session, seeded_user_id):
    import seed as seed_mod
    seed_mod.run(session=seeded_session)
    seed_mod.run(session=seeded_session)
    assert seeded_session.query(Account).filter_by(user_id=seeded_user_id).count() == 3
    assert seeded_session.query(Debt).filter_by(user_id=seeded_user_id).count() == 4
    assert seeded_session.query(RecurringRule).filter_by(user_id=seeded_user_id).count() == 7
