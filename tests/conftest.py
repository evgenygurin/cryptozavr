"""Global pytest fixtures for cryptozavr test suite."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Ensure each test starts with a clean env for CRYPTOZAVR_/SUPABASE_ vars.

    This prevents developer's local .env from leaking into unit tests.
    Integration tests can opt back in by setting vars explicitly via monkeypatch.
    """
    for key in list(os.environ.keys()):
        if key.startswith(("CRYPTOZAVR_", "SUPABASE_", "KUCOIN_", "COINGECKO_")):
            monkeypatch.delenv(key, raising=False)
    return
