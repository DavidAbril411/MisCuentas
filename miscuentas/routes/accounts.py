from flask import Blueprint, render_template, request, redirect, url_for, g, flash
from sqlalchemy import select

from ..models import Account
from ..money import to_minor, fx_to_micro
from ..metrics import account_balances

bp = Blueprint("accounts", __name__)


@bp.route("")
def list_accounts():
    snaps = account_balances(g.session)
    return render_template("accounts/list.html", snaps=snaps)


@bp.route("/new", methods=["GET", "POST"])
def new():
    if request.method == "POST":
        currency = request.form["currency"]
        opening_balance = request.form.get("opening_balance", "0").strip() or "0"
        opening_fx = request.form.get("opening_fx", "").strip()
        acc = Account(
            name=request.form["name"].strip(),
            currency=currency,
            opening_balance_minor=to_minor(opening_balance),
            opening_fx_rate_to_ars_micro=(
                fx_to_micro(opening_fx) if currency == "USD" and opening_fx else None
            ),
        )
        g.session.add(acc)
        g.session.commit()
        flash("Cuenta creada", "success")
        return redirect(url_for("accounts.list_accounts"))
    return render_template("accounts/form.html", account=None)


@bp.route("/<int:acc_id>/edit", methods=["GET", "POST"])
def edit(acc_id):
    acc = g.session.get(Account, acc_id)
    if acc is None:
        flash("Cuenta no encontrada", "danger")
        return redirect(url_for("accounts.list_accounts"))
    if request.method == "POST":
        acc.name = request.form["name"].strip()
        acc.archived = 1 if request.form.get("archived") else 0
        g.session.commit()
        flash("Cuenta actualizada", "success")
        return redirect(url_for("accounts.list_accounts"))
    return render_template("accounts/form.html", account=acc)
