from datetime import date
from dateutil.relativedelta import relativedelta
from flask import Blueprint, render_template, g
from sqlalchemy import select

from ..models import Account, RecurringRule, Category
from ..money import convert_to_ars_minor, format_money
from ..fx import current_rate_micro

bp = Blueprint("mensual", __name__)


@bp.route("")
def grid():
    session = g.session
    try:
        rate_micro = current_rate_micro(session)
    except RuntimeError:
        return render_template("no_fx.html")
    
    # 1. Generate next 12 months starting from current month
    today = date.today()
    start_month = today.replace(day=1)
    months = [start_month + relativedelta(months=i) for i in range(12)]
    month_labels = [m.strftime("%Y-%m") for m in months]
    month_names = [
        ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"][m.month - 1] + f" {m.year % 100}"
        for m in months
    ]
    
    # Fetch all accounts
    accounts = session.execute(select(Account).where(Account.archived == 0).order_by(Account.name)).scalars().all()
    credit_cards = [a for a in accounts if a.is_credit_card]
    bank_accounts = [a for a in accounts if not a.is_credit_card]
    
    # Fetch all recurring rules
    rules = session.execute(select(RecurringRule).where(RecurringRule.active == 1).order_by(RecurringRule.name)).scalars().all()
    
    # We will build rows for three tables:
    # 1. Credit Card rules/installments
    # 2. General Expense rules
    # 3. Income rules
    
    credit_card_rows = []
    general_expense_rows = []
    income_rows = []
    
    # Helper to check if rule is active in month m
    def is_active_in_month(r, m):
        r_start = r.start_date.replace(day=1)
        if r_start > m:
            return False
        if r.end_date:
            r_end = r.end_date.replace(day=1)
            if r_end < m:
                return False
        return True

    for r in rules:
        row_vals = []
        for m in months:
            if is_active_in_month(r, m):
                # Convert to ARS if currency is USD
                val_ars = convert_to_ars_minor(r.amount_minor, r.currency, rate_micro if r.currency == "USD" else None)
                row_vals.append(val_ars)
            else:
                row_vals.append(0)
                
        row_data = {
            "name": r.name,
            "account": r.account.name,
            "currency": r.currency,
            "amount_native": r.amount_minor,
            "values": row_vals, # in ARS minor
            "notes": r.notes or ""
        }
        
        if r.kind == "income":
            income_rows.append(row_data)
        elif r.account.is_credit_card:
            credit_card_rows.append(row_data)
        else:
            general_expense_rows.append(row_data)
            
    # Calculate credit card totals per card and per month
    card_totals = {}
    for card in credit_cards:
        card_totals[card.name] = [0] * 12
        for r_row in credit_card_rows:
            if r_row["account"] == card.name:
                for idx in range(12):
                    card_totals[card.name][idx] += r_row["values"][idx]
                    
    # Calculate general totals per month
    total_income = [0] * 12
    for r_row in income_rows:
        for idx in range(12):
            total_income[idx] += r_row["values"][idx]
            
    total_expense = [0] * 12
    for r_row in credit_card_rows + general_expense_rows:
        for idx in range(12):
            total_expense[idx] += r_row["values"][idx]
            
    net_saldo = [0] * 12
    for idx in range(12):
        net_saldo[idx] = total_income[idx] - total_expense[idx]
        
    return render_template(
        "mensual.html",
        months=months,
        month_names=month_names,
        credit_cards=credit_cards,
        credit_card_rows=credit_card_rows,
        card_totals=card_totals,
        general_expense_rows=general_expense_rows,
        income_rows=income_rows,
        total_income=total_income,
        total_expense=total_expense,
        net_saldo=net_saldo
    )
