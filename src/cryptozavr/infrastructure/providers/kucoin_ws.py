"""Thin async generator wrapper around ccxt.pro.kucoin for WS ticker streams.

ccxt.pro handles reconnects + exponential backoff internally. We
translate ccxt.BadSymbol -> SymbolNotFoundError; everything else
propagates.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import ccxt.pro as ccxt_pro

from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    SymbolNotFoundError,
)

_LOG = logging.getLogger(__name__)


class KucoinWsProvider:
    """Shared ccxt.pro.kucoin instance — lazy-init, closed on lifespan exit."""

    def __init__(self) -> None:
        self._exchange: Any | None = None
        self._lock = asyncio.Lock()

    async def _ensure(self) -> Any:
        async with self._lock:
            if self._exchange is None:
                self._exchange = ccxt_pro.kucoin({"newUpdates": True})
        return self._exchange

    async def watch_ticker(self, native_symbol: str) -> AsyncIterator[tuple[Decimal, int]]:
        """Yield (last_price, observed_at_ms) until caller stops iterating."""
        exchange = await self._ensure()
        ccxt_symbol = _native_to_ccxt(native_symbol)
        while True:
            try:
                raw = await exchange.watch_ticker(ccxt_symbol)
            except ccxt_pro.BadSymbol as exc:
                raise SymbolNotFoundError(user_input=native_symbol, venue="kucoin") from exc
            except ccxt_pro.NetworkError as exc:
                _LOG.warning("kucoin WS NetworkError, reconnecting: %s", exc)
                continue
            except Exception as exc:
                raise ProviderUnavailableError(f"kucoin WS failure: {exc}") from exc
            last = raw.get("last")
            ts = raw.get("timestamp")
            if last is None or ts is None:
                continue
            yield Decimal(str(last)), int(ts)

    async def close(self) -> None:
        if self._exchange is not None:
            try:
                await self._exchange.close()
            finally:
                self._exchange = None


def _native_to_ccxt(native: str) -> str:
    """KuCoin native ('BTC-USDT') -> ccxt canonical ('BTC/USDT')."""
    return native.replace("-", "/", 1)
