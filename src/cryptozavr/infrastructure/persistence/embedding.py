"""Placeholder embedding for StrategySpec.

MVP ships a deterministic BLAKE2b-derived 384-float vector. Real embeddings
(OpenAI / Voyage / local sentence-transformers) land in a follow-up when the
schema + semantics are stable. The placeholder is meaningless for similarity
— but it populates the column, exercises the IVFFLAT index, and keeps the
shape of the Supabase RPC contract honest.

BLAKE2b at 64 bytes gives us 16 float32s per hash. We chain hashes until we
have 384 * 4 = 1536 bytes, then reinterpret as little-endian f32 and
L2-normalise so the vector lives on the unit sphere (pgvector L2 / cosine
behave sensibly with unit vectors, and the RPC uses L2 distance).
"""

from __future__ import annotations

import hashlib
import math
import struct

EMBEDDING_DIM = 384


def placeholder_embedding(canonical_json: str) -> list[float]:
    """Return a deterministic 384-float unit vector derived from spec JSON."""
    seed = canonical_json.encode("utf-8")
    buf = b""
    i = 0
    while len(buf) < EMBEDDING_DIM * 4:
        h = hashlib.blake2b(seed + i.to_bytes(4, "little"), digest_size=64)
        buf += h.digest()
        i += 1
    floats = list(struct.unpack(f"<{EMBEDDING_DIM}f", buf[: EMBEDDING_DIM * 4]))
    # Replace NaN / inf — hashlib occasionally produces patterns that decode
    # to NaN/inf in float32. Use zero; the normalisation step handles the
    # division-by-zero case by returning a zero vector.
    floats = [0.0 if math.isnan(f) or math.isinf(f) else f for f in floats]
    norm = sum(f * f for f in floats) ** 0.5
    if norm == 0.0:
        return [0.0] * EMBEDDING_DIM
    return [f / norm for f in floats]
