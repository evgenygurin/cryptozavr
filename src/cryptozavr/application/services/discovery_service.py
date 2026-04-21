"""DiscoveryService — thin L4 facade over CoinGecko list_trending/list_categories."""

from typing import Any

from cryptozavr.domain.assets import Asset


class DiscoveryService:
    """Fetches trending + categories from the CoinGecko provider.

    No cache, no decoration — the CoinGecko provider itself sits behind
    the factory-wrapped decorator chain (Retry/RateLimit/Caching/Logging).
    """

    def __init__(self, *, coingecko: Any) -> None:
        self._coingecko = coingecko

    async def list_trending(self, *, limit: int = 15) -> list[Asset]:
        result: list[Asset] = await self._coingecko.list_trending(limit=limit)
        return result

    async def list_categories(
        self,
        *,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await self._coingecko.list_categories(limit=limit)
        return result
