"""Test value objects."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.value_objects import Instant, Timeframe, TimeRange


class TestTimeframe:
    def test_all_values_exposed(self) -> None:
        assert Timeframe.M1.value == "1m"
        assert Timeframe.M5.value == "5m"
        assert Timeframe.M15.value == "15m"
        assert Timeframe.M30.value == "30m"
        assert Timeframe.H1.value == "1h"
        assert Timeframe.H4.value == "4h"
        assert Timeframe.D1.value == "1d"
        assert Timeframe.W1.value == "1w"

    @pytest.mark.parametrize(
        ("tf", "expected_ms"),
        [
            (Timeframe.M1, 60_000),
            (Timeframe.M5, 300_000),
            (Timeframe.M15, 900_000),
            (Timeframe.M30, 1_800_000),
            (Timeframe.H1, 3_600_000),
            (Timeframe.H4, 14_400_000),
            (Timeframe.D1, 86_400_000),
            (Timeframe.W1, 604_800_000),
        ],
    )
    def test_to_milliseconds(self, tf: Timeframe, expected_ms: int) -> None:
        assert tf.to_milliseconds() == expected_ms

    def test_to_ccxt_string(self) -> None:
        assert Timeframe.H1.to_ccxt_string() == "1h"
        assert Timeframe.D1.to_ccxt_string() == "1d"

    def test_parse_valid(self) -> None:
        assert Timeframe.parse("1h") == Timeframe.H1
        assert Timeframe.parse("5m") == Timeframe.M5

    def test_parse_invalid_raises_ValidationError(self) -> None:
        with pytest.raises(ValidationError):
            Timeframe.parse("3m")


class TestInstant:
    def test_accepts_utc_datetime(self) -> None:
        dt = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
        inst = Instant(dt)
        assert inst.to_datetime() == dt

    def test_rejects_naive_datetime(self) -> None:
        naive = datetime(2026, 4, 21, 10, 0, 0)
        with pytest.raises(ValidationError):
            Instant(naive)

    def test_from_ms_roundtrip(self) -> None:
        ms = 1_745_200_800_000
        inst = Instant.from_ms(ms)
        assert inst.to_ms() == ms

    def test_from_iso(self) -> None:
        inst = Instant.from_iso("2026-04-21T10:00:00+00:00")
        assert inst.to_datetime().year == 2026
        assert inst.to_datetime().tzinfo is not None

    def test_isoformat(self) -> None:
        inst = Instant.from_ms(1_745_200_800_000)
        assert "T" in inst.isoformat()
        assert inst.isoformat().endswith("+00:00")

    def test_now_returns_timezone_aware(self) -> None:
        inst = Instant.now()
        assert inst.to_datetime().tzinfo is not None

    def test_equality_and_hash(self) -> None:
        a = Instant.from_ms(1000)
        b = Instant.from_ms(1000)
        c = Instant.from_ms(2000)
        assert a == b
        assert hash(a) == hash(b)
        assert a != c

    def test_ordering(self) -> None:
        earlier = Instant.from_ms(1000)
        later = Instant.from_ms(2000)
        assert earlier < later
        assert later > earlier
        assert earlier <= Instant.from_ms(1000)

    @given(st.integers(min_value=0, max_value=2_000_000_000_000))
    def test_from_ms_to_ms_roundtrip_property(self, ms: int) -> None:
        assert Instant.from_ms(ms).to_ms() == ms


class TestTimeRange:
    def test_happy_path(self) -> None:
        start = Instant.from_ms(1000)
        end = Instant.from_ms(2000)
        tr = TimeRange(start=start, end=end)
        assert tr.start == start
        assert tr.end == end

    def test_rejects_end_not_after_start(self) -> None:
        same = Instant.from_ms(1000)
        with pytest.raises(ValidationError):
            TimeRange(start=same, end=same)

        with pytest.raises(ValidationError):
            TimeRange(start=Instant.from_ms(2000), end=Instant.from_ms(1000))

    def test_duration_ms(self) -> None:
        tr = TimeRange(start=Instant.from_ms(1000), end=Instant.from_ms(3500))
        assert tr.duration_ms() == 2500

    def test_contains(self) -> None:
        tr = TimeRange(start=Instant.from_ms(1000), end=Instant.from_ms(3000))
        assert tr.contains(Instant.from_ms(1000))
        assert tr.contains(Instant.from_ms(2000))
        assert not tr.contains(Instant.from_ms(3000))
        assert not tr.contains(Instant.from_ms(500))
        assert not tr.contains(Instant.from_ms(4000))

    def test_estimate_bars(self) -> None:
        hour_range = TimeRange(
            start=Instant.from_ms(0),
            end=Instant.from_ms(3_600_000 * 10),
        )
        assert hour_range.estimate_bars(Timeframe.H1) == 10
        assert hour_range.estimate_bars(Timeframe.M30) == 20
