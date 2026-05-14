"""Currency & tenancy consistency enforced by triggers."""

from datetime import date
import pytest
from sqlalchemy.exc import OperationalError, DatabaseError, IntegrityError

from miscuentas.models import Account, Transaction, RecurringRule, User
from miscuentas.money import to_minor, fx_to_micro
from miscuentas.fx import set_rate


def _ars(session, user_id, name="ARS"):
    a = Account(user_id=user_id, name=name, currency="ARS", opening_balance_minor=0)
    session.add(a); session.flush(); return a


def _usd(session, user_id, name="USD"):
    a = Account(user_id=user_id, name=name, currency="USD", opening_balance_minor=0)
    session.add(a); session.flush(); return a


def test_ars_tx_on_usd_account_rejected(session, user_id):
    usd = _usd(session, user_id)
    bad = Transaction(
        user_id=user_id, occurred_on=date(2026, 5, 13),
        account_id=usd.id, kind="expense",
        amount_minor=to_minor("400000"), currency="ARS",
    )
    session.add(bad)
    with pytest.raises((OperationalError, DatabaseError, IntegrityError)) as ei:
        session.flush()
    assert "moneda" in str(ei.value).lower()
    session.rollback()


def test_usd_tx_on_ars_account_rejected(session, user_id):
    ars = _ars(session, user_id)
    set_rate(session, user_id, date(2026, 5, 13), "1400")
    session.flush()
    bad = Transaction(
        user_id=user_id, occurred_on=date(2026, 5, 13),
        account_id=ars.id, kind="expense",
        amount_minor=to_minor("20"), currency="USD",
        fx_rate_to_ars_micro=fx_to_micro("1400"),
    )
    session.add(bad)
    with pytest.raises((OperationalError, DatabaseError, IntegrityError)):
        session.flush()
    session.rollback()


def test_mismatched_rule_rejected(session, user_id):
    usd = _usd(session, user_id)
    rule = RecurringRule(
        user_id=user_id, name="Mismatched", kind="expense",
        amount_minor=to_minor("400000"), currency="ARS",
        account_id=usd.id, day_of_month=1,
        start_date=date(2026, 5, 1),
    )
    session.add(rule)
    with pytest.raises((OperationalError, DatabaseError, IntegrityError)):
        session.flush()
    session.rollback()


def test_tx_account_must_belong_to_same_user(session, user_id):
    """If a malicious app code tries to assign a tx to another user's account,
    the trigger blocks it."""
    from werkzeug.security import generate_password_hash
    bob = User(username="bob", password_hash=generate_password_hash("password123"))
    session.add(bob); session.flush()
    bob_acc = Account(user_id=bob.id, name="Bob's ARS", currency="ARS", opening_balance_minor=0)
    session.add(bob_acc); session.flush()
    bad = Transaction(
        user_id=user_id,  # 'tester' user
        occurred_on=date(2026, 5, 13),
        account_id=bob_acc.id,  # ... using Bob's account
        kind="expense", amount_minor=10000, currency="ARS",
    )
    session.add(bad)
    with pytest.raises((OperationalError, DatabaseError, IntegrityError)) as ei:
        session.flush()
    assert "usuario" in str(ei.value).lower()
    session.rollback()
