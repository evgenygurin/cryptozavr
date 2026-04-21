"""Test DiscoveryService: thin wrapper over CoinGeckoProvider."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.application.services.discovery_service import DiscoveryService
from cryptozavr.domain.assets import Asset, AssetCategory


@pytest.fixture
def coingecko_provider():
    provider = MagicMock()
    provider.list_trending = AsyncMock(
        return_value=[
            Asset(
                code="BTC",
                name="Bitcoin",
                coingecko_id="bitcoin",
                market_cap_rank=1,
                categories=(AssetCategory.LAYER_1,),
            ),
            Asset(
                code="PEPE",
                name="Pepe",
                coingecko_id="pepe",
                market_cap_rank=30,
                categories=(AssetCategory.MEME,),
            ),
        ],
    )
    provider.list_categories = AsyncMock(
        return_value=[
            {
                "category_id": "layer-1",
                "name": "Layer 1",
                "market_cap": 1_500_000_000,
                "market_cap_change_24h": 2.0,
            },
            {
                "category_id": "meme",
                "name": "Meme",
                "market_cap": 50_000_000,
                "market_cap_change_24h": -3.0,
            },
        ],
    )
    return provider


class TestDiscoveryService:
    @pytest.mark.asyncio
    async def test_list_trending_returns_assets(self, coingecko_provider) -> None:
        service = DiscoveryService(coingecko=coingecko_provider)
        assets = await service.list_trending(limit=2)
        assert len(assets) == 2
        assert assets[0].code == "BTC"
        coingecko_provider.list_trending.assert_awaited_once_with(limit=2)

    @pytest.mark.asyncio
    async def test_list_categories_returns_raw_dicts(
        self,
        coingecko_provider,
    ) -> None:
        service = DiscoveryService(coingecko=coingecko_provider)
        cats = await service.list_categories(limit=2)
        assert len(cats) == 2
        assert cats[0]["category_id"] == "layer-1"
        coingecko_provider.list_categories.assert_awaited_once_with(limit=2)

    @pytest.mark.asyncio
    async def test_default_limits_applied(self, coingecko_provider) -> None:
        service = DiscoveryService(coingecko=coingecko_provider)
        await service.list_trending()
        await service.list_categories()
        coingecko_provider.list_trending.assert_awaited_with(limit=15)
        coingecko_provider.list_categories.assert_awaited_with(limit=30)
