"""Net worth, monthly flow, projection — scoped by user_id."""

from __future__ import annotations
from datetime import date
from dataclasses import dataclass
from dateutil.relativedelta import relativedelta
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .models import Account, Transaction, Debt, RecurringRule
from .money import convert_to_ars_minor
from .fx import current_rate_micro
from .recurring import project_future_occurrences


@dataclass
class AccountSnapshot:
    account: Account
    balance_minor: int
    balance_ars_minor: int


@dataclass
class DebtSnapshot:
    debt: Debt
    outstanding_minor: int
    outstanding_ars_minor: int


@dataclass
class NetWorth:
    accounts_ars_minor: int = 0
    receivables_ars_minor: int = 0
    payables_ars_minor: int = 0
    @property
    def total_minor(self) -> int:
        return self.accounts_ars_minor + self.receivables_ars_minor - self.payables_ars_minor


def account_balances(session: Session, user_id: int) -> list[AccountSnapshot]:
    R = current_rate_micro(session, user_id)
    snaps: list[AccountSnapshot] = []
    accounts = session.execute(
        select(Account)
        .where(Account.user_id == user_id, Account.archived == 0)
        .order_by(Account.id)
    ).scalars().all()
    for acc in accounts:
        bal = acc.opening_balance_minor
        rows = session.execute(
            select(Transaction.kind, func.coalesce(func.sum(Transaction.amount_minor), 0))
            .where(Transaction.account_id == acc.id, Transaction.user_id == user_id)
            .group_by(Transaction.kind)
        ).all()
        for kind, total in rows:
            if kind in ("income", "transfer_in"):
                bal += total
            elif kind in ("expense", "transfer_out"):
                bal -= total
        ars = convert_to_ars_minor(bal, acc.currency, R if acc.currency == "USD" else None)
        snaps.append(AccountSnapshot(acc, bal, ars))
    return snaps


def debt_outstanding(session: Session, debt: Debt) -> int:
    paid = session.execute(
        select(func.coalesce(func.sum(Transaction.amount_minor), 0))
        .where(Transaction.debt_id == debt.id)
    ).scalar_one()
    return max(0, debt.principal_minor - paid)


def open_debts(session: Session, user_id: int) -> tuple[list[DebtSnapshot], list[DebtSnapshot]]:
    R = current_rate_micro(session, user_id)
    debts = session.execute(
        select(Debt)
        .where(Debt.user_id == user_id, Debt.status != "cancelled")
        .order_by(Debt.due_on.is_(None), Debt.due_on, Debt.id)
    ).scalars().all()
    recv: list[DebtSnapshot] = []
    pay: list[DebtSnapshot] = []
    for d in debts:
        out = debt_outstanding(session, d)
        if out <= 0:
            continue
        out_ars = convert_to_ars_minor(out, d.currency, R if d.currency == "USD" else None)
        snap = DebtSnapshot(d, out, out_ars)
        (recv if d.direction == "receivable" else pay).append(snap)
    return recv, pay


def net_worth(session: Session, user_id: int) -> NetWorth:
    nw = NetWorth()
    for s in account_balances(session, user_id):
        nw.accounts_ars_minor += s.balance_ars_minor
    recv, pay = open_debts(session, user_id)
    for s in recv:
        nw.receivables_ars_minor += s.outstanding_ars_minor
    for s in pay:
        nw.payables_ars_minor += s.outstanding_ars_minor
    return nw


def monthly_recurring_flow(session: Session, user_id: int, today: date | None = None) -> tuple[int, int, int]:
    today = today or date.today()
    R = current_rate_micro(session, user_id)
    rules = session.execute(
        select(RecurringRule).where(
            RecurringRule.user_id == user_id,
            RecurringRule.active == 1,
        )
    ).scalars().all()
    inc = 0
    exp = 0
    for r in rules:
        if r.start_date > today:
            continue
        if r.end_date and r.end_date < today:
            continue
        ars = convert_to_ars_minor(r.amount_minor, r.currency, R if r.currency == "USD" else None)
        if r.kind == "income":
            inc += ars
        else:
            exp += ars
    return inc, exp, inc - exp


@dataclass
class ProjectionRow:
    month_label: str
    period_end: date
    income_ars_minor: int = 0
    expense_ars_minor: int = 0
    receivable_due_ars_minor: int = 0
    payable_due_ars_minor: int = 0
    net_change_ars_minor: int = 0
    closing_nw_ars_minor: int = 0


def projection(session: Session, user_id: int, n_months: int, today: date | None = None) -> list[ProjectionRow]:
    today = today or date.today()
    R = current_rate_micro(session, user_id)
    nw_now = net_worth(session, user_id).total_minor

    buckets: list[tuple[date, date, str]] = []
    for i in range(n_months):
        if i == 0:
            period_start = today + relativedelta(days=1)
            period_end = (today.replace(day=1) + relativedelta(months=1)) - relativedelta(days=1)
            if period_end < period_start:
                period_end = period_start + relativedelta(months=1) - relativedelta(days=1)
        else:
            prev_end = buckets[-1][1]
            period_start = prev_end + relativedelta(days=1)
            period_end = period_start + relativedelta(months=1) - relativedelta(days=1)
        label = period_start.strftime("%Y-%m")
        buckets.append((period_start, period_end, label))

    proj_rows = [ProjectionRow(month_label=lbl, period_end=e) for (_, e, lbl) in buckets]
    horizon = buckets[-1][1]

    for occ, rule in project_future_occurrences(session, user_id, start=today, n_months=n_months + 1):
        if occ > horizon:
            continue
        for i, (s, e, _) in enumerate(buckets):
            if s <= occ <= e:
                ars = convert_to_ars_minor(rule.amount_minor, rule.currency, R if rule.currency == "USD" else None)
                if rule.kind == "income":
                    proj_rows[i].income_ars_minor += ars
                else:
                    proj_rows[i].expense_ars_minor += ars
                break

    recv, pay = open_debts(session, user_id)
    for s in recv:
        idx = _bucket_index(buckets, s.debt.due_on) if s.debt.due_on else 0
        if idx is None: continue
        proj_rows[idx].receivable_due_ars_minor += s.outstanding_ars_minor
    for s in pay:
        idx = _bucket_index(buckets, s.debt.due_on) if s.debt.due_on else 0
        if idx is None: continue
        proj_rows[idx].payable_due_ars_minor += s.outstanding_ars_minor

    running = nw_now
    for row in proj_rows:
        row.net_change_ars_minor = (
            row.income_ars_minor - row.expense_ars_minor
            + row.receivable_due_ars_minor - row.payable_due_ars_minor
        )
        running += row.net_change_ars_minor
        row.closing_nw_ars_minor = running
    return proj_rows


def _bucket_index(buckets, d: date) -> int | None:
    for i, (s, e, _) in enumerate(buckets):
        if s <= d <= e:
            return i
    if d < buckets[0][0]:
        return 0
    return None
