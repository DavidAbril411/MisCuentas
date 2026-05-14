"""Authentication: Flask-Login + Werkzeug password hashing."""

import re
from flask import Blueprint, render_template, request, redirect, url_for, g, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import select

from .models import User
from .db import get_session

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Necesitás iniciar sesión."
login_manager.login_message_category = "warning"

bp = Blueprint("auth", __name__)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")


@login_manager.user_loader
def _load_user(user_id: str):
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    return get_session().get(User, uid)


def _validate_username(u: str) -> str | None:
    if not u or not USERNAME_RE.match(u):
        return "Usuario inválido: 3-30 caracteres, letras/números/._-"
    return None


def _validate_password(p: str) -> str | None:
    if not p or len(p) < 8:
        return "La contraseña debe tener al menos 8 caracteres."
    return None


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        session = get_session()
        user = session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()
        if user is None or not check_password_hash(user.password_hash, password):
            flash("Usuario o contraseña incorrectos.", "danger")
            return render_template("auth/login.html", username=username), 401
        login_user(user, remember=True)
        next_url = request.args.get("next") or url_for("dashboard.index")
        return redirect(next_url)
    return render_template("auth/login.html", username="")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        err = _validate_username(username) or _validate_password(password)
        if not err and password != confirm:
            err = "Las contraseñas no coinciden."
        if err:
            flash(err, "danger")
            return render_template("auth/register.html", username=username), 400

        session = get_session()
        existing = session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()
        if existing is not None:
            flash("Ese usuario ya existe.", "danger")
            return render_template("auth/register.html", username=username), 400

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
        )
        session.add(user)
        session.commit()
        login_user(user, remember=True)
        flash("Cuenta creada. ¡Bienvenido!", "success")
        return redirect(url_for("dashboard.index"))
    return render_template("auth/register.html", username="")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current", "")
        new = request.form.get("new", "")
        confirm = request.form.get("confirm", "")
        session = get_session()
        user = session.get(User, current_user.id)
        if user is None or not check_password_hash(user.password_hash, current):
            flash("Contraseña actual incorrecta.", "danger")
            return render_template("auth/change_password.html"), 401
        err = _validate_password(new)
        if not err and new != confirm:
            err = "Las contraseñas nuevas no coinciden."
        if err:
            flash(err, "danger")
            return render_template("auth/change_password.html"), 400
        user.password_hash = generate_password_hash(new)
        session.commit()
        flash("Contraseña actualizada.", "success")
        return redirect(url_for("dashboard.index"))
    return render_template("auth/change_password.html")
