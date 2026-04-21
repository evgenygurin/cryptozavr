"""Test Settings load from environment variables."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cryptozavr.mcp.settings import Mode, Settings


def test_settings_defaults_with_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings must load with minimal required env (SUPABASE_* placeholders)."""
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "local-dev-key")
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
    )

    settings = Settings()

    assert settings.supabase_url == "http://127.0.0.1:54321"
    assert settings.supabase_service_role_key == "local-dev-key"
    assert settings.mode == Mode.RESEARCH_ONLY
    assert settings.log_level == "INFO"


def test_settings_mode_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """CRYPTOZAVR_MODE env overrides default mode."""
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "local-dev-key")
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
    )
    monkeypatch.setenv("CRYPTOZAVR_MODE", "research_only")

    settings = Settings()

    assert settings.mode == Mode.RESEARCH_ONLY


def test_settings_invalid_mode_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid mode value raises ValidationError."""
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "local-dev-key")
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
    )
    monkeypatch.setenv("CRYPTOZAVR_MODE", "cowboy_mode")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_missing_required_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing SUPABASE_URL raises ValidationError.

    Passes `_env_file=None` so pydantic-settings skips the local `.env`
    (which is populated from the cloud project in integration workflows).
    """
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "local-dev-key")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
