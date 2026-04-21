"""Test LoggingDecorator: stdlib logging records inner calls."""

from __future__ import annotations

import logging

import pytest

from cryptozavr.infrastructure.providers.decorators.logging import (
    LoggingDecorator,
)


class _StubProvider:
    venue_id = "kucoin"

    async def fetch_ticker(self, symbol: str) -> str:
        return f"ticker-{symbol}"

    async def fetch_ohlcv(self, symbol: str) -> str:
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_logs_successful_call(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    provider = _StubProvider()
    decorator = LoggingDecorator(provider)
    result = await decorator.fetch_ticker("BTC/USDT")
    assert result == "ticker-BTC/USDT"
    msgs = [r.message for r in caplog.records]
    assert any("fetch_ticker" in m for m in msgs)


@pytest.mark.asyncio
async def test_logs_failed_call_and_reraises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    provider = _StubProvider()
    decorator = LoggingDecorator(provider)
    with pytest.raises(RuntimeError, match="boom"):
        await decorator.fetch_ohlcv("BTC/USDT")
    msgs = [r.message for r in caplog.records]
    assert any("fetch_ohlcv" in m and "failed" in m.lower() for m in msgs)


@pytest.mark.asyncio
async def test_venue_id_forwarded() -> None:
    provider = _StubProvider()
    decorator = LoggingDecorator(provider)
    assert decorator.venue_id == "kucoin"
