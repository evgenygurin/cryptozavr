"""RiskPolicyRepository — asyncpg-backed persistence for risk_policies.

Canonical JSON + BLAKE2b content_hash dedupes repeat saves. Insert-only
history; partial unique index on `is_active = true` guarantees exactly
one active row. Activation is transactional — the table trigger stamps
`activated_at` on the 0→1 is_active flip.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg
from pydantic import ValidationError

from cryptozavr.application.risk.risk_policy import RiskPolicy


@dataclass(frozen=True, slots=True)
class RiskPolicyRow:
    """Repository-layer view of a risk_policies row.

    Not an MCP DTO — tools translate this into the wire-format
    RiskPolicyPayload envelope.
    """

    id: UUID
    policy: RiskPolicy
    is_active: bool
    created_at_ms: int
    activated_at_ms: int | None


class RiskPolicyRepository:
    """CRUD for cryptozavr.risk_policies.

    Shares the single asyncpg pool wired in `mcp/bootstrap.py` — no new
    connections, no cache, no events.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save(self, policy: RiskPolicy) -> UUID:
        """Insert the policy (is_active=false). Upsert on content_hash returns
        the pre-existing id so save() is idempotent per canonical JSON."""
        canonical = _canonical_policy_json(policy)
        chash = _content_hash(canonical)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                insert into cryptozavr.risk_policies (policy_json, content_hash)
                values ($1::jsonb, $2)
                on conflict (content_hash) do update
                  set content_hash = excluded.content_hash
                returning id
                """,
                canonical,
                chash,
            )
        assert row is not None, "upsert must return a row"
        return _as_uuid(row["id"])

    async def activate(self, policy_id: UUID) -> None:
        """Transaction: deactivate all active rows + activate the target row.

        Raises LookupError if the target id does not exist (second UPDATE
        affected 0 rows).
        """
        async with self._pool.acquire() as conn, conn.transaction():
            await conn.execute(
                "update cryptozavr.risk_policies set is_active = false where is_active = true",
            )
            result: str = await conn.execute(
                "update cryptozavr.risk_policies set is_active = true where id = $1",
                policy_id,
            )
        if result != "UPDATE 1":
            raise LookupError(
                f"RiskPolicyRepository.activate: id {policy_id} not found",
            )

    async def save_and_activate(self, policy: RiskPolicy) -> UUID:
        """Atomic insert-or-upsert + activation in one transaction.

        Prevents orphan rows if the activate phase fails after save. If the
        policy already exists (content_hash collision), returns the existing
        id and still activates it.
        """
        canonical = _canonical_policy_json(policy)
        chash = _content_hash(canonical)
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """
                insert into cryptozavr.risk_policies (policy_json, content_hash)
                values ($1::jsonb, $2)
                on conflict (content_hash) do update
                  set content_hash = excluded.content_hash
                returning id
                """,
                canonical,
                chash,
            )
            assert row is not None, "upsert must return a row"
            policy_id = _as_uuid(row["id"])
            await conn.execute(
                "update cryptozavr.risk_policies set is_active = false where is_active = true",
            )
            result: str = await conn.execute(
                "update cryptozavr.risk_policies set is_active = true where id = $1",
                policy_id,
            )
        if result != "UPDATE 1":
            raise LookupError(
                f"RiskPolicyRepository.save_and_activate: id {policy_id} missing "
                "after insert (should be impossible)",
            )
        return policy_id

    async def get_active(self) -> RiskPolicyRow | None:
        """Return the single active row or None."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select id, policy_json, is_active, created_at, activated_at
                  from cryptozavr.risk_policies
                 where is_active = true
                """,
            )
        return _row_to_domain(row) if row is not None else None

    async def list_history(self, *, limit: int = 50) -> list[RiskPolicyRow]:
        """Newest-first slice of the history."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select id, policy_json, is_active, created_at, activated_at
                  from cryptozavr.risk_policies
                 order by created_at desc
                 limit $1
                """,
                limit,
            )
        return [_row_to_domain(r) for r in rows]


# ----------------------------- helpers ---------------------------------------


def _canonical_policy_json(policy: RiskPolicy) -> str:
    """Deterministic JSON string for hashing (sort_keys + compact separators)."""
    return json.dumps(
        policy.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )


def _content_hash(canonical_json: str) -> str:
    """BLAKE2b-32 hex digest of the canonical JSON."""
    return hashlib.blake2b(canonical_json.encode("utf-8"), digest_size=32).hexdigest()


def _row_to_domain(row: Any) -> RiskPolicyRow:
    """Map an asyncpg Record to the repo-layer dataclass.

    asyncpg returns jsonb either as a str (no codec registered) or as an
    already-parsed dict depending on server setup; we normalise both.
    On corrupt jsonb / mismatched schema, the row id is surfaced so
    operators can locate and fix the offending record.
    """
    row_id = row["id"]
    try:
        raw = row["policy_json"]
        policy_dict = json.loads(raw) if isinstance(raw, str) else raw
        activated_at = row["activated_at"]
        return RiskPolicyRow(
            id=_as_uuid(row_id),
            policy=RiskPolicy.model_validate(policy_dict),
            is_active=bool(row["is_active"]),
            created_at_ms=_dt_to_ms(row["created_at"]),
            activated_at_ms=_dt_to_ms(activated_at) if activated_at is not None else None,
        )
    except (json.JSONDecodeError, ValidationError) as exc:
        raise RuntimeError(
            f"corrupt risk_policies row id={row_id}: {type(exc).__name__}: {exc}",
        ) from exc


def _dt_to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _as_uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
