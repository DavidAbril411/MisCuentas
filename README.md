# MisCuentas

App web Flask para llevar cuentas personales con multi-moneda ARS/USD,
snapshot del tipo de cambio en cada movimiento, ingresos/gastos recurrentes
mensuales, deudas a cobrar y a pagar, proyección a futuro, y multi-usuario
con autenticación.

## Stack

Python 3.11+ · Flask · Flask-Login · SQLAlchemy 2 · Jinja2 · Bootstrap 5
(CDN) · SQLite (WAL) · python-dateutil · gunicorn · pytest.  Todo el dinero
se guarda como enteros en unidades menores (centavos / cents).

## Correr en local

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python seed.py        # idempotente; crea usuario davidabril01 / Admin123
python run.py         # http://127.0.0.1:5000
pytest -q             # 29 tests
```

Después de logearte, podés cambiar la contraseña desde el menú del usuario.
Otros usuarios se pueden registrar en `/register`.

## Deploy en producción

Ver `DEPLOY.md`.  Stack: gunicorn + Docker tras nginx; SQLite persistente
en un volumen.

## Features

- **Auth**: registro, login, logout, cambio de contraseña.  Hashes PBKDF2
  vía Werkzeug.  Sesiones con Flask-Login (`remember_me`).
- **Multi-tenant**: cada tabla tiene `user_id NOT NULL`; las queries
  filtran por `current_user.id` y triggers SQLite rechazan inserts
  cross-tenant.
- **Currency match**: triggers + checks en rutas que rechazan movimientos /
  reglas cuya moneda no coincide con la de la cuenta.
- **Snapshot FX**: cada fila en USD guarda la cotización del momento;
  editar `fx_rates` no altera filas existentes.
- **Reglas recurrentes**: materializan automáticamente al cargar
  cualquier página (idempotente); borrables; pausables.
- **Pagos de deuda**: una transaction con `debt_id` afecta saldo de cuenta
  y reduce pendiente de deuda en un solo movimiento.

## Estructura

```
miscuentas/
  auth.py             # Flask-Login + login/register/logout/change-password
  schema.sql          # DDL con CHECK + triggers de tenancy y currency
  models.py           # ORM
  money.py            # to_minor / from_minor / convert_to_ars_minor
  fx.py               # current_rate / rate_at / set_rate  (per-user)
  recurring.py        # materialize + project_future_occurrences (per-user)
  metrics.py          # net_worth / monthly_flow / projection (per-user)
  routes/             # dashboard / accounts / transactions / recurring / debts / fx
  templates/
    auth/             # login, register, change_password
    ...
seed.py               # idempotente; usuario davidabril01 + datos
run.py                # entrypoint dev
gunicorn.conf.py      # entrypoint prod
Dockerfile            # multi-arch (ARM64 OK)
docker-compose.yml    # bind 127.0.0.1:5001 → contenedor :8000
deploy/nginx-cuentas.conf
DEPLOY.md             # instrucciones para el devops
tests/                # 29 tests (incluye isolation cross-tenant)
```
