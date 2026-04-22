"""OHLCVPaginator — Iterator over large historical OHLCV windows.

Fetches candle chunks (<= chunk_size per call) through OhlcvService, stepping
the cursor forward by `timeframe.ms * chunk_size`. Exposes an async-iterator
protocol so MCP tools can `async for` through arbitrarily long history and
emit progress updates between chunks.

Short-circuits on empty chunks (provider exhausted the venue's history) and
guards against no-progress cursors (safety against buggy providers).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from cryptozavr.application.services.ohlcv_service import (
    OhlcvFetchResult,
    OhlcvService,
)
from cryptozavr.domain.value_objects import Instant, Timeframe


class OHLCVPaginator:
    """Async iterator yielding OhlcvFetchResult chunks for [since_ms, until_ms).

    Usage:
        async for chunk in OHLCVPaginator(
            service=ohlcv_service,
            venue="kucoin",
            symbol="BTC-USDT",
            timeframe=Timeframe.H1,
            since_ms=1_700_000_000_000,
            until_ms=1_700_600_000_000,
            chunk_size=500,
        ):
            ...  # chunk.series.candles, chunk.reason_codes
    """

    def __init__(
        self,
        *,
        service: OhlcvService,
        venue: str,
        symbol: str,
        timeframe: Timeframe,
        since_ms: int,
        until_ms: int,
        chunk_size: int = 500,
        force_refresh: bool = False,
    ) -> None:
        if until_ms <= since_ms:
            raise ValueError(
                f"until_ms ({until_ms}) must be strictly greater than since_ms ({since_ms})",
            )
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")
        self._service = service
        self._venue = venue
        self._symbol = symbol
        self._timeframe = timeframe
        self._since_ms = since_ms
        self._until_ms = until_ms
        self._chunk_size = chunk_size
        self._force_refresh = force_refresh

    def total_chunks_estimate(self) -> int:
        """Estimate how many fetches will be needed to cover the window."""
        span = self._until_ms - self._since_ms
        step = self._timeframe.to_milliseconds() * self._chunk_size
        return max(1, -(-span // step))  # ceil div

    async def __aiter__(self) -> AsyncIterator[OhlcvFetchResult]:
        cursor_ms = self._since_ms
        while cursor_ms < self._until_ms:
            result = await self._service.fetch_ohlcv(
                venue=self._venue,
                symbol=self._symbol,
                timeframe=self._timeframe,
                limit=self._chunk_size,
                since=Instant.from_ms(cursor_ms),
                force_refresh=self._force_refresh,
            )
            candles = result.series.candles
            if not candles:
                return  # provider exhausted — stop streaming
            clipped = self._clip_to_window(result)
            if clipped.series.candles:
                yield clipped
            last_opened = candles[-1].opened_at.to_ms()
            next_cursor = last_opened + self._timeframe.to_milliseconds()
            if next_cursor <= cursor_ms:
                return  # safety guard: no forward progress
            cursor_ms = next_cursor

    def _clip_to_window(self, result: OhlcvFetchResult) -> OhlcvFetchResult:
        """Drop candles whose `opened_at` falls outside `[since_ms, until_ms)`.

        Providers may ignore `since` when data is older than their retention
        (returning recent candles instead) or overshoot `until_ms` on the last
        chunk. The paginator's contract is that consumers see only the window
        they asked for, so we trim here.
        """
        series = result.series
        kept = tuple(
            c for c in series.candles if self._since_ms <= c.opened_at.to_ms() < self._until_ms
        )
        if len(kept) == len(series.candles):
            return result
        return OhlcvFetchResult(
            series=series.__class__(
                symbol=series.symbol,
                timeframe=series.timeframe,
                candles=kept,
                range=series.range,
                quality=series.quality,
            ),
            reason_codes=[*list(result.reason_codes), "paginator:clipped_to_window"],
        )
