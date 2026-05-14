"""Idempotent seed: creates the davidabril01 user and loads his situation
as of 2026-05-13.

Idempotency key: meta.seeded_v2 (bumped from v1 since the schema now has users).
"""

from datetime import date, datetime
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from miscuentas.db import init_engine, init_db, get_session
from miscuentas.models import (
    User, Account, Category, RecurringRule, Debt, FxRate, Meta,
)
from miscuentas.money import to_minor, fx_to_micro


SEED_KEY = "seeded_v2"
SEED_DATE = date(2026, 5, 13)

DEFAULT_USERNAME = "davidabril01"
DEFAULT_PASSWORD = "Admin123"


def run(session=None):
    if session is None:
        init_engine()
        init_db()
        session = get_session()
        close_after = True
    else:
        close_after = False
    try:
        existing = session.execute(select(Meta).where(Meta.key == SEED_KEY)).scalar_one_or_none()
        if existing is not None:
            print(f"[seed] Ya estaba cargado en {existing.value}. No hago nada.")
            return

        # 1. Usuario por defecto.
        user = session.execute(
            select(User).where(User.username == DEFAULT_USERNAME)
        ).scalar_one_or_none()
        if user is None:
            user = User(
                username=DEFAULT_USERNAME,
                password_hash=generate_password_hash(DEFAULT_PASSWORD),
            )
            session.add(user)
            session.flush()
        uid = user.id

        # 2. FX rate
        session.add(FxRate(
            user_id=uid,
            effective_on=SEED_DATE,
            rate_to_ars_micro=fx_to_micro("1400"),
            source="manual (seed)",
        ))

        # 3. Categorias
        cats = {
            "Comida":        Category(user_id=uid, name="Comida",        kind="expense"),
            "Suscripciones": Category(user_id=uid, name="Suscripciones", kind="expense"),
            "Servicios":     Category(user_id=uid, name="Servicios",     kind="expense"),
            "Música":        Category(user_id=uid, name="Música",        kind="expense"),
            "Otros gasto":   Category(user_id=uid, name="Otros gasto",   kind="expense"),
            "Sueldo":        Category(user_id=uid, name="Sueldo",        kind="income"),
            "Reintegro":     Category(user_id=uid, name="Reintegro",     kind="income"),
            "Otros ingreso": Category(user_id=uid, name="Otros ingreso", kind="income"),
        }
        for c in cats.values():
            session.add(c)

        # 4. Cuentas
        billetera = Account(
            user_id=uid, name="Billetera virtual", currency="ARS",
            opening_balance_minor=to_minor("694000"),
        )
        cuenta_usd = Account(
            user_id=uid, name="Cuenta USD (conceptual)", currency="USD",
            opening_balance_minor=0,
        )
        efectivo = Account(
            user_id=uid, name="Efectivo", currency="ARS",
            opening_balance_minor=0,
        )
        for a in (billetera, cuenta_usd, efectivo):
            session.add(a)
        session.flush()

        # 5. Deudas (receivables)
        session.add(Debt(
            user_id=uid, counterparty="Orion", direction="receivable",
            principal_minor=to_minor("350000"), currency="ARS",
            opened_on=SEED_DATE, due_on=date(2026, 5, 15),
            notes="Pago pendiente del trabajo",
        ))
        session.add(Debt(
            user_id=uid, counterparty="Padres", direction="receivable",
            principal_minor=to_minor("200"), currency="USD",
            fx_rate_to_ars_micro=fx_to_micro("1400"),
            opened_on=SEED_DATE, due_on=None,
        ))
        session.add(Debt(
            user_id=uid, counterparty="Hermano", direction="receivable",
            principal_minor=to_minor("300"), currency="USD",
            fx_rate_to_ars_micro=fx_to_micro("1400"),
            opened_on=SEED_DATE, due_on=date(2026, 7, 15),
            notes="Paga en julio",
        ))
        # Deudas (payables)
        session.add(Debt(
            user_id=uid, counterparty="Padres", direction="payable",
            principal_minor=to_minor("730000"), currency="ARS",
            opened_on=SEED_DATE, due_on=None,
            notes="Pagar lo antes posible",
        ))

        # 6. Reglas recurrentes (arrancan en junio).
        start = date(2026, 6, 1)
        rules = [
            ("Clases de batería",          "expense", "80000",  "ARS", billetera,  cats["Música"],        10),
            ("Sueldo Orion",                "income",  "500",    "USD", cuenta_usd, cats["Sueldo"],         5),
            ("Claude",                      "expense", "20",     "USD", cuenta_usd, cats["Suscripciones"],  1),
            ("OpenCode",                    "expense", "10",     "USD", cuenta_usd, cats["Suscripciones"],  1),
            ("Servidor",                    "expense", "50",     "USD", cuenta_usd, cats["Servicios"],      1),
            ("Reintegro servidor (Orion)",  "income",  "20",     "USD", cuenta_usd, cats["Reintegro"],      5),
            ("Chatbot universidad",         "income",  "25000",  "ARS", billetera,  cats["Otros ingreso"], 15),
        ]
        for name, kind, amount, currency, acc, category, day in rules:
            session.add(RecurringRule(
                user_id=uid, name=name, kind=kind,
                amount_minor=to_minor(amount), currency=currency,
                account_id=acc.id, category_id=category.id,
                day_of_month=day, start_date=start, end_date=None, active=1,
            ))

        session.add(Meta(key=SEED_KEY, value=datetime.utcnow().isoformat(timespec="seconds")))
        session.commit()
        print(f"[seed] Listo. Usuario: {DEFAULT_USERNAME} / Contraseña: {DEFAULT_PASSWORD}")
    except Exception:
        session.rollback()
        raise
    finally:
        if close_after:
            session.close()


if __name__ == "__main__":
    run()
