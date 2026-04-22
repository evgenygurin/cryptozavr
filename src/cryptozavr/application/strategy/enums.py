"""Strategy-layer enums. Values are the wire contract across MCP + Supabase;
names never change, values are lowercase-snake for JSON cleanliness."""

from __future__ import annotations

from enum import StrEnum


class StrategySide(StrEnum):
    LONG = "long"
    SHORT = "short"


class IndicatorKind(StrEnum):
    SMA = "sma"
    EMA = "ema"
    RSI = "rsi"
    MACD = "macd"
    ATR = "atr"
    VOLUME = "volume"


class ComparatorOp(StrEnum):
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"


class PriceSource(StrEnum):
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    HLC3 = "hlc3"
