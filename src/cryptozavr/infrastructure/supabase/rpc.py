"""Typed RPC wrappers — stub for M2.2.

First real RPC lands in phase 2 with pgvector similarity search (match_regimes,
match_similar_strategies). See MVP design spec section 11 phase 2.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


class RpcClient:
    """Stub: raises NotImplementedError in M2.2. Populated in phase 2+."""

    async def match_regimes(
        self,
        embedding: Sequence[float],
        threshold: float,
        limit: int,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "match_regimes RPC arrives in phase 2 alongside pgvector activation."
        )
