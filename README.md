# MisCuentas

App web local para llevar cuentas personales con SQLite, multi-moneda ARS/USD,
con snapshot del tipo de cambio en cada movimiento o deuda, ingresos y gastos
recurrentes mensuales, deudas a cobrar y a pagar, y proyección a futuro.

## Stack

Python 3.11+ · Flask · SQLAlchemy 2 · Jinja2 · Bootstrap 5 (CDN) · SQLite ·
python-dateutil · pytest. Toda la plata se guarda como enteros en unidades
menores (centavos / cents). El FX se guarda como entero micro-ARS por 1 USD.

## Cómo correrlo

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python seed.py        # crea miscuentas.db con tu situación inicial (idempotente)
python run.py         # http://127.0.0.1:5000
pytest -q             # tests con DB in-memory
```

La app sólo escucha en `127.0.0.1`. No tiene auth: es para uso local.

## Datos iniciales (al 13-may-2026)

- Billetera virtual: 694.000 ARS
- A cobrar: Orion 350.000 ARS (15-may), Padres 200 USD, Hermano 300 USD (15-jul)
- A pagar: Padres 730.000 ARS
- Cotización: 1 USD = 1.400 ARS
- Reglas mensuales:
  - Gasto ARS 80.000 (clases de batería, día 10)
  - Ingreso USD 500 (sueldo Orion, día 5)
  - Gasto USD 20 / 10 / 50 (Claude / OpenCode / servidor, día 1)
  - Ingreso USD 20 (reintegro servidor Orion, día 5)
  - Ingreso ARS 25.000 (chatbot universidad, día 15)

## Conceptos

- **Snapshot FX**: cada fila en USD (`transactions`, `debts`) guarda la
  cotización al momento de su creación. Editar el historial de `fx_rates` NO
  altera los snapshots de filas existentes — sólo afecta nuevos cálculos.
- **Materialización**: las reglas recurrentes son plantillas. Al abrir
  cualquier página la app genera las transacciones pendientes hasta hoy
  (idempotente). Las del futuro se ven en la proyección sin escribirse en la
  DB.
- **Pago de deuda**: cuando registrás un pago contra una deuda, se crea una
  fila en `transactions` con `debt_id` apuntando a la deuda. Eso afecta el
  saldo de la cuenta y reduce el pendiente de la deuda en un solo movimiento.

## Estructura

```
miscuentas/
  schema.sql        DDL con CHECK constraints (USD requiere FX, ARS lo prohibe)
  models.py         ORM
  money.py          to_minor / from_minor / convert_to_ars_minor
  fx.py             current_rate / rate_at / set_rate
  recurring.py      materialize + project_future_occurrences
  metrics.py        net_worth / monthly_flow / projection
  routes/           dashboard, accounts, transactions, recurring, debts, fx
  templates/        Jinja + Bootstrap
seed.py             idempotente
run.py              python run.py
tests/              16 tests, pytest
```

## Decisiones

- Día del mes capado a 1–28 en reglas recurrentes (evita febrero).
- FX para fechas pasadas: nearest-on-or-before, fallback a la primera registrada.
- La proyección a futuro asume el dólar constante (al valor actual).
- Deudas sin fecha de vencimiento se asignan al primer bucket en la proyección.
