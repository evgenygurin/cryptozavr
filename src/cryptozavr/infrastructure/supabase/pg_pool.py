"""asyncpg Pool factory wrapper.

One Pool per process (Singleton via DI). Lifespan managed by the application
(FastMCP startup/shutdown hooks in L5).
"""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg


@dataclass(frozen=True, slots=True)
class PgPoolConfig:
    """Connection-pool sizing and timeouts for asyncpg."""

    dsn: str
    min_size: int = 1
    max_size: int = 10
    max_inactive_connection_lifetime: float = 60.0
    command_timeout: float = 30.0


async def create_pool(config: PgPoolConfig) -> asyncpg.Pool:
    """Create an asyncpg.Pool. Caller is responsible for awaiting pool.close()."""
    return await asyncpg.create_pool(
        dsn=config.dsn,
        min_size=config.min_size,
        max_size=config.max_size,
        max_inactive_connection_lifetime=config.max_inactive_connection_lifetime,
        command_timeout=config.command_timeout,
    )
