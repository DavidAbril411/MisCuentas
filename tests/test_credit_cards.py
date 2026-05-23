import pytest
import miscuentas.db as db_mod
from miscuentas import create_app
from miscuentas.models import Account, Transaction, RecurringRule, Category, FxRate
from datetime import date

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

def test_credit_card_account_creation(client):
    s = db_mod.get_session()
    s.add(FxRate(effective_on=date(2026, 5, 22), rate_to_ars_micro=1400000000))
    s.commit()
    # Create an account via POST
    resp = client.post("/accounts/new", data={
        "name": "Tarjeta Naranja Test",
        "currency": "ARS",
        "opening_balance": "0",
        "is_credit_card": "on"
    }, follow_redirects=True)
    assert resp.status_code == 200
    
    # Verify in DB
    acc = s.query(Account).filter_by(name="Tarjeta Naranja Test").first()
    assert acc is not None
    assert acc.is_credit_card == 1
    assert acc.currency == "ARS"

def test_transfer_creation(client):
    s = db_mod.get_session()
    s.add(FxRate(effective_on=date(2026, 5, 22), rate_to_ars_micro=1400000000))
    src = Account(name="Bancor Test", currency="ARS", opening_balance_minor=100000)
    dest = Account(name="Tarjeta Test", currency="ARS", opening_balance_minor=0, is_credit_card=1)
    s.add(src)
    s.add(dest)
    s.commit()
    src_id, dest_id = src.id, dest.id
    db_mod.shutdown_session()
    
    resp = client.post("/transactions/transfer", data={
        "occurred_on": "2026-05-22",
        "source_account_id": str(src_id),
        "dest_account_id": str(dest_id),
        "amount": "500.00",
        "description": "Pago de tarjeta"
    }, follow_redirects=True)
    assert resp.status_code == 200
    
    s = db_mod.get_session()
    txs = s.query(Transaction).all()
    assert len(txs) == 2
    
    tx_out = [t for t in txs if t.kind == "transfer_out"][0]
    tx_in = [t for t in txs if t.kind == "transfer_in"][0]
    
    assert tx_out.account_id == src_id
    assert tx_out.amount_minor == 50000
    assert tx_out.currency == "ARS"
    assert tx_out.description == "Pago de tarjeta"
    
    assert tx_in.account_id == dest_id
    assert tx_in.amount_minor == 50000
    assert tx_in.currency == "ARS"
    assert tx_in.description == "Pago de tarjeta"

def test_new_installment_creation(client):
    s = db_mod.get_session()
    s.add(FxRate(effective_on=date(2026, 5, 22), rate_to_ars_micro=1400000000))
    acc = Account(name="Tarjeta Cuotas Test", currency="ARS", opening_balance_minor=0, is_credit_card=1)
    cat = Category(name="Compras Test", kind="expense")
    s.add(acc)
    s.add(cat)
    s.commit()
    acc_id = acc.id
    cat_id = cat.id
    db_mod.shutdown_session()
    
    resp = client.post("/transactions/new_installment", data={
        "name": "Botas Test",
        "occurred_on": "2026-06-01",
        "amount": "17700.00",
        "installments_count": "6",
        "account_id": str(acc_id),
        "category_id": str(cat_id)
    }, follow_redirects=True)
    assert resp.status_code == 200
    
    s = db_mod.get_session()
    rule = s.query(RecurringRule).filter_by(name="Botas Test (Cuota)").first()
    assert rule is not None
    assert rule.amount_minor == 1770000
    assert rule.account_id == acc_id
    assert rule.category_id == cat_id
    assert rule.start_date.isoformat() == "2026-06-01"
    assert rule.end_date.isoformat() == "2026-11-01" # 6 months: Jun, Jul, Aug, Sep, Oct, Nov

def test_mensual_grid_renders(client):
    s = db_mod.get_session()
    s.add(FxRate(effective_on=date(2026, 5, 22), rate_to_ars_micro=1400000000))
    acc = Account(name="Bancor Mensual", currency="ARS", is_credit_card=0)
    s.add(acc)
    s.commit()
    db_mod.shutdown_session()
    
    resp = client.get("/mensual")
    assert resp.status_code == 200
    assert b"Planificaci" in resp.data
