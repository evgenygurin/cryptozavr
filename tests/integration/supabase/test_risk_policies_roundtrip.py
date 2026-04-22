"""Live-Supabase roundtrip for RiskPolicyRepository.

Exercises migration 00000000000080_risk_policies.sql end-to-end:

  * save() insert path + content_hash-idempotency on repeat.
  * activate() transactional transition — exactly one row active at a
    time (partial unique index enforces this).
  * get_active() reads the active row back after the trigger has fired
    `activated_at := now()`.

Skips if Supabase isn't reachable (see tests/integration/conftest.py for
the fixture semantics).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal

import asyncpg
import pytest
import pytest_asyncio

from cryptozavr.application.risk.risk_policy import (
    LimitDecimal,
    LimitInt,
    RiskPolicy,
)
from cryptozavr.domain.risk import Severity
from cryptozavr.infrastructure.persistence.risk_policy_repo import (
    RiskPolicyRepository,
)

pytestmark = pytest.mark.integration


def _make_policy(*, leverage: str = "3") -> RiskPolicy:
    return RiskPolicy(
        max_leverage=LimitDecimal(value=Decimal(leverage), severity=Severity.DENY),
        max_position_pct=LimitDecimal(value=Decimal("0.25"), severity=Severity.DENY),
        max_daily_loss_pct=LimitDecimal(value=Decimal("0.05"), severity=Severity.WARN),
        cooldown_after_n_losses=LimitInt(value=3, severity=Severity.WARN),
        min_balance_buffer=LimitDecimal(value=Decimal("100"), severity=Severity.DENY),
    )


@pytest_asyncio.fixture
async def clean_risk_policies(supabase_pool: asyncpg.Pool) -> AsyncIterator[None]:
    """Truncate risk_policies between tests so each case starts empty."""
    async with supabase_pool.acquire() as conn:
        await conn.execute(
            "truncate table cryptozavr.risk_policies restart identity cascade",
        )
    yield


@pytest_asyncio.fixture
async def risk_repo(
    supabase_pool: asyncpg.Pool,
) -> AsyncIterator[RiskPolicyRepository]:
    yield RiskPolicyRepository(pool=supabase_pool)


async def test_save_then_get_active_returns_row(
    risk_repo: RiskPolicyRepository,
    clean_risk_policies: None,
) -> None:
    policy = _make_policy()
    policy_id = await risk_repo.save(policy)
    await risk_repo.activate(policy_id)

    row = await risk_repo.get_active()
    assert row is not None
    assert row.id == policy_id
    assert row.is_active is True
    assert row.policy.max_leverage.value == Decimal("3")
    # activated_at trigger fires on the UPDATE is_active transition.
    assert row.activated_at_ms is not None


async def test_save_twice_same_policy_returns_same_id(
    risk_repo: RiskPolicyRepository,
    clean_risk_policies: None,
) -> None:
    policy = _make_policy()
    id_a = await risk_repo.save(policy)
    id_b = await risk_repo.save(policy)
    assert id_a == id_b
    history = await risk_repo.list_history(limit=10)
    assert len(history) == 1


async def test_activate_transitions_active_row(
    risk_repo: RiskPolicyRepository,
    clean_risk_policies: None,
    supabase_pool: asyncpg.Pool,
) -> None:
    id_a = await risk_repo.save(_make_policy(leverage="3"))
    id_b = await risk_repo.save(_make_policy(leverage="5"))

    await risk_repo.activate(id_a)
    assert (await risk_repo.get_active()).id == id_a  # type: ignore[union-attr]

    await risk_repo.activate(id_b)
    row = await risk_repo.get_active()
    assert row is not None
    assert row.id == id_b

    # Exactly one row has is_active=true (partial unique index enforces this).
    async with supabase_pool.acquire() as conn:
        count = await conn.fetchval(
            "select count(*) from cryptozavr.risk_policies where is_active = true",
        )
    assert count == 1
