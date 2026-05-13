from datetime import date

from miscuentas.models import Meta, Account, Debt, RecurringRule, FxRate


def test_seed_loads_expected_rows(seeded_session):
    s = seeded_session
    assert s.query(Meta).filter_by(key="seeded_v1").one_or_none() is not None
    assert s.query(Account).count() == 3
    assert s.query(Debt).count() == 4
    assert s.query(RecurringRule).count() == 7
    assert s.query(FxRate).count() == 1
    rate = s.query(FxRate).one()
    assert rate.rate_to_ars_micro == 1_400_000_000
    assert rate.effective_on == date(2026, 5, 13)


def test_seed_idempotent(seeded_session):
    import seed as seed_mod
    seed_mod.run(session=seeded_session)
    seed_mod.run(session=seeded_session)
    # Counts unchanged
    assert seeded_session.query(Account).count() == 3
    assert seeded_session.query(Debt).count() == 4
    assert seeded_session.query(RecurringRule).count() == 7
