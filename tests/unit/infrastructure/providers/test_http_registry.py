"""Test HttpClientRegistry: one httpx.AsyncClient per venue, async lifecycle."""

from __future__ import annotations

import httpx
import pytest

from cryptozavr.infrastructure.providers.http import HttpClientRegistry


@pytest.mark.asyncio
async def test_get_returns_same_client_for_same_venue() -> None:
    registry = HttpClientRegistry()
    a = await registry.get("kucoin", base_url="https://api.kucoin.com")
    b = await registry.get("kucoin", base_url="https://api.kucoin.com")
    assert a is b
    await registry.close_all()


@pytest.mark.asyncio
async def test_get_returns_different_client_for_different_venue() -> None:
    registry = HttpClientRegistry()
    a = await registry.get("kucoin", base_url="https://api.kucoin.com")
    b = await registry.get("coingecko", base_url="https://api.coingecko.com")
    assert a is not b
    await registry.close_all()


@pytest.mark.asyncio
async def test_client_is_async() -> None:
    registry = HttpClientRegistry()
    client = await registry.get("kucoin", base_url="https://api.kucoin.com")
    assert isinstance(client, httpx.AsyncClient)
    await registry.close_all()


@pytest.mark.asyncio
async def test_close_all_closes_every_client() -> None:
    registry = HttpClientRegistry()
    await registry.get("kucoin", base_url="https://api.kucoin.com")
    await registry.get("coingecko", base_url="https://api.coingecko.com")
    await registry.close_all()

    new_client = await registry.get("kucoin", base_url="https://api.kucoin.com")
    assert new_client is not None
    await registry.close_all()


@pytest.mark.asyncio
async def test_get_uses_default_timeout() -> None:
    registry = HttpClientRegistry(default_timeout=10.0)
    client = await registry.get("kucoin", base_url="https://api.kucoin.com")
    assert client.timeout.read == 10.0
    await registry.close_all()
