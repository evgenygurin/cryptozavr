"""Unit tests for StrategySpecRepository with a mocked asyncpg.Pool.

The repo is a thin CRUD layer; most coverage is about arg order, SQL literal
shape (the `::extensions.vector` cast expects a `[..]` string), and mapping
of rows back to `StoredStrategyRow` dataclasses. Integration-level validation
(vector cast actually works, IVFFLAT index populated, RPC returns top-K)
lives in tests/integration/supabase/test_strategy_specs_roundtrip.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from cryptozavr.infrastructure.persistence.strategy_spec_repo import (
    StoredStrategyRow,
    StrategySpecRepository,
    _canonical_spec_json,
    _content_hash,
    _vector_literal,
)
from cryptozavr.mcp.tools.strategy_dtos import StrategySpecPayload


def _valid_payload_dict() -> dict:
    return {
        "name": "sma-cross",
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


def _make_payload() -> StrategySpecPayload:
    return StrategySpecPayload.model_validate(_valid_payload_dict())


def _make_pool_with_conn(conn: MagicMock) -> MagicMock:
    """Return a mock asyncpg.Pool where `async with pool.acquire() as conn`
    yields the supplied `conn` mock."""
    pool = MagicMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_ctx)
    return pool


# ---------------------------- helpers ----------------------------------------


class TestContentHash:
    def test_deterministic(self) -> None:
        spec = _make_payload()
        canonical = _canonical_spec_json(spec)
        h1 = _content_hash(canonical)
        h2 = _content_hash(canonical)
        assert h1 == h2

    def test_hash_hex_length_64(self) -> None:
        spec = _make_payload()
        h = _content_hash(_canonical_spec_json(spec))
        # BLAKE2b digest_size=32 bytes → 64 hex chars
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_specs_different_hashes(self) -> None:
        spec_a = _make_payload()
        alt = _valid_payload_dict()
        alt["name"] = "renamed"
        spec_b = StrategySpecPayload.model_validate(alt)
        h_a = _content_hash(_canonical_spec_json(spec_a))
        h_b = _content_hash(_canonical_spec_json(spec_b))
        assert h_a != h_b


class TestCanonicalJson:
    def test_keys_sorted(self) -> None:
        spec = _make_payload()
        canonical = _canonical_spec_json(spec)
        # sort_keys + compact separators; verify: no space after colon/comma.
        assert ": " not in canonical
        assert ", " not in canonical

    def test_canonical_is_stable_across_semantically_identical_specs(self) -> None:
        spec_a = _make_payload()
        spec_b = StrategySpecPayload.model_validate(_valid_payload_dict())
        assert _canonical_spec_json(spec_a) == _canonical_spec_json(spec_b)


class TestVectorLiteral:
    def test_brackets_and_comma_separated(self) -> None:
        lit = _vector_literal([0.1, 0.2, 0.3])
        assert lit.startswith("[")
        assert lit.endswith("]")
        # Three values ⇒ two commas.
        assert lit.count(",") == 2

    def test_384_float_list_produces_383_commas(self) -> None:
        lit = _vector_literal([0.0] * 384)
        assert lit.count(",") == 383

    def test_empty_list_produces_bare_brackets(self) -> None:
        assert _vector_literal([]) == "[]"


# ---------------------------- save -------------------------------------------


class TestSave:
    @pytest.mark.asyncio
    async def test_executes_insert_with_correct_arg_shape(self) -> None:
        spec = _make_payload()
        new_id = uuid4()
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"id": new_id})
        pool = _make_pool_with_conn(conn)
        repo = StrategySpecRepository(pool=pool)

        result = await repo.save(spec)
        assert result == new_id
        # One fetchrow call (no separate select).
        assert conn.fetchrow.await_count == 1
        args = conn.fetchrow.await_args.args
        # Positional args: sql, name, version, venue, symbol_native, timeframe, spec_json, hash, emb_literal
        assert args[1] == "sma-cross"
        assert args[2] == 1
        assert args[3] == "kucoin"
        assert args[4] == "BTC-USDT"
        assert args[5] == "1h"
        # spec_json is the canonical string.
        assert isinstance(args[6], str)
        assert args[6].startswith("{")
        # hash: 64 hex chars.
        assert isinstance(args[7], str)
        assert len(args[7]) == 64
        # embedding literal: '[...]' form.
        emb = args[8]
        assert isinstance(emb, str)
        assert emb.startswith("[")
        assert emb.endswith("]")

    @pytest.mark.asyncio
    async def test_identical_spec_twice_returns_same_id_via_upsert(self) -> None:
        spec = _make_payload()
        existing_id = uuid4()
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"id": existing_id})
        pool = _make_pool_with_conn(conn)
        repo = StrategySpecRepository(pool=pool)

        id_a = await repo.save(spec)
        id_b = await repo.save(spec)
        assert id_a == id_b == existing_id

    @pytest.mark.asyncio
    async def test_returns_uuid_object_not_string(self) -> None:
        spec = _make_payload()
        # Mock may return string or UUID; repo must always normalise to UUID.
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"id": "8c2b3f4a-5e69-4a10-a4c2-1f3b4a5e6901"})
        pool = _make_pool_with_conn(conn)
        repo = StrategySpecRepository(pool=pool)
        result = await repo.save(spec)
        assert isinstance(result, UUID)


# ---------------------------- list_recent ------------------------------------


class TestListRecent:
    @pytest.mark.asyncio
    async def test_default_limit_is_50(self) -> None:
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[])
        pool = _make_pool_with_conn(conn)
        repo = StrategySpecRepository(pool=pool)

        result = await repo.list_recent()
        assert result == []
        # sql + limit
        call_args = conn.fetch.await_args.args
        assert call_args[1] == 50

    @pytest.mark.asyncio
    async def test_custom_limit_passed_through(self) -> None:
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[])
        pool = _make_pool_with_conn(conn)
        repo = StrategySpecRepository(pool=pool)

        await repo.list_recent(limit=5)
        call_args = conn.fetch.await_args.args
        assert call_args[1] == 5

    @pytest.mark.asyncio
    async def test_empty_result_returns_empty_list(self) -> None:
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[])
        pool = _make_pool_with_conn(conn)
        repo = StrategySpecRepository(pool=pool)
        assert await repo.list_recent() == []

    @pytest.mark.asyncio
    async def test_rows_mapped_to_stored_strategy_row(self) -> None:
        row_id = uuid4()
        created = datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC)
        updated = datetime(2026, 4, 22, 12, 30, 0, tzinfo=UTC)
        mock_row = {
            "id": row_id,
            "name": "sma-cross",
            "version": 1,
            "venue_id": "kucoin",
            "symbol_native": "BTC-USDT",
            "timeframe": "1h",
            "created_at": created,
            "updated_at": updated,
        }
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[mock_row])
        pool = _make_pool_with_conn(conn)
        repo = StrategySpecRepository(pool=pool)

        result = await repo.list_recent()
        assert len(result) == 1
        entry = result[0]
        assert isinstance(entry, StoredStrategyRow)
        assert entry.id == row_id
        assert entry.name == "sma-cross"
        assert entry.version == 1
        assert entry.venue_id == "kucoin"
        assert entry.symbol_native == "BTC-USDT"
        assert entry.timeframe == "1h"
        assert entry.created_at_ms == int(created.timestamp() * 1000)
        assert entry.updated_at_ms == int(updated.timestamp() * 1000)


# ---------------------------- get --------------------------------------------


class TestGet:
    @pytest.mark.asyncio
    async def test_returns_parsed_payload(self) -> None:
        spec = _make_payload()
        canonical = _canonical_spec_json(spec)
        # asyncpg yields jsonb columns as a str (when codec isn't set up).
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"spec_json": canonical})
        pool = _make_pool_with_conn(conn)
        repo = StrategySpecRepository(pool=pool)

        loaded = await repo.get(uuid4())
        assert loaded is not None
        assert loaded.name == spec.name
        assert loaded.venue == spec.venue

    @pytest.mark.asyncio
    async def test_no_match_returns_none(self) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        pool = _make_pool_with_conn(conn)
        repo = StrategySpecRepository(pool=pool)
        result = await repo.get(uuid4())
        assert result is None


# ---------------------------- delete -----------------------------------------


class TestDelete:
    @pytest.mark.asyncio
    async def test_returns_true_when_delete_1(self) -> None:
        conn = MagicMock()
        conn.execute = AsyncMock(return_value="DELETE 1")
        pool = _make_pool_with_conn(conn)
        repo = StrategySpecRepository(pool=pool)
        assert await repo.delete(uuid4()) is True

    @pytest.mark.asyncio
    async def test_returns_false_when_delete_0(self) -> None:
        conn = MagicMock()
        conn.execute = AsyncMock(return_value="DELETE 0")
        pool = _make_pool_with_conn(conn)
        repo = StrategySpecRepository(pool=pool)
        assert await repo.delete(uuid4()) is False
