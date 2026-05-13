import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_DB_PATH = BASE_DIR / "miscuentas.db"


class Config:
    DB_PATH = os.environ.get("MISCUENTAS_DB", str(DEFAULT_DB_PATH))
    SQLALCHEMY_URL = f"sqlite:///{DB_PATH}"
    SECRET_KEY = os.environ.get("MISCUENTAS_SECRET", "dev-secret-local-only")
    PROJECTION_MONTHS = int(os.environ.get("MISCUENTAS_PROJECTION_MONTHS", "12"))
