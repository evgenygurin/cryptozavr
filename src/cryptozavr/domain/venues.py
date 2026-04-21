"""Venue entity: represents an exchange or market-data aggregator."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class VenueId(StrEnum):
    """Stable venue identifier. Used as natural key across the system."""

    KUCOIN = "kucoin"
    COINGECKO = "coingecko"


class VenueKind(StrEnum):
    """High-level classification of the data source."""

    EXCHANGE_CEX = "exchange_cex"
    AGGREGATOR = "aggregator"
    EXCHANGE_DEX = "exchange_dex"


class MarketType(StrEnum):
    """Instrument market type."""

    SPOT = "spot"
    LINEAR_PERP = "linear_perp"
    INVERSE_PERP = "inverse_perp"


class VenueCapability(StrEnum):
    """Capabilities a venue exposes."""

    SPOT_OHLCV = "spot_ohlcv"
    SPOT_ORDERBOOK = "spot_orderbook"
    SPOT_TRADES = "spot_trades"
    SPOT_TICKER = "spot_ticker"
    FUTURES_OHLCV = "futures_ohlcv"
    FUNDING_RATE = "funding_rate"
    OPEN_INTEREST = "open_interest"
    MARKET_CAP_RANK = "market_cap_rank"
    CATEGORY_DATA = "category_data"


class VenueStateKind(StrEnum):
    """Operational state of a venue (runtime, updated by L2)."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    RATE_LIMITED = "rate_limited"
    DOWN = "down"


@dataclass(frozen=True, slots=True, eq=False)
class Venue:
    """Identity = `id`. Equality and hashing ignore dynamic state/capabilities."""

    id: VenueId
    kind: VenueKind
    capabilities: frozenset[VenueCapability]
    state: VenueStateKind = VenueStateKind.HEALTHY

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Venue):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
