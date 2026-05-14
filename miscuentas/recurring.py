"""Materialize recurring rules into real transactions, and project future months."""

from __future__ import annotations
from datetime import date
from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import RecurringRule, Transaction
from .fx import rate_at_micro


def _occurrence(year: int, month: int, day_of_month: int) -> date:
    return date(year, month, day_of_month)


def _iter_occurrences(rule: RecurringRule, up_to: date):
    end = rule.end_date or up_to
    if end > up_to:
        end = up_to

    cur_y = rule.start_date.year
    cur_m = rule.start_date.month
    while True:
        try:
            occ = _occurrence(cur_y, cur_m, rule.day_of_month)
        except ValueError:
            occ = None
        if occ is not None:
            if occ < rule.start_date:
                pass
            elif occ > end:
                return
            else:
                yield occ
        cur_m += 1
        if cur_m > 12:
            cur_m = 1
            cur_y += 1
        if date(cur_y, cur_m, 1) > end:
            return


def materialize_recurring(session: Session, user_id: int, up_to: date) -> int:
    rules = session.execute(
        select(RecurringRule).where(
            RecurringRule.user_id == user_id,
            RecurringRule.active == 1,
        )
    ).scalars().all()

    created = 0
    for rule in rules:
        existing_dates = {
            d for (d,) in session.execute(
                select(Transaction.occurred_on)
                .where(Transaction.recurring_rule_id == rule.id)
            ).all()
        }
        for occ in _iter_occurrences(rule, up_to):
            if occ in existing_dates:
                continue
            fx_micro = None
            if rule.currency == "USD":
                fx_micro = rate_at_micro(session, user_id, occ)
            tx = Transaction(
                user_id=user_id,
                occurred_on=occ,
                account_id=rule.account_id,
                category_id=rule.category_id,
                kind=rule.kind,
                amount_minor=rule.amount_minor,
                currency=rule.currency,
                fx_rate_to_ars_micro=fx_micro,
                description=rule.name,
                recurring_rule_id=rule.id,
            )
            session.add(tx)
            existing_dates.add(occ)
            created += 1
    if created:
        session.flush()
    return created


def project_future_occurrences(session: Session, user_id: int, start: date, n_months: int):
    horizon = start + relativedelta(months=n_months)
    rules = session.execute(
        select(RecurringRule).where(
            RecurringRule.user_id == user_id,
            RecurringRule.active == 1,
        )
    ).scalars().all()
    for rule in rules:
        end = rule.end_date or horizon
        if end > horizon:
            end = horizon
        cur_y = max(rule.start_date.year, start.year)
        cur_m = max(rule.start_date.month, start.month) if cur_y == start.year else 1
        if (cur_y, cur_m) < (rule.start_date.year, rule.start_date.month):
            cur_y, cur_m = rule.start_date.year, rule.start_date.month
        while True:
            try:
                occ = _occurrence(cur_y, cur_m, rule.day_of_month)
            except ValueError:
                occ = None
            if occ is not None and occ > start and occ <= end:
                yield occ, rule
            cur_m += 1
            if cur_m > 12:
                cur_m = 1
                cur_y += 1
            if date(cur_y, cur_m, 1) > end:
                break
