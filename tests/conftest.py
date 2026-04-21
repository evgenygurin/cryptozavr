"""Global pytest fixtures for cryptozavr test suite."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Ensure each test starts with a clean env for CRYPTOZAVR_/SUPABASE_ vars.

    This prevents the developer's local .env from leaking into unit tests.
    Integration tests (marker `integration`) keep env intact — they need
    SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / SUPABASE_DB_URL to reach
    the live cloud stack.
    """
    if request.node.get_closest_marker("integration") is not None:
        return
    for key in list(os.environ.keys()):
        if key.startswith(("CRYPTOZAVR_", "SUPABASE_", "KUCOIN_", "COINGECKO_")):
            monkeypatch.delenv(key, raising=False)
    return
