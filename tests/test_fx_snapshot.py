from datetime import date
import pytest
from sqlalchemy.exc import IntegrityError

from miscuentas.models import Account, Transaction, FxRate
from miscuentas.money import to_minor, fx_to_micro
from miscuentas.fx import set_rate


def _account(session, user_id, currency="USD"):
    a = Account(user_id=user_id, name=f"Test {currency}", currency=currency, opening_balance_minor=0)
    session.add(a)
    session.flush()
    return a


def test_usd_tx_requires_fx(session, user_id):
    a = _account(session, user_id, "USD")
    bad = Transaction(
        user_id=user_id, occurred_on=date(2026, 5, 1), account_id=a.id, kind="income",
        amount_minor=10000, currency="USD", fx_rate_to_ars_micro=None,
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_ars_tx_rejects_fx(session, user_id):
    a = _account(session, user_id, "ARS")
    bad = Transaction(
        user_id=user_id, occurred_on=date(2026, 5, 1), account_id=a.id, kind="income",
        amount_minor=10000, currency="ARS", fx_rate_to_ars_micro=fx_to_micro("1400"),
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_snapshot_immutable_when_fx_changes(session, user_id):
    a = _account(session, user_id, "USD")
    set_rate(session, user_id, date(2026, 5, 13), "1400")
    session.flush()
    tx = Transaction(
        user_id=user_id, occurred_on=date(2026, 5, 13), account_id=a.id, kind="expense",
        amount_minor=to_minor("20"), currency="USD",
        fx_rate_to_ars_micro=fx_to_micro("1400"),
        description="Claude",
    )
    session.add(tx)
    session.commit()
    tx_id = tx.id
    set_rate(session, user_id, date(2026, 5, 14), "1500")
    session.commit()
    session.expire_all()
    again = session.get(Transaction, tx_id)
    assert again.fx_rate_to_ars_micro == 1_400_000_000
