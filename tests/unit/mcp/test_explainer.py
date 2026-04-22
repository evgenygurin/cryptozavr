"""Unit tests for SessionExplainer helper."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.value_objects import Instant
from cryptozavr.mcp.explainer import build_envelope, new_query_id


class _DummyDTO(BaseModel):
    name: str
    price: Decimal


def _quality() -> DataQuality:
    return DataQuality(
        source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
        fetched_at=Instant.from_ms(1_700_000_000_000),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=True,
    )


class TestBuildEnvelope:
    def test_wraps_pydantic_dto_via_model_dump(self) -> None:
        dto = _DummyDTO(name="BTC", price=Decimal("100000.5"))
        env = build_envelope(data=dto, quality=_quality(), reason_codes=["cache:hit"])
        assert env["data"] == {"name": "BTC", "price": "100000.5"}
        assert env["quality"]["source"] == "kucoin:fetch_ticker"
        assert env["quality"]["staleness"] == "fresh"
        assert env["quality"]["cache_hit"] is True
        assert env["reasoning"]["chain_decisions"] == ["cache:hit"]
        assert len(env["reasoning"]["query_id"]) == 12

    def test_passes_dicts_through_untouched(self) -> None:
        env = build_envelope(
            data={"foo": "bar"},
            quality=_quality(),
            reason_codes=[],
        )
        assert env["data"] == {"foo": "bar"}

    def test_omits_quality_when_none(self) -> None:
        env = build_envelope(data={"x": 1}, quality=None, reason_codes=["no-data"])
        assert "quality" not in env
        assert env["reasoning"]["chain_decisions"] == ["no-data"]

    def test_respects_explicit_query_id_and_notes(self) -> None:
        env = build_envelope(
            data={"ok": True},
            quality=None,
            reason_codes=[],
            query_id="fixed-id-000",
            notes=["approximate upstream read", "retry:1"],
        )
        assert env["reasoning"]["query_id"] == "fixed-id-000"
        assert env["reasoning"]["notes"] == [
            "approximate upstream read",
            "retry:1",
        ]

    def test_new_query_id_is_short_and_unique(self) -> None:
        ids = {new_query_id() for _ in range(50)}
        assert len(ids) == 50
        assert all(len(qid) == 12 for qid in ids)
