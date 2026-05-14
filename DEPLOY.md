# Deploy de MisCuentas en el server de Cappy

Pequeña app web Flask para llevar cuentas personales (proyecto académico).
Va a quedar en `https://cuentas.abrilcodes.com`.

## Pedido para el devops de Cappy

Hola — necesito desplegar otra app en el server de Cappy
(`146.181.52.67`, Oracle Cloud sa-santiago-1).  No comparte código ni DB con
Cappy, sólo el reverse proxy nginx y el certificate manager.  Es para uso
personal/académico, escala chica (≤10 usuarios).  Tengo el código en
`https://github.com/davidabril411/MisCuentas` (rama
`claude/accounting-app-sqlite-6FkOq`).

**DNS**: yo agrego `cuentas.abrilcodes.com → 146.181.52.67` antes de que
emitamos el cert.

**Lo que necesito que hagas en el server**:

1. Emitir cert Let's Encrypt para `cuentas.abrilcodes.com`:
   ```bash
   sudo certbot certonly --webroot -w /var/www/letsencrypt -d cuentas.abrilcodes.com
   ```

2. Levantar el contenedor.  El repo trae todo: `Dockerfile`, `docker-compose.yml`, `gunicorn.conf.py`.
   ```bash
   sudo mkdir -p /srv/miscuentas && sudo chown $USER /srv/miscuentas
   cd /srv/miscuentas
   git clone https://github.com/davidabril411/MisCuentas.git .
   git checkout claude/accounting-app-sqlite-6FkOq
   echo "MISCUENTAS_SECRET=$(openssl rand -hex 32)" > .env
   docker compose up -d --build
   # Carga inicial con los datos de davidabril01:
   docker compose run --rm miscuentas python seed.py
   ```
   El contenedor escucha en `127.0.0.1:5001` (sólo loopback).

3. Reverse proxy de nginx — copio el vhost listo en `deploy/nginx-cuentas.conf` del repo:
   ```bash
   sudo cp /srv/miscuentas/deploy/nginx-cuentas.conf /etc/nginx/sites-available/cuentas.abrilcodes.com
   sudo ln -s /etc/nginx/sites-available/cuentas.abrilcodes.com /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   ```
   Usa el mismo `options-ssl-nginx.conf` y `ssl-dhparams.pem` que Cappy.

Cuando esté arriba, `https://cuentas.abrilcodes.com/login` debería responder 200.
El usuario inicial es `davidabril01` / `Admin123` (cambio la pass después del primer login).

**Cosas que **no** necesito**: ni Postgres, ni Redis, ni cron, ni mail.  La
app guarda todo en un SQLite dentro del volumen Docker `miscuentas_data`
(montado en `/data` adentro del contenedor).

**Backups**: cada tanto `docker compose cp miscuentas:/data/miscuentas.db ./backup-$(date +%F).db` y guardás el archivo.  Es lo único persistente.

Gracias!

---

## Stack & decisiones (para referencia)

- **DB**: SQLite con WAL.  Escala perfectamente para esta carga (1-10 users,
  pocos writes), no requiere infra adicional, backup = `cp`.
- **Server WSGI**: gunicorn con 1 worker + 8 threads (gthread).  SQLite no
  tolera bien múltiples writers; threads en un solo proceso evitan
  "database is locked".
- **Container**: Python 3.12 slim, multi-arch (corre en ARM64 del Oracle
  Cloud y en x86 local).
- **Reverse proxy**: nginx en el host, TLS termination ahí.  Match con el
  setup de Cappy (loopback-only binds, headers de seguridad explícitos).
- **Auth**: Flask-Login + Werkzeug PBKDF2 (incluido en stdlib de Flask
  ecosystem).  Sin OAuth, sin email — username/password local.  Hay
  registro abierto: el dueño del server puede limitarlo cerrando la ruta
  `/register` si hiciera falta.
- **Tenancy**: cada tabla tiene `user_id NOT NULL`; triggers SQLite
  rechazan inserts cross-tenant.  Test de aislamiento en
  `tests/test_routes.py::test_users_cannot_see_each_others_data`.
- **Validación**: triggers + checks en routes para `currency match`
  (moneda del movimiento ↔ moneda de la cuenta).
