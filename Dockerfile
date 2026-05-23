# Single-stage; tiny enough that multi-stage adds complexity without value.
# Works on both linux/amd64 and linux/arm64 (Oracle Cloud ARM).
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MISCUENTAS_DB=/data/miscuentas.db \
    PORT=8000

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY miscuentas/ ./miscuentas/
COPY seed.py run.py gunicorn.conf.py ./

# Non-root user, owns /data for the SQLite file
RUN useradd --create-home --shell /bin/bash app \
 && mkdir -p /data \
 && chown -R app:app /data /app
USER app

VOLUME ["/data"]
EXPOSE 8000

# Healthcheck: GET /login returns 200 once the app is up.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/login >/dev/null || exit 1

# Run gunicorn directly. The schema is created automatically on first request
# (init_db is idempotent).  For initial seed, run: docker compose run --rm web python seed.py
CMD ["gunicorn", "-c", "gunicorn.conf.py", "miscuentas:create_app()"]
