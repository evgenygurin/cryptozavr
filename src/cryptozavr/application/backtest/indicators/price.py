"""PriceSource → Decimal extractor.

HLC3 uses exact Decimal division (no float precision loss)."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.strategy.enums import PriceSource
from cryptozavr.domain.market_data import OHLCVCandle

_THREE = Decimal("3")


def extract_price(candle: OHLCVCandle, source: PriceSource) -> Decimal:
    match source:
        case PriceSource.OPEN:
            return candle.open
        case PriceSource.HIGH:
            return candle.high
        case PriceSource.LOW:
            return candle.low
        case PriceSource.CLOSE:
            return candle.close
        case PriceSource.HLC3:
            return (candle.high + candle.low + candle.close) / _THREE
