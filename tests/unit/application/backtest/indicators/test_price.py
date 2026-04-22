"""PriceSource extractor: each source reads the expected field."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.backtest.indicators.price import extract_price
from cryptozavr.application.strategy.enums import PriceSource
from tests.unit.application.backtest.indicators.fixtures import candle


def test_open_source() -> None:
    c = candle(0, open_="100", high="110", low="90", close="105")
    assert extract_price(c, PriceSource.OPEN) == Decimal("100")


def test_high_source() -> None:
    c = candle(0, open_="100", high="110", low="90", close="105")
    assert extract_price(c, PriceSource.HIGH) == Decimal("110")


def test_low_source() -> None:
    c = candle(0, open_="100", high="110", low="90", close="105")
    assert extract_price(c, PriceSource.LOW) == Decimal("90")


def test_close_source() -> None:
    c = candle(0, open_="100", high="110", low="90", close="105")
    assert extract_price(c, PriceSource.CLOSE) == Decimal("105")


def test_hlc3_uses_exact_decimal_division() -> None:
    """(high + low + close) / 3. Using Decimal throughout so exact
    arithmetic holds even for prices that would lose float precision."""
    c = candle(0, high="110", low="90", close="100")
    # (110 + 90 + 100) / 3 = 300 / 3 = 100 exactly
    assert extract_price(c, PriceSource.HLC3) == Decimal("100")


def test_hlc3_non_terminating_decimal() -> None:
    """300.1 / 3 is non-terminating; Decimal still produces a deterministic
    finite-digit result (no exception, no float drift)."""
    c = candle(0, high="110", low="90.1", close="100")
    result = extract_price(c, PriceSource.HLC3)
    # 300.1 / 3 ≈ 100.03333...
    assert Decimal("100.033") < result < Decimal("100.034")
