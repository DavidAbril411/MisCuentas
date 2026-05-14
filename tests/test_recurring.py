from datetime import date

from miscuentas.models import Account, RecurringRule, Transaction
from miscuentas.money import to_minor, fx_to_micro
from miscuentas.fx import set_rate
from miscuentas.recurring import materialize_recurring


def test_materialize_idempotent(session, user_id):
    a = Account(user_id=user_id, name="Pesos", currency="ARS", opening_balance_minor=0)
    session.add(a); session.flush()
    rule = RecurringRule(
        user_id=user_id, name="Mensual", kind="expense",
        amount_minor=to_minor("100"), currency="ARS",
        account_id=a.id, day_of_month=10,
        start_date=date(2026, 1, 1),
    )
    session.add(rule); session.flush()
    n1 = materialize_recurring(session, user_id, date(2026, 5, 13))
    session.commit()
    n2 = materialize_recurring(session, user_id, date(2026, 5, 13))
    session.commit()
    assert n1 == 5
    assert n2 == 0
    rows = session.query(Transaction).filter_by(recurring_rule_id=rule.id).all()
    assert len(rows) == 5


def test_materialize_usd_uses_rate_on_occurrence(session, user_id):
    a = Account(user_id=user_id, name="USD", currency="USD", opening_balance_minor=0)
    session.add(a); session.flush()
    set_rate(session, user_id, date(2026, 1, 1), "1300")
    set_rate(session, user_id, date(2026, 5, 1), "1400")
    session.commit()
    rule = RecurringRule(
        user_id=user_id, name="USD sub", kind="expense",
        amount_minor=to_minor("20"), currency="USD",
        account_id=a.id, day_of_month=1,
        start_date=date(2026, 1, 1),
    )
    session.add(rule); session.flush()
    materialize_recurring(session, user_id, date(2026, 5, 13))
    session.commit()
    txs = (session.query(Transaction)
           .filter_by(recurring_rule_id=rule.id)
           .order_by(Transaction.occurred_on)
           .all())
    assert len(txs) == 5
    assert txs[0].fx_rate_to_ars_micro == fx_to_micro("1300")
    assert txs[4].fx_rate_to_ars_micro == fx_to_micro("1400")
