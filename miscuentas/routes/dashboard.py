from datetime import date
from flask import Blueprint, render_template, g, current_app

from ..metrics import (
    net_worth, account_balances, open_debts,
    monthly_recurring_flow, projection,
)
from ..fx import current_rate_micro
from ..money import fx_from_micro

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    session = g.session
    try:
        rate_micro = current_rate_micro(session)
    except RuntimeError:
        return render_template("no_fx.html")

    nw = net_worth(session)
    accs = account_balances(session)
    recv, pay = open_debts(session)
    inc, exp, net_flow = monthly_recurring_flow(session)
    n_months = current_app.config.get("PROJECTION_MONTHS", 12)
    proj = projection(session, n_months)
    return render_template(
        "dashboard.html",
        today=date.today(),
        rate=fx_from_micro(rate_micro),
        nw=nw,
        accounts=accs,
        receivables=recv,
        payables=pay,
        rec_income=inc,
        rec_expense=exp,
        rec_net=net_flow,
        projection=proj,
    )
