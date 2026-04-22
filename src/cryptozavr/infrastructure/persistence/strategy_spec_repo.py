"""StrategySpecRepository — asyncpg-backed CRUD for cryptozavr.strategy_specs.

Shares the existing SupabaseGateway `_pool` (single pool per server, single
connection lifecycle). Pure CRUD: no cache, no events. Upsert keyed on
`content_hash` so re-saving an identical spec returns the existing id —
save() is idempotent w.r.t. canonical JSON.

pgvector + asyncpg note: asyncpg has no built-in codec for `vector`. The
cleanest MVP route is to bind the embedding as a text literal cast via
`$N::extensions.vector` — avoids adding the `pgvector` python dep and its
async codec registration. If the cast breaks in integration, revisit.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from cryptozavr.infrastructure.persistence.embedding import placeholder_embedding
from cryptozavr.mcp.tools.strategy_dtos import StrategySpecPayload


@dataclass(frozen=True, slots=True)
class StoredStrategyRow:
    """Repository-layer view of a strategy_specs row (not an MCP DTO)."""

    id: UUID
    name: str
    version: int
    venue_id: str
    symbol_native: str
    timeframe: str
    created_at_ms: int
    updated_at_ms: int


class StrategySpecRepository:
    """CRUD + similarity over cryptozavr.strategy_specs.

    Embedding is generated inside `save()` via the deterministic placeholder
    — callers pass only the StrategySpecPayload. A real-embedding followup
    will either override the placeholder call-site or accept a pre-computed
    vector argument; the storage contract stays unchanged.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save(self, spec: StrategySpecPayload) -> UUID:
        """Upsert spec; return the row id (new or existing by content_hash)."""
        canonical = _canonical_spec_json(spec)
        chash = _content_hash(canonical)
        emb_literal = _vector_literal(placeholder_embedding(canonical))
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                insert into cryptozavr.strategy_specs (
                  name, version, venue_id, symbol_native, timeframe,
                  spec_json, content_hash, embedding
                )
                values ($1, $2, $3, $4, $5, $6::jsonb, $7, $8::extensions.vector)
                on conflict (content_hash) do update set
                  updated_at = now()
                returning id
                """,
                spec.name,
                spec.version,
                spec.venue.value,
                spec.symbol.native_symbol,
                spec.timeframe.value,
                canonical,
                chash,
                emb_literal,
            )
        assert row is not None, "upsert must return a row"
        return _as_uuid(row["id"])

    async def list_recent(self, *, limit: int = 50) -> list[StoredStrategyRow]:
        """List up to `limit` most recent strategies (summary view, no JSON)."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select id, name, version, venue_id, symbol_native, timeframe,
                       created_at, updated_at
                  from cryptozavr.strategy_specs
                 order by created_at desc
                 limit $1
                """,
                limit,
            )
        return [
            StoredStrategyRow(
                id=_as_uuid(r["id"]),
                name=str(r["name"]),
                version=int(r["version"]),
                venue_id=str(r["venue_id"]),
                symbol_native=str(r["symbol_native"]),
                timeframe=str(r["timeframe"]),
                created_at_ms=_dt_to_ms(r["created_at"]),
                updated_at_ms=_dt_to_ms(r["updated_at"]),
            )
            for r in rows
        ]

    async def get(self, spec_id: UUID) -> StrategySpecPayload | None:
        """Fetch spec JSON by id; return a parsed StrategySpecPayload.

        asyncpg returns jsonb columns as either a str (no codec registered)
        or as an already-parsed dict depending on server setup — we handle
        both via `model_validate` / `model_validate_json`.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "select spec_json from cryptozavr.strategy_specs where id = $1",
                spec_id,
            )
        if row is None:
            return None
        raw = row["spec_json"]
        if isinstance(raw, str):
            return StrategySpecPayload.model_validate_json(raw)
        return StrategySpecPayload.model_validate(raw)

    async def delete(self, spec_id: UUID) -> bool:
        """Delete by id; return True if exactly one row was removed."""
        async with self._pool.acquire() as conn:
            result: str = await conn.execute(
                "delete from cryptozavr.strategy_specs where id = $1",
                spec_id,
            )
        return result == "DELETE 1"


# ----------------------------- helpers ---------------------------------------


def _canonical_spec_json(spec: StrategySpecPayload) -> str:
    """Deterministic JSON string for hashing (`sort_keys` + compact separators)."""
    return json.dumps(
        spec.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )


def _content_hash(canonical_json: str) -> str:
    """BLAKE2b-32 hex digest of the canonical JSON."""
    return hashlib.blake2b(canonical_json.encode("utf-8"), digest_size=32).hexdigest()


def _vector_literal(floats: list[float]) -> str:
    """Render a float list as pgvector text literal: `[f1,f2,...]`.

    asyncpg binds this as TEXT and the SQL cast `::extensions.vector` parses
    it into the proper pgvector value. Keep the format lean — no spaces, 8
    decimal places is enough for unit-normalised placeholder vectors.
    """
    return "[" + ",".join(f"{f:.8f}" for f in floats) + "]"


def _dt_to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _as_uuid(value: object) -> UUID:
    """Normalise asyncpg's UUID-or-str to UUID."""
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
