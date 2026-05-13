from decimal import Decimal
from miscuentas.money import to_minor, from_minor, fx_to_micro, fx_from_micro, convert_to_ars_minor


def test_to_minor_string_int_decimal():
    assert to_minor("694000") == 69_400_000
    assert to_minor("694000.00") == 69_400_000
    assert to_minor("694000.50") == 69_400_050
    assert to_minor(694000) == 69_400_000
    assert to_minor(Decimal("694000.123")) == 69_400_012  # half-up


def test_from_minor_roundtrip():
    assert from_minor(69_400_000) == Decimal("694000.00")
    assert from_minor(1) == Decimal("0.01")


def test_fx_micro_roundtrip():
    assert fx_to_micro("1400") == 1_400_000_000
    assert fx_to_micro("1400.5") == 1_400_500_000
    assert fx_from_micro(1_400_000_000) == Decimal("1400.000000")


def test_convert_to_ars():
    # 500 USD at rate 1400 -> 700_000 ARS
    assert convert_to_ars_minor(500 * 100, "USD", fx_to_micro("1400")) == 700_000 * 100
    # ARS passes through unchanged
    assert convert_to_ars_minor(80_000_00, "ARS", None) == 80_000_00
