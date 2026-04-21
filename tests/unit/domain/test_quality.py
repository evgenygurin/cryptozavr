"""Test quality / provenance value objects."""

from __future__ import annotations

import pytest

from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.value_objects import Instant


class TestStaleness:
    def test_ordering(self) -> None:
        assert Staleness.FRESH < Staleness.RECENT
        assert Staleness.RECENT < Staleness.STALE
        assert Staleness.STALE < Staleness.EXPIRED

    def test_values(self) -> None:
        assert Staleness.FRESH.value == "fresh"
        assert Staleness.EXPIRED.value == "expired"


class TestConfidence:
    def test_values(self) -> None:
        assert Confidence.HIGH.value == "high"
        assert Confidence.UNKNOWN.value == "unknown"


class TestProvenance:
    def test_happy_path(self) -> None:
        p = Provenance(venue_id="kucoin", endpoint="fetch_ticker")
        assert p.venue_id == "kucoin"
        assert p.endpoint == "fetch_ticker"

    def test_str_representation(self) -> None:
        p = Provenance(venue_id="kucoin", endpoint="fetch_ohlcv")
        assert str(p) == "kucoin:fetch_ohlcv"


class TestDataQuality:
    def test_happy_path(self) -> None:
        fetched = Instant.now()
        q = DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
            fetched_at=fetched,
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        )
        assert q.staleness == Staleness.FRESH
        assert q.confidence == Confidence.HIGH
        assert q.cache_hit is False
        assert q.fetched_at == fetched

    def test_immutable(self) -> None:
        q = DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="e"),
            fetched_at=Instant.now(),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        )
        with pytest.raises(AttributeError):
            q.cache_hit = True  # type: ignore[misc]
