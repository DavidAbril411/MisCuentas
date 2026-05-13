"""FX rate access. ARS-per-USD stored as integer micro (rate * 1_000_000)."""

from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import FxRate
from .money import fx_to_micro


def current_rate_micro(session: Session) -> int:
    """Most recent FX rate. Raises if none exists."""
    row = session.execute(
        select(FxRate).order_by(FxRate.effective_on.desc()).limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise RuntimeError(
            "No FX rate found. Add one at /fx/new or run seed.py."
        )
    return row.rate_to_ars_micro


def rate_at_micro(session: Session, on: date) -> int:
    """Rate on `on`, using nearest-on-or-before. Falls back to nearest-after if
    none exist on/before (e.g. a date earlier than any recorded rate)."""
    row = session.execute(
        select(FxRate)
        .where(FxRate.effective_on <= on)
        .order_by(FxRate.effective_on.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is not None:
        return row.rate_to_ars_micro
    row = session.execute(
        select(FxRate).order_by(FxRate.effective_on.asc()).limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise RuntimeError(
            "No FX rate found. Add one at /fx/new or run seed.py."
        )
    return row.rate_to_ars_micro


def set_rate(session: Session, on: date, rate_decimal, source: str | None = None) -> FxRate:
    """Upsert an FX rate for a given date."""
    micro = fx_to_micro(rate_decimal)
    row = session.execute(
        select(FxRate).where(FxRate.effective_on == on)
    ).scalar_one_or_none()
    if row is None:
        row = FxRate(effective_on=on, rate_to_ars_micro=micro, source=source)
        session.add(row)
    else:
        row.rate_to_ars_micro = micro
        if source is not None:
            row.source = source
    return row
