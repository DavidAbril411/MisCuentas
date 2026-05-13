from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, g, flash
from sqlalchemy import select

from ..models import Account, Debt, Transaction
from ..money import to_minor, fx_to_micro, fx_from_micro
from ..fx import current_rate_micro
from ..metrics import open_debts, debt_outstanding

bp = Blueprint("debts", __name__)


def _parse_date(s, default=None):
    if not s:
        return default
    return datetime.strptime(s, "%Y-%m-%d").date()


@bp.route("")
def list_debts():
    recv, pay = open_debts(g.session)
    settled = g.session.execute(
        select(Debt).where(Debt.status == "settled").order_by(Debt.id.desc()).limit(20)
    ).scalars().all()
    return render_template("debts/list.html", receivables=recv, payables=pay, settled=settled)


@bp.route("/new", methods=["GET", "POST"])
def new():
    session = g.session
    try:
        current_rate = fx_from_micro(current_rate_micro(session))
    except RuntimeError:
        current_rate = None
    if request.method == "POST":
        currency = request.form["currency"]
        fx_micro = None
        if currency == "USD":
            fx_in = request.form.get("fx_rate", "").strip()
            fx_micro = fx_to_micro(fx_in) if fx_in else current_rate_micro(session)
        debt = Debt(
            counterparty=request.form["counterparty"].strip(),
            direction=request.form["direction"],
            principal_minor=to_minor(request.form["principal"]),
            currency=currency,
            fx_rate_to_ars_micro=fx_micro,
            opened_on=_parse_date(request.form.get("opened_on"), date.today()),
            due_on=_parse_date(request.form.get("due_on"), None),
            notes=request.form.get("notes", "").strip() or None,
        )
        session.add(debt)
        session.commit()
        flash("Deuda creada", "success")
        return redirect(url_for("debts.list_debts"))
    return render_template("debts/form.html", debt=None, current_rate=current_rate, today=date.today())


@bp.route("/<int:debt_id>/edit", methods=["GET", "POST"])
def edit(debt_id):
    session = g.session
    debt = session.get(Debt, debt_id)
    if debt is None:
        flash("Deuda no encontrada", "danger")
        return redirect(url_for("debts.list_debts"))
    if request.method == "POST":
        debt.counterparty = request.form["counterparty"].strip()
        debt.due_on = _parse_date(request.form.get("due_on"), None)
        debt.notes = request.form.get("notes", "").strip() or None
        debt.status = request.form.get("status", debt.status)
        session.commit()
        flash("Deuda actualizada", "success")
        return redirect(url_for("debts.list_debts"))
    return render_template(
        "debts/form.html", debt=debt,
        current_rate=fx_from_micro(debt.fx_rate_to_ars_micro) if debt.fx_rate_to_ars_micro else None,
        today=date.today(),
    )


@bp.route("/<int:debt_id>/pay", methods=["GET", "POST"])
def pay(debt_id):
    session = g.session
    debt = session.get(Debt, debt_id)
    if debt is None:
        flash("Deuda no encontrada", "danger")
        return redirect(url_for("debts.list_debts"))
    accounts = session.execute(select(Account).where(Account.archived == 0).order_by(Account.name)).scalars().all()
    try:
        current_rate = fx_from_micro(current_rate_micro(session))
    except RuntimeError:
        current_rate = None
    outstanding = debt_outstanding(session, debt)

    if request.method == "POST":
        amount_minor = to_minor(request.form["amount"])
        currency = debt.currency
        fx_micro = None
        if currency == "USD":
            fx_in = request.form.get("fx_rate", "").strip()
            fx_micro = fx_to_micro(fx_in) if fx_in else current_rate_micro(session)
        kind = "income" if debt.direction == "receivable" else "expense"
        tx = Transaction(
            occurred_on=_parse_date(request.form.get("occurred_on"), date.today()),
            account_id=int(request.form["account_id"]),
            kind=kind,
            amount_minor=amount_minor,
            currency=currency,
            fx_rate_to_ars_micro=fx_micro,
            description=f"Pago de deuda: {debt.counterparty}",
            debt_id=debt.id,
        )
        session.add(tx)
        session.flush()
        new_outstanding = debt_outstanding(session, debt)
        if new_outstanding == 0:
            debt.status = "settled"
        elif new_outstanding < debt.principal_minor:
            debt.status = "partial"
        session.commit()
        flash("Pago registrado", "success")
        return redirect(url_for("debts.list_debts"))

    return render_template(
        "debts/pay.html", debt=debt, accounts=accounts,
        current_rate=current_rate, outstanding=outstanding, today=date.today(),
    )
