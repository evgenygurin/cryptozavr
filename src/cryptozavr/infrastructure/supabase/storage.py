"""Supabase Storage wrapper — stub for M2.2.

Full implementation (upload/download backtest reports, exported OHLCV)
lands in phase 2+ per MVP design spec section 5 Storage subsection.
"""

from __future__ import annotations


class StorageClient:
    """Stub: raises NotImplementedError in M2.2. Populated in phase 2+."""

    async def upload(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str,
    ) -> str:
        raise NotImplementedError("Storage uploads arrive in phase 2+ for backtest artefacts.")

    async def get_signed_url(self, bucket: str, key: str, expires_sec: int) -> str:
        raise NotImplementedError("Signed URLs arrive in phase 2+.")
