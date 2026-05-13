from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, g, flash
from sqlalchemy import select

from ..models import Account, Category, RecurringRule
from ..money import to_minor
from ..recurring import materialize_recurring

bp = Blueprint("recurring", __name__)


@bp.route("")
def list_rules():
    rules = g.session.execute(
        select(RecurringRule).order_by(RecurringRule.active.desc(), RecurringRule.kind, RecurringRule.name)
    ).scalars().all()
    return render_template("recurring/list.html", rules=rules)


def _parse_date(s, default=None):
    if not s:
        return default
    return datetime.strptime(s, "%Y-%m-%d").date()


@bp.route("/new", methods=["GET", "POST"])
def new():
    session = g.session
    accounts = session.execute(select(Account).where(Account.archived == 0).order_by(Account.name)).scalars().all()
    categories = session.execute(select(Category).order_by(Category.name)).scalars().all()
    if request.method == "POST":
        rule = RecurringRule(
            name=request.form["name"].strip(),
            kind=request.form["kind"],
            amount_minor=to_minor(request.form["amount"]),
            currency=request.form["currency"],
            account_id=int(request.form["account_id"]),
            category_id=int(request.form["category_id"]) if request.form.get("category_id") else None,
            day_of_month=int(request.form["day_of_month"]),
            start_date=_parse_date(request.form["start_date"], date.today()),
            end_date=_parse_date(request.form.get("end_date"), None),
            active=1 if request.form.get("active", "on") else 0,
            notes=request.form.get("notes", "").strip() or None,
        )
        session.add(rule)
        session.commit()
        flash("Regla creada", "success")
        return redirect(url_for("recurring.list_rules"))
    return render_template(
        "recurring/form.html", rule=None,
        accounts=accounts, categories=categories, today=date.today(),
    )


@bp.route("/<int:rule_id>/edit", methods=["GET", "POST"])
def edit(rule_id):
    session = g.session
    rule = session.get(RecurringRule, rule_id)
    if rule is None:
        flash("Regla no encontrada", "danger")
        return redirect(url_for("recurring.list_rules"))
    accounts = session.execute(select(Account).order_by(Account.name)).scalars().all()
    categories = session.execute(select(Category).order_by(Category.name)).scalars().all()
    if request.method == "POST":
        rule.name = request.form["name"].strip()
        rule.kind = request.form["kind"]
        rule.amount_minor = to_minor(request.form["amount"])
        rule.currency = request.form["currency"]
        rule.account_id = int(request.form["account_id"])
        rule.category_id = int(request.form["category_id"]) if request.form.get("category_id") else None
        rule.day_of_month = int(request.form["day_of_month"])
        rule.start_date = _parse_date(request.form["start_date"], rule.start_date)
        rule.end_date = _parse_date(request.form.get("end_date"), None)
        rule.active = 1 if request.form.get("active") else 0
        rule.notes = request.form.get("notes", "").strip() or None
        session.commit()
        flash("Regla actualizada", "success")
        return redirect(url_for("recurring.list_rules"))
    return render_template(
        "recurring/form.html", rule=rule,
        accounts=accounts, categories=categories, today=date.today(),
    )


@bp.route("/<int:rule_id>/toggle", methods=["POST"])
def toggle(rule_id):
    session = g.session
    rule = session.get(RecurringRule, rule_id)
    if rule is None:
        flash("Regla no encontrada", "danger")
    else:
        rule.active = 0 if rule.active else 1
        session.commit()
    return redirect(url_for("recurring.list_rules"))


@bp.route("/materialize", methods=["POST"])
def materialize():
    n = materialize_recurring(g.session, date.today())
    g.session.commit()
    flash(f"Generados {n} movimientos pendientes.", "success")
    return redirect(url_for("recurring.list_rules"))
