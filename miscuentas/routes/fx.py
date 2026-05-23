from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, g, flash
from flask_login import login_required, current_user
from sqlalchemy import select

from ..models import FxRate
from ..fx import set_rate

bp = Blueprint("fx", __name__)


@bp.route("")
@login_required
def list_rates():
    uid = current_user.id
    rates = g.session.execute(
        select(FxRate).where(FxRate.user_id == uid).order_by(FxRate.effective_on.desc())
    ).scalars().all()
    return render_template("fx/list.html", rates=rates)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        on = datetime.strptime(request.form["effective_on"], "%Y-%m-%d").date()
        set_rate(g.session, current_user.id, on, request.form["rate"], request.form.get("source") or None)
        g.session.commit()
        flash("Cotización guardada", "success")
        return redirect(url_for("fx.list_rates"))
    return render_template("fx/form.html", today=date.today())
