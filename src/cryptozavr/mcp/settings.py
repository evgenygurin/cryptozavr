"""Pydantic Settings for cryptozavr MCP server.

All configuration comes from env vars (prefixed CRYPTOZAVR_ or SUPABASE_).
Loaded once at server startup.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(StrEnum):
    """Operational mode governing which capabilities are available.

    MVP supports only RESEARCH_ONLY. Other modes are reserved for future phases.
    """

    RESEARCH_ONLY = "research_only"
    PAPER_TRADING = "paper_trading"
    APPROVAL_GATED_LIVE = "approval_gated_live"
    POLICY_CONSTRAINED_AUTO_LIVE = "policy_constrained_auto_live"


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Supabase ---
    supabase_url: str = Field(
        alias="SUPABASE_URL",
        description="Supabase REST endpoint, e.g. http://127.0.0.1:54321 (local) or cloud URL.",
    )
    supabase_service_role_key: str = Field(
        alias="SUPABASE_SERVICE_ROLE_KEY",
        description="Service role key — bypasses RLS. Keep out of git.",
    )
    supabase_db_url: str = Field(
        alias="SUPABASE_DB_URL",
        description="Direct Postgres connection string for asyncpg hot-path.",
    )

    # --- cryptozavr runtime ---
    mode: Mode = Field(
        default=Mode.RESEARCH_ONLY,
        alias="CRYPTOZAVR_MODE",
        description="Operational mode. MVP locks this to research_only.",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        alias="CRYPTOZAVR_LOG_LEVEL",
    )
    paper_bankroll_initial: Decimal = Field(
        default=Decimal("10000"),
        description="Starting paper-trading bankroll in quote currency (USDT).",
    )
