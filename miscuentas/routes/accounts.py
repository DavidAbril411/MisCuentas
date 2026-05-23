from flask import Blueprint, render_template, request, redirect, url_for, g, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import select

from ..models import Account
from ..money import to_minor, fx_to_micro
from ..metrics import account_balances

bp = Blueprint("accounts", __name__)


def _own_account(session, acc_id: int) -> Account | None:
    acc = session.get(Account, acc_id)
    if acc is None or acc.user_id != current_user.id:
        return None
    return acc


@bp.route("")
@login_required
def list_accounts():
    snaps = account_balances(g.session, current_user.id)
    return render_template("accounts/list.html", snaps=snaps)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        currency = request.form["currency"]
        opening_balance = (request.form.get("opening_balance") or "0").strip() or "0"
        opening_fx = request.form.get("opening_fx", "").strip()
        is_cc = 1 if request.form.get("is_credit_card") else 0
        acc = Account(
            user_id=current_user.id,
            name=request.form["name"].strip(),
            currency=currency,
            opening_balance_minor=to_minor(opening_balance),
            opening_fx_rate_to_ars_micro=(
                fx_to_micro(opening_fx) if currency == "USD" and opening_fx else None
            ),
            is_credit_card=is_cc,
        )
        g.session.add(acc)
        g.session.commit()
        flash("Cuenta creada", "success")
        return redirect(url_for("accounts.list_accounts"))
    return render_template("accounts/form.html", account=None)


@bp.route("/<int:acc_id>/edit", methods=["GET", "POST"])
@login_required
def edit(acc_id):
    acc = _own_account(g.session, acc_id)
    if acc is None:
        abort(404)
    if request.method == "POST":
        acc.name = request.form["name"].strip()
        acc.archived = 1 if request.form.get("archived") else 0
        acc.is_credit_card = 1 if request.form.get("is_credit_card") else 0
        g.session.commit()
        flash("Cuenta actualizada", "success")
        return redirect(url_for("accounts.list_accounts"))
    return render_template("accounts/form.html", account=acc)
