from datetime import date

from miscuentas.models import Account, Debt, Transaction
from miscuentas.money import to_minor, fx_to_micro
from miscuentas.fx import set_rate
from miscuentas.metrics import (
    net_worth, debt_outstanding, projection, monthly_recurring_flow,
)


def test_account_balance_mixed_currency(session, user_id):
    set_rate(session, user_id, date(2026, 5, 13), "1400")
    ars = Account(user_id=user_id, name="ARS", currency="ARS", opening_balance_minor=to_minor("100000"))
    usd = Account(user_id=user_id, name="USD", currency="USD", opening_balance_minor=0)
    session.add_all([ars, usd]); session.flush()
    session.add(Transaction(
        user_id=user_id, occurred_on=date(2026, 5, 1), account_id=usd.id, kind="income",
        amount_minor=to_minor("50"), currency="USD",
        fx_rate_to_ars_micro=fx_to_micro("1400"),
    ))
    session.commit()
    nw = net_worth(session, user_id)
    assert nw.accounts_ars_minor == to_minor("170000")


def test_debt_partial_payment_keeps_own_fx(session, user_id):
    set_rate(session, user_id, date(2026, 5, 13), "1400")
    acc = Account(user_id=user_id, name="USD", currency="USD", opening_balance_minor=0)
    session.add(acc); session.flush()
    debt = Debt(
        user_id=user_id, counterparty="Hermano", direction="receivable",
        principal_minor=to_minor("300"), currency="USD",
        fx_rate_to_ars_micro=fx_to_micro("1400"),
        opened_on=date(2026, 5, 13),
    )
    session.add(debt); session.flush()
    payment = Transaction(
        user_id=user_id, occurred_on=date(2026, 6, 1), account_id=acc.id, kind="income",
        amount_minor=to_minor("100"), currency="USD",
        fx_rate_to_ars_micro=fx_to_micro("1450"),
        debt_id=debt.id,
    )
    session.add(payment); session.commit()
    assert debt_outstanding(session, debt) == to_minor("200")
    assert payment.fx_rate_to_ars_micro == fx_to_micro("1450")
    assert debt.fx_rate_to_ars_micro == fx_to_micro("1400")


def test_net_worth_with_seed(seeded_session, seeded_user_id):
    nw = net_worth(seeded_session, seeded_user_id)
    assert nw.total_minor == to_minor("1014000")
    assert nw.accounts_ars_minor == to_minor("694000")
    assert nw.receivables_ars_minor == to_minor("350000") + to_minor("500") * 1400
    assert nw.payables_ars_minor == to_minor("730000")


def test_monthly_flow_with_seed(seeded_session, seeded_user_id):
    inc, exp, net = monthly_recurring_flow(seeded_session, seeded_user_id, today=date(2026, 7, 1))
    assert inc == to_minor("753000")
    assert exp == to_minor("192000")
    assert net == inc - exp


def test_projection_includes_brother_in_july(seeded_session, seeded_user_id):
    rows = projection(seeded_session, seeded_user_id, n_months=4, today=date(2026, 5, 13))
    labels = [r.month_label for r in rows]
    assert labels[0] == "2026-05"
    jul_idx = labels.index("2026-07")
    assert rows[jul_idx].receivable_due_ars_minor == to_minor("420000")
