"""CoinGeckoProvider: BaseProvider subclass using httpx + HttpClientRegistry."""

from __future__ import annotations

from typing import Any

import httpx

from cryptozavr.domain.assets import Asset
from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    RateLimitExceededError,
)
from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.providers.adapters.coingecko_adapter import (
    CoinGeckoAdapter,
)
from cryptozavr.infrastructure.providers.base import BaseProvider
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

_HTTP_RATE_LIMIT = 429
_HTTP_SERVER_ERROR_MIN = 500


class CoinGeckoProvider(BaseProvider):
    """CoinGecko REST provider.

    Aggregator, not an exchange — only ticker/trending/categories supported.
    OHLCV/orderbook/trades inherit NotImplementedError defaults from BaseProvider.
    """

    def __init__(
        self,
        *,
        state: VenueState,
        client: httpx.AsyncClient,
    ) -> None:
        super().__init__(venue_id=VenueId.COINGECKO, state=state)
        self._client = client

    async def _ensure_markets_loaded(self) -> None:
        """No-op. CoinGecko has no 'markets' in CEX sense."""
        return None

    async def _fetch_ticker_raw(self, symbol: Symbol) -> Any:
        coin_id = symbol.native_symbol
        vs = symbol.quote.lower()
        response = await self._client.get(
            "/simple/price",
            params={
                "ids": coin_id,
                "vs_currencies": vs,
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_last_updated_at": "true",
            },
        )
        self._raise_for_status(response)
        return response.json()

    def _normalize_ticker(self, raw: Any, symbol: Symbol) -> Ticker:
        return CoinGeckoAdapter.simple_price_to_ticker(
            raw,
            coin_id=symbol.native_symbol,
            vs_currency=symbol.quote.lower(),
            symbol=symbol,
        )

    def _translate_exception(self, exc: Exception) -> Exception:
        if isinstance(exc, httpx.ConnectError | httpx.TimeoutException):
            return ProviderUnavailableError(str(exc))
        return exc

    async def list_trending(self, *, limit: int = 15) -> list[Asset]:
        """/search/trending → list[Asset]."""
        self._state.require_operational()
        try:
            response = await self._client.get("/search/trending")
            self._raise_for_status(response)
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        assets = CoinGeckoAdapter.trending_to_assets(response.json())
        return assets[:limit]

    async def list_categories(self, *, limit: int = 30) -> list[dict[str, Any]]:
        """/coins/categories → list of category dicts."""
        self._state.require_operational()
        try:
            response = await self._client.get("/coins/categories")
            self._raise_for_status(response)
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        return CoinGeckoAdapter.categories_to_list(response.json())[:limit]

    async def close(self) -> None:
        """Client is owned by HttpClientRegistry — don't close here."""
        return None

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code == _HTTP_RATE_LIMIT:
            raise RateLimitExceededError(f"coingecko rate limited: {response.text[:200]}")
        if response.status_code >= _HTTP_SERVER_ERROR_MIN:
            raise ProviderUnavailableError(
                f"coingecko {response.status_code}: {response.text[:200]}"
            )
        response.raise_for_status()
