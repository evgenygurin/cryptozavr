"""Test asyncpg Pool factory configuration and lifecycle."""

from __future__ import annotations

import pytest

from cryptozavr.infrastructure.supabase.pg_pool import PgPoolConfig, create_pool


class TestPgPoolConfig:
    def test_defaults(self) -> None:
        cfg = PgPoolConfig(dsn="postgresql://user:pw@host:5432/db")
        assert cfg.dsn == "postgresql://user:pw@host:5432/db"
        assert cfg.min_size == 1
        assert cfg.max_size == 10
        assert cfg.max_inactive_connection_lifetime == 60.0
        assert cfg.command_timeout == 30.0

    def test_custom(self) -> None:
        cfg = PgPoolConfig(
            dsn="postgresql://u:p@h/d",
            min_size=5,
            max_size=20,
            max_inactive_connection_lifetime=120.0,
            command_timeout=10.0,
        )
        assert cfg.min_size == 5
        assert cfg.max_size == 20
        assert cfg.max_inactive_connection_lifetime == 120.0
        assert cfg.command_timeout == 10.0


@pytest.mark.asyncio
async def test_create_pool_invalid_dsn_raises() -> None:
    """Invalid DSN must surface as an exception from asyncpg."""
    cfg = PgPoolConfig(dsn="postgresql://invalid:invalid@127.0.0.1:1/nowhere")
    with pytest.raises(ConnectionRefusedError, match="Connect call failed"):
        await create_pool(cfg)
