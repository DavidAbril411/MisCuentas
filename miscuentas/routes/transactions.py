from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, g, flash
from sqlalchemy import select

from ..models import Account, Category, Transaction
from ..money import to_minor, fx_to_micro, fx_from_micro
from ..fx import current_rate_micro

bp = Blueprint("transactions", __name__)


@bp.route("")
def list_tx():
    session = g.session
    month = request.args.get("month")
    account_id = request.args.get("account_id", type=int)
    kind = request.args.get("kind")
    q = select(Transaction).order_by(Transaction.occurred_on.desc(), Transaction.id.desc())
    if month:
        q = q.where(Transaction.occurred_on.like(f"{month}%"))
    if account_id:
        q = q.where(Transaction.account_id == account_id)
    if kind:
        q = q.where(Transaction.kind == kind)
    txs = session.execute(q.limit(500)).scalars().all()
    accounts = session.execute(select(Account).order_by(Account.name)).scalars().all()
    return render_template(
        "transactions/list.html",
        txs=txs, accounts=accounts,
        month=month, account_id=account_id, kind=kind,
    )


@bp.route("/new", methods=["GET", "POST"])
def new():
    session = g.session
    accounts = session.execute(select(Account).where(Account.archived == 0).order_by(Account.name)).scalars().all()
    categories = session.execute(select(Category).order_by(Category.name)).scalars().all()
    try:
        current_rate = fx_from_micro(current_rate_micro(session))
    except RuntimeError:
        current_rate = None

    if request.method == "POST":
        currency = request.form["currency"]
        amount_minor = to_minor(request.form["amount"])
        fx_micro = None
        if currency == "USD":
            fx_in = request.form.get("fx_rate", "").strip()
            fx_micro = fx_to_micro(fx_in) if fx_in else current_rate_micro(session)
        tx = Transaction(
            occurred_on=datetime.strptime(request.form["occurred_on"], "%Y-%m-%d").date(),
            account_id=int(request.form["account_id"]),
            category_id=int(request.form["category_id"]) if request.form.get("category_id") else None,
            kind=request.form["kind"],
            amount_minor=amount_minor,
            currency=currency,
            fx_rate_to_ars_micro=fx_micro,
            description=request.form.get("description", "").strip() or None,
        )
        session.add(tx)
        session.commit()
        flash("Movimiento creado", "success")
        return redirect(url_for("transactions.list_tx"))

    return render_template(
        "transactions/form.html",
        tx=None, accounts=accounts, categories=categories,
        current_rate=current_rate, today=date.today(),
    )


@bp.route("/<int:tx_id>/edit", methods=["GET", "POST"])
def edit(tx_id):
    session = g.session
    tx = session.get(Transaction, tx_id)
    if tx is None:
        flash("Movimiento no encontrado", "danger")
        return redirect(url_for("transactions.list_tx"))
    if tx.recurring_rule_id or tx.debt_id:
        flash("Este movimiento es automático (recurrente o pago de deuda). Editá el origen.", "warning")
        return redirect(url_for("transactions.list_tx"))
    accounts = session.execute(select(Account).order_by(Account.name)).scalars().all()
    categories = session.execute(select(Category).order_by(Category.name)).scalars().all()
    if request.method == "POST":
        currency = request.form["currency"]
        tx.occurred_on = datetime.strptime(request.form["occurred_on"], "%Y-%m-%d").date()
        tx.account_id = int(request.form["account_id"])
        tx.category_id = int(request.form["category_id"]) if request.form.get("category_id") else None
        tx.kind = request.form["kind"]
        tx.amount_minor = to_minor(request.form["amount"])
        tx.currency = currency
        if currency == "USD":
            fx_in = request.form.get("fx_rate", "").strip()
            tx.fx_rate_to_ars_micro = fx_to_micro(fx_in) if fx_in else current_rate_micro(session)
        else:
            tx.fx_rate_to_ars_micro = None
        tx.description = request.form.get("description", "").strip() or None
        session.commit()
        flash("Movimiento actualizado", "success")
        return redirect(url_for("transactions.list_tx"))
    return render_template(
        "transactions/form.html",
        tx=tx, accounts=accounts, categories=categories,
        current_rate=fx_from_micro(tx.fx_rate_to_ars_micro) if tx.fx_rate_to_ars_micro else None,
        today=tx.occurred_on,
    )


@bp.route("/<int:tx_id>/delete", methods=["POST"])
def delete(tx_id):
    session = g.session
    tx = session.get(Transaction, tx_id)
    if tx is None:
        flash("Movimiento no encontrado", "danger")
    elif tx.recurring_rule_id or tx.debt_id:
        flash("No se puede borrar un movimiento automático. Eliminá la regla o la deuda.", "warning")
    else:
        session.delete(tx)
        session.commit()
        flash("Movimiento borrado", "success")
    return redirect(url_for("transactions.list_tx"))
