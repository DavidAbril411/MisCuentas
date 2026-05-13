"""Idempotent seed: loads the user's situation as of 2026-05-13."""

from datetime import date, datetime
from sqlalchemy import select

from miscuentas.db import init_engine, init_db, get_session
from miscuentas.models import (
    Account, Category, RecurringRule, Debt, FxRate, Meta,
)
from miscuentas.money import to_minor, fx_to_micro


SEED_KEY = "seeded_v1"
SEED_DATE = date(2026, 5, 13)


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

        # 1. FX rate
        session.add(FxRate(
            effective_on=SEED_DATE,
            rate_to_ars_micro=fx_to_micro("1400"),
            source="manual (seed)",
        ))

        # 2. Categorias base
        cats = {
            "Comida":        Category(name="Comida",        kind="expense"),
            "Suscripciones": Category(name="Suscripciones", kind="expense"),
            "Servicios":     Category(name="Servicios",     kind="expense"),
            "Música":        Category(name="Música",        kind="expense"),
            "Otros gasto":   Category(name="Otros gasto",   kind="expense"),
            "Sueldo":        Category(name="Sueldo",        kind="income"),
            "Reintegro":     Category(name="Reintegro",     kind="income"),
            "Otros ingreso": Category(name="Otros ingreso", kind="income"),
        }
        for c in cats.values():
            session.add(c)

        # 3. Cuentas
        billetera = Account(
            name="Billetera virtual",
            currency="ARS",
            opening_balance_minor=to_minor("694000"),
        )
        cuenta_usd = Account(
            name="Cuenta USD (conceptual)",
            currency="USD",
            opening_balance_minor=0,
        )
        session.add(billetera)
        session.add(cuenta_usd)
        session.flush()

        # 4. Deudas (receivables)
        session.add(Debt(
            counterparty="Orion",
            direction="receivable",
            principal_minor=to_minor("350000"),
            currency="ARS",
            opened_on=SEED_DATE,
            due_on=date(2026, 5, 15),
            notes="Pago pendiente del trabajo",
        ))
        session.add(Debt(
            counterparty="Padres",
            direction="receivable",
            principal_minor=to_minor("200"),
            currency="USD",
            fx_rate_to_ars_micro=fx_to_micro("1400"),
            opened_on=SEED_DATE,
            due_on=None,
        ))
        session.add(Debt(
            counterparty="Hermano",
            direction="receivable",
            principal_minor=to_minor("300"),
            currency="USD",
            fx_rate_to_ars_micro=fx_to_micro("1400"),
            opened_on=SEED_DATE,
            due_on=date(2026, 7, 15),
            notes="Paga en julio",
        ))
        # Deudas (payables)
        session.add(Debt(
            counterparty="Padres",
            direction="payable",
            principal_minor=to_minor("730000"),
            currency="ARS",
            opened_on=SEED_DATE,
            due_on=None,
            notes="Pagar lo antes posible",
        ))

        # 5. Reglas recurrentes (arrancan en junio: mayo ya está reflejado
        # en el saldo actual de la billetera).
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
                name=name,
                kind=kind,
                amount_minor=to_minor(amount),
                currency=currency,
                account_id=acc.id,
                category_id=category.id,
                day_of_month=day,
                start_date=start,
                end_date=None,
                active=1,
            ))

        session.add(Meta(key=SEED_KEY, value=datetime.utcnow().isoformat(timespec="seconds")))
        session.commit()
        print("[seed] Datos iniciales cargados.")
    except Exception:
        session.rollback()
        raise
    finally:
        if close_after:
            session.close()


if __name__ == "__main__":
    run()
