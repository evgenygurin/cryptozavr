"""asyncpg Pool factory wrapper.

One Pool per process (Singleton via DI). Lifespan managed by the application
(FastMCP startup/shutdown hooks in L5).
"""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg


@dataclass(frozen=True, slots=True)
class PgPoolConfig:
    """Connection-pool sizing and timeouts for asyncpg.

    `max_size=25` absorbs parallel tool bursts (up to ~12 concurrent
    calls each doing 2 acquires for cache-read + write-through).
    `command_timeout=15s` and `acquire_timeout=2s` ensure that a
    slow Supabase query or a saturated pool fails fast rather than
    stalling the whole event loop — stdio MCP clients treat long
    hangs as dead subprocesses.
    """

    dsn: str
    min_size: int = 2
    max_size: int = 25
    max_inactive_connection_lifetime: float = 60.0
    command_timeout: float = 15.0
    acquire_timeout: float = 2.0


async def create_pool(config: PgPoolConfig) -> asyncpg.Pool:
    """Create an asyncpg.Pool. Caller is responsible for awaiting pool.close()."""
    return await asyncpg.create_pool(
        dsn=config.dsn,
        min_size=config.min_size,
        max_size=config.max_size,
        max_inactive_connection_lifetime=config.max_inactive_connection_lifetime,
        command_timeout=config.command_timeout,
        timeout=config.acquire_timeout,
    )
