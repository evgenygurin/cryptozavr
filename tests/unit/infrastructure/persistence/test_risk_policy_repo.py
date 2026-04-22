"""Unit tests for RiskPolicyRepository with a mocked asyncpg.Pool.

The repo mirrors StrategySpecRepository (Phase 2E-1):

- ``save`` upserts on BLAKE2b ``content_hash`` and returns the row id
  (new or pre-existing).
- ``activate`` runs a two-step transaction: deactivate all active rows,
  then activate the target id. Raises ``LookupError`` if the second
  UPDATE does not affect exactly one row.
- ``get_active`` returns a ``RiskPolicyRow`` dataclass or ``None``.
- ``list_history`` returns newest-first, newest at index 0.

Integration-level validation of the partial unique index + trigger lives
in tests/integration/supabase/test_risk_policies_roundtrip.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from cryptozavr.application.risk.risk_policy import (
    LimitDecimal,
    LimitInt,
    RiskPolicy,
)
from cryptozavr.domain.risk import Severity
from cryptozavr.infrastructure.persistence.risk_policy_repo import (
    RiskPolicyRepository,
    RiskPolicyRow,
    _canonical_policy_json,
    _content_hash,
)


def _valid_policy() -> RiskPolicy:
    return RiskPolicy(
        max_leverage=LimitDecimal(value=Decimal("3"), severity=Severity.DENY),
        max_position_pct=LimitDecimal(value=Decimal("0.25"), severity=Severity.DENY),
        max_daily_loss_pct=LimitDecimal(value=Decimal("0.05"), severity=Severity.WARN),
        cooldown_after_n_losses=LimitInt(value=3, severity=Severity.WARN),
        min_balance_buffer=LimitDecimal(value=Decimal("100"), severity=Severity.DENY),
    )


def _make_pool_with_conn(conn: MagicMock) -> MagicMock:
    """Return a mock asyncpg.Pool where ``async with pool.acquire() as conn``
    yields the supplied ``conn`` mock."""
    pool = MagicMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_ctx)
    return pool


def _conn_with_txn() -> MagicMock:
    """Connection mock where `async with conn.transaction():` is also supported."""
    conn = MagicMock()
    txn_ctx = MagicMock()
    txn_ctx.__aenter__ = AsyncMock(return_value=None)
    txn_ctx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=txn_ctx)
    return conn


# ---------------------------- helpers ----------------------------------------


class TestCanonicalJsonAndHash:
    def test_canonical_json_deterministic(self) -> None:
        policy = _valid_policy()
        a = _canonical_policy_json(policy)
        b = _canonical_policy_json(policy)
        assert a == b

    def test_canonical_json_compact(self) -> None:
        policy = _valid_policy()
        canonical = _canonical_policy_json(policy)
        # sort_keys + compact separators: no space after colon/comma.
        assert ": " not in canonical
        assert ", " not in canonical

    def test_content_hash_deterministic_and_hex_64(self) -> None:
        policy = _valid_policy()
        canonical = _canonical_policy_json(policy)
        h1 = _content_hash(canonical)
        h2 = _content_hash(canonical)
        assert h1 == h2
        assert len(h1) == 64
        assert all(c in "0123456789abcdef" for c in h1)

    def test_different_policies_produce_different_hashes(self) -> None:
        a = _valid_policy()
        b = RiskPolicy(
            max_leverage=LimitDecimal(value=Decimal("5"), severity=Severity.DENY),
            max_position_pct=a.max_position_pct,
            max_daily_loss_pct=a.max_daily_loss_pct,
            cooldown_after_n_losses=a.cooldown_after_n_losses,
            min_balance_buffer=a.min_balance_buffer,
        )
        assert _content_hash(_canonical_policy_json(a)) != _content_hash(
            _canonical_policy_json(b),
        )


# ---------------------------- save -------------------------------------------


class TestSave:
    @pytest.mark.asyncio
    async def test_insert_with_correct_arg_shape(self) -> None:
        policy = _valid_policy()
        new_id = uuid4()
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"id": new_id})
        pool = _make_pool_with_conn(conn)
        repo = RiskPolicyRepository(pool=pool)

        result = await repo.save(policy)
        assert result == new_id
        assert conn.fetchrow.await_count == 1
        args = conn.fetchrow.await_args.args
        # Positional args: sql, policy_json_canonical, content_hash.
        assert isinstance(args[1], str)
        assert args[1].startswith("{")
        assert isinstance(args[2], str)
        assert len(args[2]) == 64  # BLAKE2b hex(32) = 64 chars

    @pytest.mark.asyncio
    async def test_identical_policy_twice_returns_same_id(self) -> None:
        policy = _valid_policy()
        existing_id = uuid4()
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"id": existing_id})
        pool = _make_pool_with_conn(conn)
        repo = RiskPolicyRepository(pool=pool)

        id_a = await repo.save(policy)
        id_b = await repo.save(policy)
        assert id_a == id_b == existing_id

    @pytest.mark.asyncio
    async def test_returns_uuid_object_not_string(self) -> None:
        policy = _valid_policy()
        conn = MagicMock()
        conn.fetchrow = AsyncMock(
            return_value={"id": "8c2b3f4a-5e69-4a10-a4c2-1f3b4a5e6901"},
        )
        pool = _make_pool_with_conn(conn)
        repo = RiskPolicyRepository(pool=pool)
        result = await repo.save(policy)
        assert isinstance(result, UUID)


# ---------------------------- activate ---------------------------------------


class TestActivate:
    @pytest.mark.asyncio
    async def test_success_runs_two_updates_in_transaction(self) -> None:
        conn = _conn_with_txn()
        # First call deactivates whatever is active ("UPDATE N"); second call
        # activates the target ("UPDATE 1").
        conn.execute = AsyncMock(side_effect=["UPDATE 0", "UPDATE 1"])
        pool = _make_pool_with_conn(conn)
        repo = RiskPolicyRepository(pool=pool)

        target = uuid4()
        await repo.activate(target)
        assert conn.execute.await_count == 2
        # Deactivate call comes first.
        deactivate_sql = conn.execute.await_args_list[0].args[0]
        assert "is_active = false" in deactivate_sql
        # Activate call targets the id binding.
        activate_call = conn.execute.await_args_list[1]
        assert "is_active = true" in activate_call.args[0]
        assert activate_call.args[1] == target

    @pytest.mark.asyncio
    async def test_raises_lookup_error_when_target_missing(self) -> None:
        conn = _conn_with_txn()
        conn.execute = AsyncMock(side_effect=["UPDATE 0", "UPDATE 0"])
        pool = _make_pool_with_conn(conn)
        repo = RiskPolicyRepository(pool=pool)

        with pytest.raises(LookupError):
            await repo.activate(uuid4())


# ---------------------------- save_and_activate ------------------------------


class TestSaveAndActivate:
    @pytest.mark.asyncio
    async def test_happy_path_runs_insert_plus_two_updates_in_transaction(self) -> None:
        policy = _valid_policy()
        new_id = uuid4()
        conn = _conn_with_txn()
        conn.fetchrow = AsyncMock(return_value={"id": new_id})
        conn.execute = AsyncMock(side_effect=["UPDATE 0", "UPDATE 1"])
        pool = _make_pool_with_conn(conn)
        repo = RiskPolicyRepository(pool=pool)

        result = await repo.save_and_activate(policy)
        assert result == new_id
        # One INSERT + two UPDATEs, all against the same connection under
        # a single transaction context.
        assert conn.fetchrow.await_count == 1
        assert conn.execute.await_count == 2
        deactivate_sql = conn.execute.await_args_list[0].args[0]
        activate_sql = conn.execute.await_args_list[1].args[0]
        assert "is_active = false" in deactivate_sql
        assert "is_active = true" in activate_sql

    @pytest.mark.asyncio
    async def test_raises_lookup_error_when_inserted_id_missing_on_activate(
        self,
    ) -> None:
        # Impossible in practice (we just inserted), but defensively covered.
        policy = _valid_policy()
        conn = _conn_with_txn()
        conn.fetchrow = AsyncMock(return_value={"id": uuid4()})
        conn.execute = AsyncMock(side_effect=["UPDATE 0", "UPDATE 0"])
        pool = _make_pool_with_conn(conn)
        repo = RiskPolicyRepository(pool=pool)

        with pytest.raises(LookupError):
            await repo.save_and_activate(policy)


# ---------------------------- get_active -------------------------------------


class TestGetActive:
    @pytest.mark.asyncio
    async def test_returns_row_when_active_exists(self) -> None:
        policy = _valid_policy()
        canonical = _canonical_policy_json(policy)
        row_id = uuid4()
        created = datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC)
        activated = datetime(2026, 4, 22, 12, 30, 0, tzinfo=UTC)
        mock_row = {
            "id": row_id,
            "policy_json": canonical,
            "is_active": True,
            "created_at": created,
            "activated_at": activated,
        }
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=mock_row)
        pool = _make_pool_with_conn(conn)
        repo = RiskPolicyRepository(pool=pool)

        result = await repo.get_active()
        assert result is not None
        assert isinstance(result, RiskPolicyRow)
        assert result.id == row_id
        assert result.is_active is True
        assert result.created_at_ms == int(created.timestamp() * 1000)
        assert result.activated_at_ms == int(activated.timestamp() * 1000)
        assert result.policy.max_leverage.value == Decimal("3")

    @pytest.mark.asyncio
    async def test_returns_none_when_no_active(self) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        pool = _make_pool_with_conn(conn)
        repo = RiskPolicyRepository(pool=pool)
        assert await repo.get_active() is None


# ---------------------------- list_history -----------------------------------


class TestListHistory:
    @pytest.mark.asyncio
    async def test_default_limit_is_50(self) -> None:
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[])
        pool = _make_pool_with_conn(conn)
        repo = RiskPolicyRepository(pool=pool)

        result = await repo.list_history()
        assert result == []
        call_args = conn.fetch.await_args.args
        assert call_args[1] == 50

    @pytest.mark.asyncio
    async def test_custom_limit_passed_through(self) -> None:
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[])
        pool = _make_pool_with_conn(conn)
        repo = RiskPolicyRepository(pool=pool)
        await repo.list_history(limit=5)
        assert conn.fetch.await_args.args[1] == 5

    @pytest.mark.asyncio
    async def test_rows_mapped_to_risk_policy_row(self) -> None:
        policy = _valid_policy()
        canonical = _canonical_policy_json(policy)
        row_id = uuid4()
        created = datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC)
        row = {
            "id": row_id,
            "policy_json": canonical,
            "is_active": False,
            "created_at": created,
            "activated_at": None,
        }
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[row])
        pool = _make_pool_with_conn(conn)
        repo = RiskPolicyRepository(pool=pool)

        result = await repo.list_history()
        assert len(result) == 1
        entry = result[0]
        assert isinstance(entry, RiskPolicyRow)
        assert entry.id == row_id
        assert entry.is_active is False
        assert entry.activated_at_ms is None
