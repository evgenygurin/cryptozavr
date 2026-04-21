"""Test Symbol + SymbolRegistry Flyweight."""

from __future__ import annotations

import asyncio

import pytest

from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId


class TestSymbol:
    def test_happy_path(self) -> None:
        s = Symbol(
            venue=VenueId.KUCOIN,
            base="BTC",
            quote="USDT",
            market_type=MarketType.SPOT,
            native_symbol="BTC-USDT",
        )
        assert s.base == "BTC"
        assert s.quote == "USDT"
        assert s.venue == VenueId.KUCOIN

    def test_rejects_lowercase_base(self) -> None:
        with pytest.raises(ValidationError):
            Symbol(
                venue=VenueId.KUCOIN,
                base="btc",
                quote="USDT",
                market_type=MarketType.SPOT,
                native_symbol="BTC-USDT",
            )

    def test_equality_by_tuple(self) -> None:
        a = Symbol(
            venue=VenueId.KUCOIN,
            base="BTC",
            quote="USDT",
            market_type=MarketType.SPOT,
            native_symbol="BTC-USDT",
        )
        b = Symbol(
            venue=VenueId.KUCOIN,
            base="BTC",
            quote="USDT",
            market_type=MarketType.SPOT,
            native_symbol="BTC/USDT",
        )
        assert a == b
        assert hash(a) == hash(b)


class TestSymbolRegistry:
    def test_get_returns_shared_instance(self) -> None:
        registry = SymbolRegistry()
        a = registry.get(
            VenueId.KUCOIN,
            "BTC",
            "USDT",
            market_type=MarketType.SPOT,
            native_symbol="BTC-USDT",
        )
        b = registry.get(
            VenueId.KUCOIN,
            "BTC",
            "USDT",
            market_type=MarketType.SPOT,
            native_symbol="BTC-USDT",
        )
        assert a is b

    def test_different_venue_produces_different_instance(self) -> None:
        registry = SymbolRegistry()
        a = registry.get(
            VenueId.KUCOIN,
            "BTC",
            "USDT",
            market_type=MarketType.SPOT,
            native_symbol="BTC-USDT",
        )
        b = registry.get(
            VenueId.COINGECKO,
            "BTC",
            "USDT",
            market_type=MarketType.SPOT,
            native_symbol="bitcoin",
        )
        assert a is not b

    def test_find_returns_registered(self) -> None:
        registry = SymbolRegistry()
        s = registry.get(
            VenueId.KUCOIN,
            "BTC",
            "USDT",
            market_type=MarketType.SPOT,
            native_symbol="BTC-USDT",
        )
        assert registry.find(VenueId.KUCOIN, "BTC-USDT") is s
        assert registry.find(VenueId.KUCOIN, "MISSING") is None

    def test_find_by_base(self) -> None:
        registry = SymbolRegistry()
        s = registry.get(
            VenueId.KUCOIN,
            "ETH",
            "USDT",
            market_type=MarketType.SPOT,
            native_symbol="ETH-USDT",
        )
        assert registry.find_by_base(VenueId.KUCOIN, "ETH", quote="USDT") is s
        assert registry.find_by_base(VenueId.KUCOIN, "ETH", quote="BTC") is None

    @pytest.mark.asyncio
    async def test_concurrent_get_yields_same_instance(self) -> None:
        registry = SymbolRegistry()

        async def fetch() -> Symbol:
            return registry.get(
                VenueId.KUCOIN,
                "BTC",
                "USDT",
                market_type=MarketType.SPOT,
                native_symbol="BTC-USDT",
            )

        results = await asyncio.gather(*(fetch() for _ in range(100)))
        first = results[0]
        assert all(s is first for s in results)
