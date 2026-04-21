"""SupabaseGateway: Facade over asyncpg + supabase-py + realtime-py + storage/rpc.

M2.2 exposes:
- symbol id resolution (asyncpg)
- OHLCV upsert + range load (asyncpg bulk)
- ticker upsert + single-symbol load (asyncpg)
- query_log insert (asyncpg)
- close (lifecycle)

Stubs (raise NotImplementedError): realtime subscribe_tickers, storage
uploads, rpc match_regimes.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

import asyncpg

from cryptozavr.domain.market_data import OHLCVSeries, Ticker
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.infrastructure.supabase.mappers import (
    row_to_ohlcv_series,
    row_to_ticker,
)
from cryptozavr.infrastructure.supabase.realtime import (
    RealtimeSubscriber,
    SubscriptionHandle,
)
from cryptozavr.infrastructure.supabase.rpc import RpcClient
from cryptozavr.infrastructure.supabase.storage import StorageClient


class SupabaseGateway:
    """Facade over Supabase integration clients.

    Owns the asyncpg Pool; stubs realtime/storage/rpc until later phases.
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        symbol_registry: SymbolRegistry,
        *,
        realtime: RealtimeSubscriber | None = None,
        storage: StorageClient | None = None,
        rpc: RpcClient | None = None,
    ) -> None:
        self._pool = pool
        self._registry = symbol_registry
        self._realtime = realtime or RealtimeSubscriber()
        self._storage = storage or StorageClient()
        self._rpc = rpc or RpcClient()

    async def resolve_symbol_id(self, symbol: Symbol) -> int:
        """Look up symbols.id by identity tuple (venue, base, quote, market_type)."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select id from cryptozavr.symbols
                 where venue_id = $1 and base = $2 and quote = $3 and market_type = $4
                """,
                symbol.venue.value,
                symbol.base,
                symbol.quote,
                symbol.market_type.value,
            )
        if row is None:
            raise LookupError(
                f"symbol not registered in DB: {symbol.venue.value}:"
                f"{symbol.base}/{symbol.quote}/{symbol.market_type.value}"
            )
        return int(row["id"])

    async def upsert_ticker(self, ticker: Ticker) -> None:
        """Upsert a single ticker into tickers_live (one row per symbol)."""
        symbol_id = await self.resolve_symbol_id(ticker.symbol)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                insert into cryptozavr.tickers_live (
                  symbol_id, last, bid, ask, volume_24h, change_24h_pct,
                  high_24h, low_24h, observed_at, source_endpoint
                )
                values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                on conflict (symbol_id) do update set
                  last = excluded.last,
                  bid = excluded.bid,
                  ask = excluded.ask,
                  volume_24h = excluded.volume_24h,
                  change_24h_pct = excluded.change_24h_pct,
                  high_24h = excluded.high_24h,
                  low_24h = excluded.low_24h,
                  observed_at = excluded.observed_at,
                  fetched_at = now(),
                  source_endpoint = excluded.source_endpoint
                """,
                symbol_id,
                ticker.last,
                ticker.bid,
                ticker.ask,
                ticker.volume_24h,
                ticker.change_24h_pct.value if ticker.change_24h_pct else None,
                ticker.high_24h,
                ticker.low_24h,
                ticker.observed_at.to_datetime(),
                ticker.quality.source.endpoint,
            )

    async def load_ticker(self, symbol: Symbol) -> Ticker | None:
        """Fetch the latest ticker for symbol, if any."""
        symbol_id = await self.resolve_symbol_id(symbol)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select symbol_id, last, bid, ask, volume_24h, change_24h_pct,
                       high_24h, low_24h, observed_at, fetched_at, source_endpoint
                  from cryptozavr.tickers_live
                 where symbol_id = $1
                """,
                symbol_id,
            )
        if row is None:
            return None
        quality = DataQuality(
            source=Provenance(
                venue_id=symbol.venue.value,
                endpoint=row["source_endpoint"],
            ),
            fetched_at=Instant(row["fetched_at"]),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=True,
        )
        return row_to_ticker(row, symbol=symbol, quality=quality)

    async def upsert_ohlcv(self, series: OHLCVSeries) -> int:
        """Bulk-upsert OHLCV candles. Returns number of candles written."""
        if not series.candles:
            return 0
        symbol_id = await self.resolve_symbol_id(series.symbol)
        records = [
            (
                symbol_id,
                series.timeframe.value,
                c.opened_at.to_datetime(),
                c.open,
                c.high,
                c.low,
                c.close,
                c.volume,
                c.closed,
            )
            for c in series.candles
        ]
        async with self._pool.acquire() as conn:
            await conn.executemany(
                """
                insert into cryptozavr.ohlcv_candles (
                  symbol_id, timeframe, opened_at,
                  open, high, low, close, volume, closed
                )
                values ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                on conflict (symbol_id, timeframe, opened_at) do update set
                  open = excluded.open,
                  high = excluded.high,
                  low = excluded.low,
                  close = excluded.close,
                  volume = excluded.volume,
                  closed = excluded.closed,
                  fetched_at = now()
                """,
                records,
            )
        return len(records)

    async def load_ohlcv(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        *,
        since: Instant | None = None,
        limit: int = 500,
    ) -> OHLCVSeries | None:
        """Fetch OHLCV range DESC-ordered by opened_at, then re-sort ASC."""
        symbol_id = await self.resolve_symbol_id(symbol)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select opened_at, open, high, low, close, volume, closed
                  from cryptozavr.ohlcv_candles
                 where symbol_id = $1 and timeframe = $2
                   and ($3::timestamptz is null or opened_at >= $3)
                 order by opened_at desc
                 limit $4
                """,
                symbol_id,
                timeframe.value,
                since.to_datetime() if since else None,
                limit,
            )
        if not rows:
            return None
        ordered_rows: Sequence[dict[str, Any]] = list(reversed(rows))
        quality = DataQuality(
            source=Provenance(
                venue_id=symbol.venue.value,
                endpoint="fetch_ohlcv",
            ),
            fetched_at=Instant.now(),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=True,
        )
        return row_to_ohlcv_series(
            ordered_rows,
            symbol=symbol,
            timeframe=timeframe,
            quality=quality,
        )

    async def insert_query_log(
        self,
        *,
        kind: str,
        symbol: Symbol | None,
        timeframe: Timeframe | None,
        range_start: Instant | None,
        range_end: Instant | None,
        limit_n: int | None,
        force_refresh: bool,
        reason_codes: Sequence[str],
        quality: dict[str, Any] | None,
        issued_by: str,
        client_id: str | None,
    ) -> UUID:
        """Insert a row into query_log. Returns the generated UUID."""
        symbol_id: int | None = None
        if symbol is not None:
            symbol_id = await self.resolve_symbol_id(symbol)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                insert into cryptozavr.query_log (
                  kind, symbol_id, timeframe, range_start, range_end,
                  limit_n, force_refresh, reason_codes, quality,
                  issued_by, client_id
                )
                values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                returning id
                """,
                kind,
                symbol_id,
                timeframe.value if timeframe else None,
                range_start.to_datetime() if range_start else None,
                range_end.to_datetime() if range_end else None,
                limit_n,
                force_refresh,
                list(reason_codes),
                quality,
                issued_by,
                client_id,
            )
        assert row is not None
        return UUID(str(row["id"]))

    async def subscribe_tickers(
        self,
        venue_id: str,
        callback: object,
    ) -> SubscriptionHandle:
        return await self._realtime.subscribe_tickers(venue_id, callback)

    async def upload_artifact(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str,
    ) -> str:
        return await self._storage.upload(bucket, key, data, content_type)

    async def match_regimes(
        self,
        embedding: Sequence[float],
        threshold: float,
        limit: int,
    ) -> list[dict[str, Any]]:
        return await self._rpc.match_regimes(embedding, threshold, limit)

    async def close(self) -> None:
        """Close the underlying pool."""
        await self._realtime.close()
        await self._pool.close()
