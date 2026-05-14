"""End-to-end HTTP tests: auth, validation, isolation."""

import pytest
from werkzeug.security import generate_password_hash

import miscuentas.db as db_mod
from miscuentas import create_app
from miscuentas.models import User, Account, Transaction, RecurringRule, FxRate
from miscuentas.fx import set_rate
from miscuentas.money import to_minor


def _reset_db_module():
    db_mod._engine = None
    db_mod._SessionFactory = None
    db_mod._Session = None


@pytest.fixture
def app():
    _reset_db_module()
    app = create_app({
        "SQLALCHEMY_URL": "sqlite:///:memory:",
        "DISABLE_AUTO_MATERIALIZE": True,
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "WTF_CSRF_ENABLED": False,
    })
    yield app
    db_mod.shutdown_session()


@pytest.fixture
def client(app):
    return app.test_client()


def _make_user(s, username="alice", password="password123"):
    u = User(username=username, password_hash=generate_password_hash(password))
    s.add(u); s.commit(); return u


def _login(client, username, password):
    return client.post("/login", data={"username": username, "password": password},
                       follow_redirects=False)


# -------- auth ----------

def test_dashboard_requires_login(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/login" in resp.headers["Location"]


def test_register_then_login_flow(client):
    resp = client.post("/register", data={
        "username": "newuser",
        "password": "abc12345",
        "confirm": "abc12345",
    }, follow_redirects=False)
    assert resp.status_code == 302  # redirected after register
    # user can now log in
    db_mod.shutdown_session()
    client.get("/logout")  # ensure logout state if any
    client.post("/logout")
    resp = _login(client, "newuser", "abc12345")
    assert resp.status_code == 302


def test_register_rejects_short_password(client):
    resp = client.post("/register", data={
        "username": "shorty",
        "password": "abc",
        "confirm": "abc",
    })
    assert resp.status_code == 400
    assert "contrase" in resp.data.decode("utf-8").lower()


def test_login_with_wrong_password_fails(client):
    s = db_mod.get_session()
    _make_user(s)
    db_mod.shutdown_session()
    resp = _login(client, "alice", "wrong")
    assert resp.status_code == 401


def test_change_password_flow(client):
    s = db_mod.get_session()
    _make_user(s)
    db_mod.shutdown_session()
    _login(client, "alice", "password123")
    resp = client.post("/change-password", data={
        "current": "password123",
        "new": "newpass456",
        "confirm": "newpass456",
    }, follow_redirects=False)
    assert resp.status_code == 302
    # old password no longer works, new one does
    client.post("/logout")
    assert _login(client, "alice", "password123").status_code == 401
    assert _login(client, "alice", "newpass456").status_code == 302


# -------- isolation ----------

def test_users_cannot_see_each_others_data(client):
    s = db_mod.get_session()
    alice = _make_user(s, "alice", "password123")
    bob = _make_user(s, "bob", "password123")
    # Alice has an account and a tx
    alice_acc = Account(user_id=alice.id, name="Alice ARS", currency="ARS", opening_balance_minor=to_minor("100"))
    s.add(alice_acc); s.flush()
    set_rate(s, alice.id, __import__("datetime").date(2026, 5, 13), "1400")
    alice_tx = Transaction(
        user_id=alice.id,
        occurred_on=__import__("datetime").date(2026, 5, 13),
        account_id=alice_acc.id, kind="expense",
        amount_minor=to_minor("50"), currency="ARS",
        description="Alice secret",
    )
    s.add(alice_tx); s.commit()
    alice_tx_id = alice_tx.id
    alice_acc_id = alice_acc.id
    db_mod.shutdown_session()

    # Bob logs in; should not see Alice's stuff
    _login(client, "bob", "password123")
    set_rate_resp = client.post("/fx/new", data={
        "effective_on": "2026-05-13", "rate": "1400",
    }, follow_redirects=False)
    assert set_rate_resp.status_code == 302
    resp = client.get("/transactions")
    assert b"Alice secret" not in resp.data
    resp = client.get("/accounts")
    assert b"Alice ARS" not in resp.data
    # Bob can't edit Alice's tx via direct URL
    resp = client.get(f"/transactions/{alice_tx_id}/edit", follow_redirects=False)
    assert resp.status_code == 404
    resp = client.get(f"/accounts/{alice_acc_id}/edit", follow_redirects=False)
    assert resp.status_code == 404
    # Bob can't delete Alice's tx
    resp = client.post(f"/transactions/{alice_tx_id}/delete", follow_redirects=False)
    assert resp.status_code == 404


# -------- validation + delete ----------

def test_tx_creation_with_mismatched_currency_is_rejected(client):
    s = db_mod.get_session()
    u = _make_user(s)
    usd = Account(user_id=u.id, name="USD", currency="USD", opening_balance_minor=0)
    s.add(usd); s.commit()
    usd_id = usd.id
    set_rate(s, u.id, __import__("datetime").date(2026, 5, 13), "1400")
    s.commit()
    db_mod.shutdown_session()

    _login(client, "alice", "password123")
    resp = client.post("/transactions/new", data={
        "occurred_on": "2026-05-13",
        "account_id": str(usd_id),
        "kind": "expense",
        "currency": "ARS",  # mismatch
        "amount": "400000",
    }, follow_redirects=False)
    assert resp.status_code == 200
    assert b"moneda" in resp.data.lower()

    s = db_mod.get_session()
    assert s.query(Transaction).count() == 0


def test_delete_recurring_generated_transaction(client):
    import datetime
    s = db_mod.get_session()
    u = _make_user(s)
    ars = Account(user_id=u.id, name="ARS", currency="ARS", opening_balance_minor=0)
    s.add(ars); s.flush()
    rule = RecurringRule(
        user_id=u.id, name="x", kind="expense",
        amount_minor=10000, currency="ARS",
        account_id=ars.id, day_of_month=1,
        start_date=datetime.date(2026, 4, 1),
    )
    s.add(rule); s.flush()
    tx = Transaction(
        user_id=u.id, occurred_on=datetime.date(2026, 4, 1),
        account_id=ars.id, kind="expense",
        amount_minor=10000, currency="ARS",
        recurring_rule_id=rule.id,
    )
    s.add(tx); s.commit()
    tx_id = tx.id
    db_mod.shutdown_session()

    _login(client, "alice", "password123")
    resp = client.post(f"/transactions/{tx_id}/delete", follow_redirects=False)
    assert resp.status_code == 302
    s = db_mod.get_session()
    assert s.get(Transaction, tx_id) is None
