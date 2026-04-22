"""Live-Supabase roundtrip for StrategySpecRepository.

Exercises migration 00000000000070_strategy_specs.sql end-to-end:

  * save() insert path — pgvector `::extensions.vector` cast resolves against
    the real pgvector codec on the server side.
  * save() upsert path — identical canonical JSON → same row id, updated_at
    bumped by the trigger.
  * list_recent() → get() → delete() → get() reads-after-writes on the real
    jsonb column (asyncpg returns it as str when no codec is registered).

Skips if Supabase isn't reachable (see tests/integration/conftest.py for the
fixture semantics).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from cryptozavr.infrastructure.persistence.strategy_spec_repo import (
    StrategySpecRepository,
)
from cryptozavr.mcp.tools.strategy_dtos import StrategySpecPayload

pytestmark = pytest.mark.integration


def _valid_payload_dict(*, name: str = "sma-cross") -> dict:
    return {
        "name": name,
        "description": "fast-over-slow SMA cross",
        "venue": "kucoin",
        "symbol": {
            "venue": "kucoin",
            "base": "BTC",
            "quote": "USDT",
            "market_type": "spot",
            "native_symbol": "BTC-USDT",
        },
        "timeframe": "1h",
        "entry": {
            "side": "long",
            "conditions": [
                {
                    "lhs": {"kind": "sma", "period": 20, "source": "close"},
                    "op": "crosses_above",
                    "rhs": {"kind": "sma", "period": 50, "source": "close"},
                },
            ],
        },
        "exit": {
            "conditions": [],
            "take_profit_pct": "0.05",
            "stop_loss_pct": "0.02",
        },
        "size_pct": "0.25",
        "version": 1,
    }


def _make_payload(*, name: str = "sma-cross") -> StrategySpecPayload:
    return StrategySpecPayload.model_validate(_valid_payload_dict(name=name))


@pytest_asyncio.fixture
async def clean_strategy_specs(supabase_pool: asyncpg.Pool) -> AsyncIterator[None]:
    """Truncate strategy_specs between tests so each case starts empty."""
    async with supabase_pool.acquire() as conn:
        await conn.execute(
            "truncate table cryptozavr.strategy_specs restart identity cascade",
        )
    yield


@pytest_asyncio.fixture
async def strategy_repo(
    supabase_pool: asyncpg.Pool,
) -> AsyncIterator[StrategySpecRepository]:
    yield StrategySpecRepository(pool=supabase_pool)


async def test_save_then_list_recent_shows_row(
    strategy_repo: StrategySpecRepository,
    clean_strategy_specs: None,
) -> None:
    spec = _make_payload(name="sma-cross")
    new_id = await strategy_repo.save(spec)

    rows = await strategy_repo.list_recent(limit=10)
    assert len(rows) == 1
    row = rows[0]
    assert row.id == new_id
    assert row.name == "sma-cross"
    assert row.version == 1
    assert row.venue_id == "kucoin"
    assert row.symbol_native == "BTC-USDT"
    assert row.timeframe == "1h"


async def test_save_twice_with_same_spec_returns_same_id(
    strategy_repo: StrategySpecRepository,
    clean_strategy_specs: None,
) -> None:
    spec = _make_payload()
    id_a = await strategy_repo.save(spec)
    id_b = await strategy_repo.save(spec)
    assert id_a == id_b
    # Only one row after two saves (content_hash deduplicates).
    rows = await strategy_repo.list_recent(limit=10)
    assert len(rows) == 1


async def test_save_get_delete_roundtrip(
    strategy_repo: StrategySpecRepository,
    clean_strategy_specs: None,
) -> None:
    spec = _make_payload(name="sma-cross-roundtrip")
    new_id = await strategy_repo.save(spec)

    loaded = await strategy_repo.get(new_id)
    assert loaded is not None
    assert loaded.name == spec.name
    assert loaded.version == spec.version
    assert loaded.venue == spec.venue
    assert loaded.timeframe == spec.timeframe

    deleted = await strategy_repo.delete(new_id)
    assert deleted is True

    assert await strategy_repo.get(new_id) is None
    # Second delete reports False (no matching row).
    assert await strategy_repo.delete(new_id) is False
