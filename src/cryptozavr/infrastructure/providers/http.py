"""HttpClientRegistry: one httpx.AsyncClient per venue.

Lifecycle managed by caller (FastMCP startup/shutdown hooks in L5).
DI-singleton via composition root.
"""

from __future__ import annotations

import asyncio

import httpx


class HttpClientRegistry:
    """Keyed pool of httpx.AsyncClient instances.

    After close_all(), re-issuing get() for a venue creates a fresh client.
    """

    def __init__(self, default_timeout: float = 30.0) -> None:
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._default_timeout = default_timeout
        self._lock = asyncio.Lock()

    async def get(self, venue_id: str, *, base_url: str) -> httpx.AsyncClient:
        """Return the cached client for venue_id, or create one."""
        async with self._lock:
            existing = self._clients.get(venue_id)
            if existing is not None and not existing.is_closed:
                return existing
            client = httpx.AsyncClient(
                base_url=base_url,
                timeout=self._default_timeout,
            )
            self._clients[venue_id] = client
            return client

    async def close_all(self) -> None:
        """Close every registered client and clear the registry."""
        async with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            if not client.is_closed:
                await client.aclose()
