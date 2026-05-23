"""Gunicorn config for MisCuentas. Single-process, threaded — SQLite likes that."""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
# Single worker + threads: SQLite handles concurrency via WAL but multi-process
# writers cause "database is locked" errors. Threaded model avoids that.
workers = 1
threads = int(os.environ.get("GUNICORN_THREADS", "8"))
worker_class = "gthread"
timeout = 60
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
# Behind nginx terminating TLS:
forwarded_allow_ips = "*"
secure_scheme_headers = {"X-Forwarded-Proto": "https"}
