from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from flask import Blueprint, render_template, request, redirect, url_for, g, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import select

from ..models import Account, Category, Transaction, Debt, RecurringRule
from ..money import to_minor, fx_to_micro, fx_from_micro
from ..fx import current_rate_micro
from ..metrics import debt_outstanding
from ..recurring import materialize_recurring

bp = Blueprint("transactions", __name__)


def _own_tx(session, tx_id: int) -> Transaction | None:
    tx = session.get(Transaction, tx_id)
    if tx is None or tx.user_id != current_user.id:
        return None
    return tx


def _check_account_currency(session, account_id: int, currency: str) -> str | None:
    acc = session.get(Account, account_id)
    if acc is None or acc.user_id != current_user.id:
        return "Cuenta inexistente."
    if acc.currency != currency:
        return (f"La cuenta '{acc.name}' es {acc.currency}; no podés cargar "
                f"un movimiento en {currency}. Cambiá la moneda o elegí otra cuenta.")
    return None


def _refresh_debt_status(session, debt: Debt):
    out = debt_outstanding(session, debt)
    if out <= 0:
        debt.status = "settled"
    elif out < debt.principal_minor:
        debt.status = "partial"
    else:
        debt.status = "open"


@bp.route("")
@login_required
def list_tx():
    session = g.session
    uid = current_user.id
    month = request.args.get("month")
    account_id = request.args.get("account_id", type=int)
    kind = request.args.get("kind")
    q = (select(Transaction)
         .where(Transaction.user_id == uid)
         .order_by(Transaction.occurred_on.desc(), Transaction.id.desc()))
    if month:
        q = q.where(Transaction.occurred_on.like(f"{month}%"))
    if account_id:
        q = q.where(Transaction.account_id == account_id)
    if kind:
        q = q.where(Transaction.kind == kind)
    txs = session.execute(q.limit(500)).scalars().all()
    accounts = session.execute(
        select(Account).where(Account.user_id == uid).order_by(Account.name)
    ).scalars().all()
    return render_template(
        "transactions/list.html",
        txs=txs, accounts=accounts,
        month=month, account_id=account_id, kind=kind,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    session = g.session
    uid = current_user.id
    accounts = session.execute(
        select(Account).where(Account.user_id == uid, Account.archived == 0).order_by(Account.name)
    ).scalars().all()
    categories = session.execute(
        select(Category).where(Category.user_id == uid).order_by(Category.name)
    ).scalars().all()
    try:
        current_rate = fx_from_micro(current_rate_micro(session, uid))
    except RuntimeError:
        current_rate = None

    if request.method == "POST":
        currency = request.form["currency"]
        account_id = int(request.form["account_id"])
        err = _check_account_currency(session, account_id, currency)
        if err:
            flash(err, "danger")
            return render_template("transactions/form.html",
                tx=None, accounts=accounts, categories=categories,
                current_rate=current_rate, today=date.today())
        fx_micro = None
        if currency == "USD":
            fx_in = request.form.get("fx_rate", "").strip()
            fx_micro = fx_to_micro(fx_in) if fx_in else current_rate_micro(session, uid)
        tx = Transaction(
            user_id=uid,
            occurred_on=datetime.strptime(request.form["occurred_on"], "%Y-%m-%d").date(),
            account_id=account_id,
            category_id=int(request.form["category_id"]) if request.form.get("category_id") else None,
            kind=request.form["kind"],
            amount_minor=to_minor(request.form["amount"]),
            currency=currency,
            fx_rate_to_ars_micro=fx_micro,
            description=request.form.get("description", "").strip() or None,
        )
        session.add(tx)
        session.commit()
        flash("Movimiento creado", "success")
        return redirect(url_for("transactions.list_tx"))

    return render_template("transactions/form.html",
        tx=None, accounts=accounts, categories=categories,
        current_rate=current_rate, today=date.today())


@bp.route("/<int:tx_id>/edit", methods=["GET", "POST"])
@login_required
def edit(tx_id):
    session = g.session
    uid = current_user.id
    tx = _own_tx(session, tx_id)
    if tx is None:
        abort(404)
    accounts = session.execute(
        select(Account).where(Account.user_id == uid).order_by(Account.name)
    ).scalars().all()
    categories = session.execute(
        select(Category).where(Category.user_id == uid).order_by(Category.name)
    ).scalars().all()
    if request.method == "POST":
        currency = request.form["currency"]
        account_id = int(request.form["account_id"])
        err = _check_account_currency(session, account_id, currency)
        if err:
            flash(err, "danger")
            return render_template("transactions/form.html",
                tx=tx, accounts=accounts, categories=categories,
                current_rate=fx_from_micro(tx.fx_rate_to_ars_micro) if tx.fx_rate_to_ars_micro else None,
                today=tx.occurred_on)
        tx.occurred_on = datetime.strptime(request.form["occurred_on"], "%Y-%m-%d").date()
        tx.account_id = account_id
        tx.category_id = int(request.form["category_id"]) if request.form.get("category_id") else None
        tx.kind = request.form["kind"]
        tx.amount_minor = to_minor(request.form["amount"])
        tx.currency = currency
        if currency == "USD":
            fx_in = request.form.get("fx_rate", "").strip()
            tx.fx_rate_to_ars_micro = fx_to_micro(fx_in) if fx_in else current_rate_micro(session, uid)
        else:
            tx.fx_rate_to_ars_micro = None
        tx.description = request.form.get("description", "").strip() or None
        if tx.debt_id:
            debt = session.get(Debt, tx.debt_id)
            session.flush()
            _refresh_debt_status(session, debt)
        session.commit()
        flash("Movimiento actualizado", "success")
        return redirect(url_for("transactions.list_tx"))
    return render_template("transactions/form.html",
        tx=tx, accounts=accounts, categories=categories,
        current_rate=fx_from_micro(tx.fx_rate_to_ars_micro) if tx.fx_rate_to_ars_micro else None,
        today=tx.occurred_on)


@bp.route("/<int:tx_id>/delete", methods=["POST"])
@login_required
def delete(tx_id):
    session = g.session
    tx = _own_tx(session, tx_id)
    if tx is None:
        abort(404)
    debt_id = tx.debt_id
    session.delete(tx)
    session.flush()
    if debt_id:
        debt = session.get(Debt, debt_id)
        if debt is not None:
            _refresh_debt_status(session, debt)
    session.commit()
    flash("Movimiento borrado", "success")
    return redirect(url_for("transactions.list_tx"))


@bp.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():
    session = g.session
    accounts = session.execute(
        select(Account)
        .where(Account.archived == 0, Account.user_id == current_user.id)
        .order_by(Account.name)
    ).scalars().all()
    if request.method == "POST":
        source_id = int(request.form["source_account_id"])
        dest_id = int(request.form["dest_account_id"])
        if source_id == dest_id:
            flash("La cuenta origen y destino deben ser distintas.", "danger")
            return render_template("transactions/transfer.html", accounts=accounts, today=date.today())
        
        source = session.get(Account, source_id)
        dest = session.get(Account, dest_id)
        if source is None or source.user_id != current_user.id or dest is None or dest.user_id != current_user.id:
            abort(404)
            
        occurred_on = datetime.strptime(request.form["occurred_on"], "%Y-%m-%d").date()
        amount_minor = to_minor(request.form["amount"])
        description = request.form.get("description", "").strip() or f"Transferencia de {source.name} a {dest.name}"
        
        rate_micro = current_rate_micro(session)
        amount_dest_minor = amount_minor
        if source.currency == "ARS" and dest.currency == "USD":
            amount_dest_minor = amount_minor * 1_000_000 // rate_micro
        elif source.currency == "USD" and dest.currency == "ARS":
            amount_dest_minor = amount_minor * rate_micro // 1_000_000

        # Source transaction (transfer_out)
        tx_out = Transaction(
            user_id=current_user.id,
            occurred_on=occurred_on,
            account_id=source.id,
            kind="transfer_out",
            amount_minor=amount_minor,
            currency=source.currency,
            description=description,
            fx_rate_to_ars_micro=rate_micro if source.currency == "USD" else None
        )
        # Destination transaction (transfer_in)
        tx_in = Transaction(
            user_id=current_user.id,
            occurred_on=occurred_on,
            account_id=dest.id,
            kind="transfer_in",
            amount_minor=amount_dest_minor,
            currency=dest.currency,
            description=description,
            fx_rate_to_ars_micro=rate_micro if dest.currency == "USD" else None
        )
        session.add(tx_out)
        session.add(tx_in)
        session.commit()
        flash("Transferencia registrada con éxito", "success")
        return redirect(url_for("transactions.list_tx"))
        
    return render_template("transactions/transfer.html", accounts=accounts, today=date.today())


@bp.route("/new_installment", methods=["GET", "POST"])
@login_required
def new_installment():
    session = g.session
    accounts = session.execute(
        select(Account)
        .where(Account.archived == 0, Account.user_id == current_user.id)
        .order_by(Account.name)
    ).scalars().all()
    categories = session.execute(
        select(Category)
        .where(Category.user_id == current_user.id)
        .order_by(Category.name)
    ).scalars().all()
    
    if request.method == "POST":
        account_id = int(request.form["account_id"])
        category_id = int(request.form["category_id"]) if request.form.get("category_id") else None
        amount_val = request.form["amount"]
        installments_count = int(request.form["installments_count"])
        occurred_on = datetime.strptime(request.form["occurred_on"], "%Y-%m-%d").date()
        name = request.form["name"].strip()
        
        account = session.get(Account, account_id)
        if account is None or account.user_id != current_user.id:
            abort(404)
        if category_id:
            category = session.get(Category, category_id)
            if category is None or category.user_id != current_user.id:
                abort(404)
        
        day_of_month = min(28, max(1, occurred_on.day))
        start_date = occurred_on
        end_date = start_date + relativedelta(months=installments_count - 1)
        
        rule = RecurringRule(
            user_id=current_user.id,
            name=f"{name} (Cuota)",
            kind="expense",
            amount_minor=to_minor(amount_val),
            currency=account.currency,
            account_id=account.id,
            category_id=category_id,
            day_of_month=day_of_month,
            start_date=start_date,
            end_date=end_date,
            active=1,
            notes=f"Compra en {installments_count} cuotas de {amount_val} {account.currency}"
        )
        session.add(rule)
        session.flush()
        
        materialize_recurring(session, date.today())
        session.commit()
        
        flash("Compra en cuotas registrada con éxito", "success")
        return redirect(url_for("recurring.list_rules"))
        
    return render_template("transactions/new_installment.html", accounts=accounts, categories=categories, today=date.today())

