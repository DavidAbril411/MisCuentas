"""FX rate access (per-user). ARS-per-USD stored as integer micro."""

from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import FxRate
from .money import fx_to_micro


def current_rate_micro(session: Session, user_id: int) -> int:
    row = session.execute(
        select(FxRate)
        .where(FxRate.user_id == user_id)
        .order_by(FxRate.effective_on.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise RuntimeError(
            "No FX rate found. Add one at /fx/new."
        )
    return row.rate_to_ars_micro


def rate_at_micro(session: Session, user_id: int, on: date) -> int:
    """Rate on `on`, nearest-on-or-before; fallback to nearest-after."""
    row = session.execute(
        select(FxRate)
        .where(FxRate.user_id == user_id, FxRate.effective_on <= on)
        .order_by(FxRate.effective_on.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is not None:
        return row.rate_to_ars_micro
    row = session.execute(
        select(FxRate)
        .where(FxRate.user_id == user_id)
        .order_by(FxRate.effective_on.asc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise RuntimeError("No FX rate found.")
    return row.rate_to_ars_micro


def set_rate(session: Session, user_id: int, on: date, rate_decimal, source: str | None = None) -> FxRate:
    micro = fx_to_micro(rate_decimal)
    row = session.execute(
        select(FxRate).where(FxRate.user_id == user_id, FxRate.effective_on == on)
    ).scalar_one_or_none()
    if row is None:
        row = FxRate(user_id=user_id, effective_on=on, rate_to_ars_micro=micro, source=source)
        session.add(row)
    else:
        row.rate_to_ars_micro = micro
        if source is not None:
            row.source = source
    return row
