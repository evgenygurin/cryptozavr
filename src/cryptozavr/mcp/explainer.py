"""SessionExplainer — envelope builder for tool responses.

Per spec (cryptozavr-mvp-design.md §5), every tool response can be
wrapped in a ``{data, quality, reasoning}`` envelope. This module
provides a tiny, stateless helper — no class hierarchy, no dependency
injection. Tools call ``build_envelope(data, quality, reason_codes)``
and return the resulting dict (or a Pydantic wrapper).

By design the helper is PERMISSIVE about the ``data`` field: it accepts
Pydantic BaseModels, plain dicts, or any JSON-serialisable value and
leaves the caller in charge of shape. This keeps existing tools
(ticker/ohlcv/...) untouched — only new tools opt in to the envelope.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from cryptozavr.domain.quality import DataQuality


def _quality_payload(quality: DataQuality) -> dict[str, Any]:
    return {
        "source": str(quality.source),
        "fetched_at_ms": quality.fetched_at.to_ms(),
        "staleness": quality.staleness.value,
        "confidence": quality.confidence.value,
        "cache_hit": quality.cache_hit,
    }


def new_query_id() -> str:
    """Short, URL-safe identifier for correlating a tool call to its audit trail."""
    return uuid4().hex[:12]


def build_envelope(
    *,
    data: Any,
    quality: DataQuality | None,
    reason_codes: list[str],
    query_id: str | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    """Wrap tool output in the canonical ``{data, quality, reasoning}`` envelope.

    Args:
        data: the primary payload. Pydantic BaseModels are dumped via
            ``model_dump(mode="json")``; everything else is passed through
            as-is (caller is responsible for JSON-serialisability).
        quality: optional DataQuality. When absent, ``quality`` field is
            omitted from the envelope so clients can distinguish
            "unknown quality" from "quality=fresh, confidence=unknown".
        reason_codes: chain-of-responsibility audit trail.
        query_id: client-provided id; defaults to a fresh 12-char hex.
        notes: free-form caveats to surface to the LLM (e.g. "approximate
            due to cache miss on upstream").
    """
    if hasattr(data, "model_dump"):
        data_payload: Any = data.model_dump(mode="json")
    else:
        data_payload = data
    envelope: dict[str, Any] = {
        "data": data_payload,
        "reasoning": {
            "query_id": query_id or new_query_id(),
            "chain_decisions": list(reason_codes),
            "notes": list(notes or []),
        },
    }
    if quality is not None:
        envelope["quality"] = _quality_payload(quality)
    return envelope
