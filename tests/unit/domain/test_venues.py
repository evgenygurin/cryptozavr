"""Test Venue and its enums."""

from __future__ import annotations

from cryptozavr.domain.venues import (
    MarketType,
    Venue,
    VenueCapability,
    VenueId,
    VenueKind,
    VenueStateKind,
)


class TestVenueId:
    def test_values(self) -> None:
        assert VenueId.KUCOIN.value == "kucoin"
        assert VenueId.COINGECKO.value == "coingecko"


class TestVenueKind:
    def test_values(self) -> None:
        assert VenueKind.EXCHANGE_CEX.value == "exchange_cex"
        assert VenueKind.AGGREGATOR.value == "aggregator"
        assert VenueKind.EXCHANGE_DEX.value == "exchange_dex"


class TestMarketType:
    def test_values(self) -> None:
        assert MarketType.SPOT.value == "spot"
        assert MarketType.LINEAR_PERP.value == "linear_perp"
        assert MarketType.INVERSE_PERP.value == "inverse_perp"


class TestVenueCapability:
    def test_values_include_all_mvp_caps(self) -> None:
        expected = {
            "spot_ohlcv",
            "spot_orderbook",
            "spot_trades",
            "spot_ticker",
            "futures_ohlcv",
            "funding_rate",
            "open_interest",
            "market_cap_rank",
            "category_data",
        }
        values = {c.value for c in VenueCapability}
        assert expected.issubset(values)


class TestVenueStateKind:
    def test_values(self) -> None:
        assert VenueStateKind.HEALTHY.value == "healthy"
        assert VenueStateKind.DEGRADED.value == "degraded"
        assert VenueStateKind.RATE_LIMITED.value == "rate_limited"
        assert VenueStateKind.DOWN.value == "down"


class TestVenue:
    def test_happy_path(self) -> None:
        v = Venue(
            id=VenueId.KUCOIN,
            kind=VenueKind.EXCHANGE_CEX,
            capabilities=frozenset({VenueCapability.SPOT_OHLCV, VenueCapability.SPOT_TICKER}),
            state=VenueStateKind.HEALTHY,
        )
        assert v.id == VenueId.KUCOIN
        assert VenueCapability.SPOT_OHLCV in v.capabilities
        assert v.state == VenueStateKind.HEALTHY

    def test_equality_by_id(self) -> None:
        a = Venue(
            id=VenueId.KUCOIN,
            kind=VenueKind.EXCHANGE_CEX,
            capabilities=frozenset({VenueCapability.SPOT_TICKER}),
            state=VenueStateKind.HEALTHY,
        )
        b = Venue(
            id=VenueId.KUCOIN,
            kind=VenueKind.EXCHANGE_CEX,
            capabilities=frozenset({VenueCapability.SPOT_OHLCV}),
            state=VenueStateKind.DEGRADED,
        )
        assert a == b
        assert hash(a) == hash(b)
