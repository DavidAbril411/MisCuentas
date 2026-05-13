"""Currency consistency between account and transactions / recurring rules.
Enforced at the DB level via triggers (defensive backstop) and at the
application level via route validation."""

from datetime import date
import pytest
from sqlalchemy.exc import OperationalError, DatabaseError, IntegrityError

from miscuentas.models import Account, Transaction, RecurringRule
from miscuentas.money import to_minor, fx_to_micro
from miscuentas.fx import set_rate


def _ars_account(session, name="ARS"):
    a = Account(name=name, currency="ARS", opening_balance_minor=0)
    session.add(a)
    session.flush()
    return a


def _usd_account(session, name="USD"):
    a = Account(name=name, currency="USD", opening_balance_minor=0)
    session.add(a)
    session.flush()
    return a


def test_ars_tx_on_usd_account_rejected_by_trigger(session):
    usd = _usd_account(session)
    bad = Transaction(
        occurred_on=date(2026, 5, 13),
        account_id=usd.id,
        kind="expense",
        amount_minor=to_minor("400000"),
        currency="ARS",
        fx_rate_to_ars_micro=None,
    )
    session.add(bad)
    with pytest.raises((OperationalError, DatabaseError, IntegrityError)) as ei:
        session.flush()
    assert "moneda" in str(ei.value).lower()
    session.rollback()


def test_usd_tx_on_ars_account_rejected_by_trigger(session):
    ars = _ars_account(session)
    set_rate(session, date(2026, 5, 13), "1400")
    session.flush()
    bad = Transaction(
        occurred_on=date(2026, 5, 13),
        account_id=ars.id,
        kind="expense",
        amount_minor=to_minor("20"),
        currency="USD",
        fx_rate_to_ars_micro=fx_to_micro("1400"),
    )
    session.add(bad)
    with pytest.raises((OperationalError, DatabaseError, IntegrityError)):
        session.flush()
    session.rollback()


def test_update_tx_to_wrong_account_rejected(session):
    ars = _ars_account(session, "ARS-1")
    usd = _usd_account(session, "USD-1")
    tx = Transaction(
        occurred_on=date(2026, 5, 13),
        account_id=ars.id,
        kind="expense",
        amount_minor=to_minor("100"),
        currency="ARS",
    )
    session.add(tx)
    session.commit()
    tx.account_id = usd.id  # ARS tx pointing to USD account
    with pytest.raises((OperationalError, DatabaseError, IntegrityError)):
        session.flush()
    session.rollback()


def test_mismatched_rule_rejected_by_trigger(session):
    usd = _usd_account(session)
    rule = RecurringRule(
        name="Mismatched", kind="expense",
        amount_minor=to_minor("400000"), currency="ARS",
        account_id=usd.id, day_of_month=1,
        start_date=date(2026, 5, 1),
    )
    session.add(rule)
    with pytest.raises((OperationalError, DatabaseError, IntegrityError)):
        session.flush()
    session.rollback()
