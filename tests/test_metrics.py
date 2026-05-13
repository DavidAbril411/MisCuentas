from datetime import date

from miscuentas.models import Account, Debt, Transaction
from miscuentas.money import to_minor, fx_to_micro
from miscuentas.fx import set_rate
from miscuentas.metrics import (
    net_worth, debt_outstanding, projection, monthly_recurring_flow,
)


def test_account_balance_mixed_currency(session):
    set_rate(session, date(2026, 5, 13), "1400")
    ars = Account(name="ARS", currency="ARS", opening_balance_minor=to_minor("100000"))
    usd = Account(name="USD", currency="USD", opening_balance_minor=0)
    session.add_all([ars, usd])
    session.flush()
    session.add(Transaction(
        occurred_on=date(2026, 5, 1), account_id=usd.id, kind="income",
        amount_minor=to_minor("50"), currency="USD",
        fx_rate_to_ars_micro=fx_to_micro("1400"),
    ))
    session.commit()
    nw = net_worth(session)
    # 100_000 ARS + 50 USD * 1400 = 170_000 ARS
    assert nw.accounts_ars_minor == to_minor("170000")


def test_debt_partial_payment_keeps_own_fx(session):
    set_rate(session, date(2026, 5, 13), "1400")
    acc = Account(name="USD", currency="USD", opening_balance_minor=0)
    session.add(acc)
    session.flush()
    debt = Debt(
        counterparty="Hermano", direction="receivable",
        principal_minor=to_minor("300"), currency="USD",
        fx_rate_to_ars_micro=fx_to_micro("1400"),
        opened_on=date(2026, 5, 13),
    )
    session.add(debt)
    session.flush()
    # Pay 100 USD at rate 1450
    payment = Transaction(
        occurred_on=date(2026, 6, 1), account_id=acc.id, kind="income",
        amount_minor=to_minor("100"), currency="USD",
        fx_rate_to_ars_micro=fx_to_micro("1450"),
        debt_id=debt.id,
    )
    session.add(payment)
    session.commit()
    assert debt_outstanding(session, debt) == to_minor("200")
    assert payment.fx_rate_to_ars_micro == fx_to_micro("1450")
    assert debt.fx_rate_to_ars_micro == fx_to_micro("1400")  # unchanged


def test_net_worth_with_seed(seeded_session):
    nw = net_worth(seeded_session)
    # 694_000 (wallet) + 350_000 (Orion AR) + 500 USD *1400 - 730_000 = 1_014_000
    assert nw.total_minor == to_minor("1014000")
    assert nw.accounts_ars_minor == to_minor("694000")
    assert nw.receivables_ars_minor == to_minor("350000") + to_minor("500") * 1400
    assert nw.payables_ars_minor == to_minor("730000")


def test_monthly_flow_with_seed(seeded_session):
    inc, exp, net = monthly_recurring_flow(seeded_session, today=date(2026, 7, 1))
    # ingresos: 500 USD + 20 USD + 25k ARS = 520*1400 + 25000 = 753000
    assert inc == to_minor("753000")
    # gastos: 80k ARS + 20+10+50 USD = 80000 + 80*1400 = 80000 + 112000 = 192000
    assert exp == to_minor("192000")
    assert net == inc - exp


def test_projection_includes_brother_in_july(seeded_session):
    rows = projection(seeded_session, n_months=4, today=date(2026, 5, 13))
    labels = [r.month_label for r in rows]
    assert labels[0] == "2026-05"  # rest of May
    # Find July
    jul_idx = labels.index("2026-07")
    # Hermano 300 USD due 2026-07-15 → 420_000 ARS receivable in July
    assert rows[jul_idx].receivable_due_ars_minor == to_minor("420000")
