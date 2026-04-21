"""Test SymbolResolver: in-memory fuzzy match against SymbolRegistry."""

import pytest

from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.domain.exceptions import (
    SymbolNotFoundError,
    VenueNotSupportedError,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId


@pytest.fixture
def registry() -> SymbolRegistry:
    reg = SymbolRegistry()
    reg.get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    reg.get(
        VenueId.KUCOIN,
        "ETH",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="ETH-USDT",
    )
    return reg


class TestSymbolResolver:
    def test_exact_native_symbol_resolves_direct(
        self,
        registry: SymbolRegistry,
    ) -> None:
        resolver = SymbolResolver(registry)
        sym = resolver.resolve(user_input="BTC-USDT", venue="kucoin")
        assert sym.native_symbol == "BTC-USDT"

    def test_lowercase_normalised_to_upper(
        self,
        registry: SymbolRegistry,
    ) -> None:
        resolver = SymbolResolver(registry)
        sym = resolver.resolve(user_input="btc-usdt", venue="kucoin")
        assert sym.native_symbol == "BTC-USDT"

    def test_concatenated_form_resolves_via_variants(
        self,
        registry: SymbolRegistry,
    ) -> None:
        resolver = SymbolResolver(registry)
        sym = resolver.resolve(user_input="btcusdt", venue="kucoin")
        assert sym.native_symbol == "BTC-USDT"

    def test_slash_form_resolves_via_variants(
        self,
        registry: SymbolRegistry,
    ) -> None:
        resolver = SymbolResolver(registry)
        sym = resolver.resolve(user_input="BTC/USDT", venue="kucoin")
        assert sym.native_symbol == "BTC-USDT"

    def test_base_only_resolves_with_default_quote(
        self,
        registry: SymbolRegistry,
    ) -> None:
        resolver = SymbolResolver(registry)
        sym = resolver.resolve(user_input="BTC", venue="kucoin")
        assert sym.native_symbol == "BTC-USDT"

    def test_unknown_venue_raises(self, registry: SymbolRegistry) -> None:
        resolver = SymbolResolver(registry)
        with pytest.raises(VenueNotSupportedError):
            resolver.resolve(user_input="BTC-USDT", venue="binance")

    def test_unknown_symbol_raises(self, registry: SymbolRegistry) -> None:
        resolver = SymbolResolver(registry)
        with pytest.raises(SymbolNotFoundError):
            resolver.resolve(user_input="DOGE-USDT", venue="kucoin")
