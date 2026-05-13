"""Money helpers. All money is integer minor units (centavos/cents).
FX rate is integer micro-ARS per 1 USD (rate_ARS_per_USD * 1_000_000)."""

from decimal import Decimal, ROUND_HALF_UP

MICRO = 1_000_000
MINOR_PER_UNIT = 100  # both ARS centavos and USD cents


def to_minor(amount) -> int:
    """Parse a user-entered amount (str/Decimal/int/float) into integer minor units.
    Rounds half-up to the nearest minor unit. Never returns a float."""
    if isinstance(amount, int):
        return amount * MINOR_PER_UNIT
    d = Decimal(str(amount))
    q = (d * MINOR_PER_UNIT).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(q)


def from_minor(minor: int) -> Decimal:
    """Convert integer minor units to a Decimal with 2 decimal places."""
    return (Decimal(minor) / MINOR_PER_UNIT).quantize(Decimal("0.01"))


def fx_to_micro(rate) -> int:
    """Parse an ARS-per-USD rate into integer micro-ARS-per-USD."""
    d = Decimal(str(rate))
    q = (d * MICRO).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(q)


def fx_from_micro(micro: int) -> Decimal:
    """Convert integer micro-ARS-per-USD to a Decimal rate."""
    return (Decimal(micro) / MICRO).quantize(Decimal("0.000001"))


def convert_to_ars_minor(amount_minor: int, currency: str, rate_micro: int | None) -> int:
    """Return amount in ARS minor units. For USD, uses given rate_micro snapshot.
    Sub-centavo precision is truncated (acceptable for display)."""
    if currency == "ARS":
        return amount_minor
    if currency == "USD":
        if rate_micro is None:
            raise ValueError("USD amount requires an FX rate")
        return amount_minor * rate_micro // MICRO
    raise ValueError(f"Unknown currency: {currency}")


def format_money(minor: int, currency: str) -> str:
    """Human-friendly amount with thousand separators (Spanish style: 1.234,56)."""
    d = from_minor(minor)
    sign = "-" if d < 0 else ""
    d = abs(d)
    int_part, _, dec_part = f"{d:.2f}".partition(".")
    int_with_sep = "{:,}".format(int(int_part)).replace(",", ".")
    symbol = "$" if currency == "ARS" else "US$"
    return f"{sign}{symbol} {int_with_sep},{dec_part}"
