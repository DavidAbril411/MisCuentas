from datetime import date
from flask import Blueprint, render_template, g, current_app, redirect, url_for
from flask_login import login_required, current_user

from ..metrics import (
    net_worth, account_balances, open_debts,
    monthly_recurring_flow, projection,
)
from ..fx import current_rate_micro
from ..money import fx_from_micro

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    session = g.session
    uid = current_user.id
    try:
        rate_micro = current_rate_micro(session, uid)
    except RuntimeError:
        return render_template("no_fx.html")

    nw = net_worth(session, uid)
    accs = account_balances(session, uid)
    recv, pay = open_debts(session, uid)
    inc, exp, net_flow = monthly_recurring_flow(session, uid)
    n_months = current_app.config.get("PROJECTION_MONTHS", 12)
    proj = projection(session, uid, n_months)
    return render_template(
        "dashboard.html",
        today=date.today(),
        rate=fx_from_micro(rate_micro),
        nw=nw, accounts=accs,
        receivables=recv, payables=pay,
        rec_income=inc, rec_expense=exp, rec_net=net_flow,
        projection=proj,
    )
