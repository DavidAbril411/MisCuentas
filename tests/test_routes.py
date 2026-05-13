"""End-to-end route tests: validation and deletion via HTTP."""

import pytest
import miscuentas.db as db_mod
from miscuentas import create_app
from miscuentas.models import Account, Transaction, RecurringRule


@pytest.fixture
def app():
    db_mod._engine = None
    db_mod._SessionFactory = None
    db_mod._Session = None
    app = create_app({
        "SQLALCHEMY_URL": "sqlite:///:memory:",
        "DISABLE_AUTO_MATERIALIZE": True,
        "TESTING": True,
    })
    yield app
    db_mod.shutdown_session()


@pytest.fixture
def client(app):
    return app.test_client()


def _ars(session, name="ARS"):
    a = Account(name=name, currency="ARS", opening_balance_minor=0)
    session.add(a); session.flush(); return a


def _usd(session, name="USD"):
    a = Account(name=name, currency="USD", opening_balance_minor=0)
    session.add(a); session.flush(); return a


def test_tx_creation_with_mismatched_currency_is_rejected(client):
    s = db_mod.get_session()
    usd = _usd(s)
    s.commit()
    usd_id = usd.id
    db_mod.shutdown_session()

    resp = client.post("/transactions/new", data={
        "occurred_on": "2026-05-13",
        "account_id": str(usd_id),
        "kind": "expense",
        "currency": "ARS",       # mismatch: USD account
        "amount": "400000",
    }, follow_redirects=False)
    # No redirect → re-rendered the form with error
    assert resp.status_code == 200
    assert b"moneda" in resp.data.lower()

    s = db_mod.get_session()
    assert s.query(Transaction).count() == 0


def test_delete_recurring_generated_transaction(client):
    s = db_mod.get_session()
    ars = _ars(s)
    rule = RecurringRule(
        name="x", kind="expense",
        amount_minor=10000, currency="ARS",
        account_id=ars.id, day_of_month=1,
        start_date=__import__("datetime").date(2026, 4, 1),
    )
    s.add(rule); s.flush()
    tx = Transaction(
        occurred_on=__import__("datetime").date(2026, 4, 1),
        account_id=ars.id, kind="expense",
        amount_minor=10000, currency="ARS",
        recurring_rule_id=rule.id,
    )
    s.add(tx); s.commit()
    tx_id = tx.id
    rule_id = rule.id
    db_mod.shutdown_session()

    resp = client.post(f"/transactions/{tx_id}/delete", follow_redirects=False)
    assert resp.status_code == 302

    s = db_mod.get_session()
    assert s.get(Transaction, tx_id) is None


def test_delete_recurring_rule_keeps_generated_txs_but_unlinks_them(client):
    s = db_mod.get_session()
    ars = _ars(s)
    rule = RecurringRule(
        name="x", kind="expense",
        amount_minor=10000, currency="ARS",
        account_id=ars.id, day_of_month=1,
        start_date=__import__("datetime").date(2026, 4, 1),
    )
    s.add(rule); s.flush()
    tx = Transaction(
        occurred_on=__import__("datetime").date(2026, 4, 1),
        account_id=ars.id, kind="expense",
        amount_minor=10000, currency="ARS",
        recurring_rule_id=rule.id,
    )
    s.add(tx); s.commit()
    rule_id = rule.id
    tx_id = tx.id
    db_mod.shutdown_session()

    resp = client.post(f"/recurring/{rule_id}/delete", follow_redirects=False)
    assert resp.status_code == 302

    s = db_mod.get_session()
    assert s.get(RecurringRule, rule_id) is None
    surviving = s.get(Transaction, tx_id)
    assert surviving is not None
    assert surviving.recurring_rule_id is None
