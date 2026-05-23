from datetime import date
from flask import Flask, g

from .config import Config
from .db import init_engine, init_db, get_session, shutdown_session
from .recurring import materialize_recurring
from .money import format_money, from_minor, convert_to_ars_minor


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)
    app.secret_key = app.config.get("SECRET_KEY", "dev")

    url = app.config.get("SQLALCHEMY_URL", Config.SQLALCHEMY_URL)
    init_engine(url)
    init_db()

    @app.before_request
    def _before_request():
        g.session = get_session()
        if not app.config.get("DISABLE_AUTO_MATERIALIZE"):
            try:
                materialize_recurring(g.session, date.today())
                g.session.commit()
            except Exception:
                g.session.rollback()

    @app.teardown_request
    def _teardown(exc):
        try:
            if exc is not None:
                g.session.rollback()
        finally:
            shutdown_session()

    # Jinja filters
    app.jinja_env.filters["money"] = format_money
    app.jinja_env.filters["ars"] = lambda m: format_money(m, "ARS")
    app.jinja_env.filters["decimal"] = from_minor

    from .routes.dashboard import bp as dashboard_bp
    from .routes.accounts import bp as accounts_bp
    from .routes.transactions import bp as transactions_bp
    from .routes.recurring import bp as recurring_bp
    from .routes.debts import bp as debts_bp
    from .routes.fx import bp as fx_bp
    from .routes.mensual import bp as mensual_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(accounts_bp, url_prefix="/accounts")
    app.register_blueprint(transactions_bp, url_prefix="/transactions")
    app.register_blueprint(recurring_bp, url_prefix="/recurring")
    app.register_blueprint(debts_bp, url_prefix="/debts")
    app.register_blueprint(fx_bp, url_prefix="/fx")
    app.register_blueprint(mensual_bp, url_prefix="/mensual")

    return app
