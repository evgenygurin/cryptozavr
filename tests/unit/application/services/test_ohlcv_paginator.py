"""Unit tests for OHLCVPaginator."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.application.services.ohlcv_paginator import OHLCVPaginator
from cryptozavr.application.services.ohlcv_service import (
    OhlcvFetchResult,
    OhlcvService,
)
from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe, TimeRange
from cryptozavr.domain.venues import MarketType, VenueId

_TF_MS = Timeframe.H1.to_milliseconds()
_START = 1_700_000_000_000


def _symbol():
    return SymbolRegistry().get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


def _quality() -> DataQuality:
    return DataQuality(
        source=Provenance(venue_id="kucoin", endpoint="fetch_ohlcv"),
        fetched_at=Instant.from_ms(_START),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )


def _candle(ms: int) -> OHLCVCandle:
    return OHLCVCandle(
        opened_at=Instant.from_ms(ms),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=Decimal("5"),
    )


def _series(candles: tuple[OHLCVCandle, ...]) -> OHLCVSeries:
    first_ms = candles[0].opened_at.to_ms() if candles else _START
    # TimeRange requires end > start; pad by 1ms for empty-candle edge case.
    last_ms = candles[-1].opened_at.to_ms() + _TF_MS if candles else _START + 1
    return OHLCVSeries(
        symbol=_symbol(),
        timeframe=Timeframe.H1,
        candles=candles,
        range=TimeRange(
            start=Instant.from_ms(first_ms),
            end=Instant.from_ms(last_ms),
        ),
        quality=_quality(),
    )


def _result(candles: tuple[OHLCVCandle, ...], codes: list[str]) -> OhlcvFetchResult:
    return OhlcvFetchResult(series=_series(candles), reason_codes=codes)


class TestOHLCVPaginator:
    def test_rejects_inverted_range(self) -> None:
        service = MagicMock(spec=OhlcvService)
        with pytest.raises(ValueError, match="strictly greater"):
            OHLCVPaginator(
                service=service,
                venue="kucoin",
                symbol="BTC-USDT",
                timeframe=Timeframe.H1,
                since_ms=_START + _TF_MS,
                until_ms=_START,
            )

    def test_rejects_non_positive_chunk_size(self) -> None:
        service = MagicMock(spec=OhlcvService)
        with pytest.raises(ValueError, match="positive"):
            OHLCVPaginator(
                service=service,
                venue="kucoin",
                symbol="BTC-USDT",
                timeframe=Timeframe.H1,
                since_ms=_START,
                until_ms=_START + _TF_MS * 10,
                chunk_size=0,
            )

    def test_total_chunks_estimate(self) -> None:
        service = MagicMock(spec=OhlcvService)
        paginator = OHLCVPaginator(
            service=service,
            venue="kucoin",
            symbol="BTC-USDT",
            timeframe=Timeframe.H1,
            since_ms=_START,
            until_ms=_START + _TF_MS * 250,
            chunk_size=100,
        )
        assert paginator.total_chunks_estimate() == 3  # ceil(250/100)

    @pytest.mark.asyncio
    async def test_single_chunk_window_yields_once(self) -> None:
        candles = tuple(_candle(_START + i * _TF_MS) for i in range(5))
        service = MagicMock(spec=OhlcvService)
        service.fetch_ohlcv = AsyncMock(return_value=_result(candles, ["cache:miss"]))
        paginator = OHLCVPaginator(
            service=service,
            venue="kucoin",
            symbol="BTC-USDT",
            timeframe=Timeframe.H1,
            since_ms=_START,
            until_ms=_START + _TF_MS * 5,
            chunk_size=500,
        )
        chunks = [chunk async for chunk in paginator]
        assert len(chunks) == 1
        assert len(chunks[0].series.candles) == 5
        service.fetch_ohlcv.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_multi_chunk_span_advances_cursor(self) -> None:
        first = tuple(_candle(_START + i * _TF_MS) for i in range(3))
        second = tuple(_candle(_START + (3 + i) * _TF_MS) for i in range(2))
        service = MagicMock(spec=OhlcvService)
        service.fetch_ohlcv = AsyncMock(
            side_effect=[
                _result(first, ["chunk:0"]),
                _result(second, ["chunk:1"]),
            ],
        )
        paginator = OHLCVPaginator(
            service=service,
            venue="kucoin",
            symbol="BTC-USDT",
            timeframe=Timeframe.H1,
            since_ms=_START,
            until_ms=_START + _TF_MS * 5,
            chunk_size=3,
        )
        chunks = [chunk async for chunk in paginator]
        assert len(chunks) == 2
        assert service.fetch_ohlcv.await_count == 2
        first_call_kwargs = service.fetch_ohlcv.await_args_list[0].kwargs
        second_call_kwargs = service.fetch_ohlcv.await_args_list[1].kwargs
        assert first_call_kwargs["since"].to_ms() == _START
        # Cursor after first chunk = last candle opened_at + tf_ms = start + 3*tf
        assert second_call_kwargs["since"].to_ms() == _START + 3 * _TF_MS

    @pytest.mark.asyncio
    async def test_empty_chunk_stops_iteration(self) -> None:
        empty_candles: tuple[OHLCVCandle, ...] = ()
        service = MagicMock(spec=OhlcvService)
        service.fetch_ohlcv = AsyncMock(return_value=_result(empty_candles, ["exhausted"]))
        paginator = OHLCVPaginator(
            service=service,
            venue="kucoin",
            symbol="BTC-USDT",
            timeframe=Timeframe.H1,
            since_ms=_START,
            until_ms=_START + _TF_MS * 100,
            chunk_size=50,
        )
        chunks = [chunk async for chunk in paginator]
        assert chunks == []
        service.fetch_ohlcv.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_clips_candles_outside_window(self) -> None:
        """Provider may return candles beyond until_ms — paginator trims them."""
        since_ms = _START
        until_ms = _START + _TF_MS * 5  # 5-candle window
        # Provider returns 8 candles; last 3 are past until_ms.
        candles = tuple(_candle(_START + i * _TF_MS) for i in range(8))
        service = MagicMock(spec=OhlcvService)
        service.fetch_ohlcv = AsyncMock(return_value=_result(candles, ["cache:miss"]))
        paginator = OHLCVPaginator(
            service=service,
            venue="kucoin",
            symbol="BTC-USDT",
            timeframe=Timeframe.H1,
            since_ms=since_ms,
            until_ms=until_ms,
            chunk_size=10,
        )

        chunks = [chunk async for chunk in paginator]

        assert len(chunks) == 1
        clipped = chunks[0].series.candles
        assert len(clipped) == 5
        assert all(since_ms <= c.opened_at.to_ms() < until_ms for c in clipped)
        assert "paginator:clipped_to_window" in chunks[0].reason_codes

    @pytest.mark.asyncio
    async def test_candles_before_since_are_dropped(self) -> None:
        """Provider may ignore `since` and return older history — paginator drops it."""
        since_ms = _START + _TF_MS * 5
        until_ms = _START + _TF_MS * 10
        # Provider returns 10 candles starting from _START (before `since`).
        candles = tuple(_candle(_START + i * _TF_MS) for i in range(10))
        service = MagicMock(spec=OhlcvService)
        service.fetch_ohlcv = AsyncMock(return_value=_result(candles, ["cache:miss"]))
        paginator = OHLCVPaginator(
            service=service,
            venue="kucoin",
            symbol="BTC-USDT",
            timeframe=Timeframe.H1,
            since_ms=since_ms,
            until_ms=until_ms,
            chunk_size=10,
        )

        chunks = [chunk async for chunk in paginator]

        kept = [c for chunk in chunks for c in chunk.series.candles]
        assert all(since_ms <= c.opened_at.to_ms() < until_ms for c in kept)

    @pytest.mark.asyncio
    async def test_stuck_provider_does_not_loop_forever(self) -> None:
        # Provider keeps returning the same single candle (opened_at = _START).
        # First fetch yields, then cursor advances to _START + tf_ms. Second
        # fetch returns the same candle (still opened_at = _START); next_cursor
        # ends up <= cursor_ms → safety guard stops iteration.
        same_candle = (_candle(_START),)
        service = MagicMock(spec=OhlcvService)
        service.fetch_ohlcv = AsyncMock(return_value=_result(same_candle, ["stuck"]))
        paginator = OHLCVPaginator(
            service=service,
            venue="kucoin",
            symbol="BTC-USDT",
            timeframe=Timeframe.H1,
            since_ms=_START,
            until_ms=_START + _TF_MS * 100,
            chunk_size=50,
        )
        chunks = [chunk async for chunk in paginator]
        assert len(chunks) <= 3
        assert service.fetch_ohlcv.await_count <= 3
