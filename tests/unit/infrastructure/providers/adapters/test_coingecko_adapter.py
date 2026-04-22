"""Test CoinGeckoAdapter pure functions on saved fixtures."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.adapters.coingecko_adapter import (
    CoinGeckoAdapter,
)

FIXTURE_DIR = Path(__file__).resolve().parents[4] / "contract" / "fixtures" / "coingecko"


@pytest.fixture
def registry() -> SymbolRegistry:
    return SymbolRegistry()


@pytest.fixture
def btc_symbol(registry: SymbolRegistry):
    return registry.get(
        VenueId.COINGECKO,
        "BTC",
        "USD",
        market_type=MarketType.SPOT,
        native_symbol="bitcoin",
    )


class TestSimplePriceToTicker:
    def test_happy_path(self, btc_symbol) -> None:
        raw = json.loads((FIXTURE_DIR / "simple_price_btc.json").read_text())
        ticker = CoinGeckoAdapter.simple_price_to_ticker(
            raw,
            coin_id="bitcoin",
            vs_currency="usd",
            symbol=btc_symbol,
        )
        assert ticker.last == Decimal("65000.5")
        assert ticker.volume_24h == Decimal("45230000000.0")
        assert ticker.change_24h_pct is not None
        assert ticker.change_24h_pct.value == Decimal("2.5")
        assert ticker.quality.source.venue_id == "coingecko"
        assert ticker.quality.source.endpoint == "simple_price"

    def test_missing_coin_raises(self, btc_symbol) -> None:
        with pytest.raises(KeyError):
            CoinGeckoAdapter.simple_price_to_ticker(
                {},
                coin_id="bitcoin",
                vs_currency="usd",
                symbol=btc_symbol,
            )


class TestTrendingToAssets:
    def test_happy_path(self) -> None:
        raw = json.loads((FIXTURE_DIR / "trending.json").read_text())
        assets = CoinGeckoAdapter.trending_to_assets(raw)
        assert len(assets) == 3
        assert assets[0].code == "BTC"
        assert assets[0].name == "Bitcoin"
        assert assets[0].coingecko_id == "bitcoin"
        assert assets[0].market_cap_rank == 1


class TestCategoriesToList:
    def test_happy_path(self) -> None:
        raw = json.loads((FIXTURE_DIR / "categories.json").read_text())
        cats = CoinGeckoAdapter.categories_to_list(raw)
        assert len(cats) == 3
        assert cats[0]["id"] == "layer-1"
        assert cats[0]["market_cap"] == 1500000000000

    def test_maps_id_to_category_id_for_dto_compat(self) -> None:
        """CoinGecko /coins/categories returns `id`; DTO wants `category_id`."""
        raw = [{"id": "layer-1", "name": "L1", "market_cap": 1, "market_cap_change_24h": 0.5}]
        cats = CoinGeckoAdapter.categories_to_list(raw)
        assert cats[0]["category_id"] == "layer-1"
        assert cats[0]["id"] == "layer-1"  # original left intact

    def test_preserves_existing_category_id(self) -> None:
        """If upstream already supplies category_id, do not clobber it."""
        raw = [{"category_id": "legacy", "id": "new", "name": "X"}]
        cats = CoinGeckoAdapter.categories_to_list(raw)
        assert cats[0]["category_id"] == "legacy"
