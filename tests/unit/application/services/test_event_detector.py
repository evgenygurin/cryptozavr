from decimal import Decimal

import pytest

from cryptozavr.application.services.position_watcher import EventDetector
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.domain.watch import EventType, WatchSide, WatchState


@pytest.fixture
def btc_symbol():
    reg = SymbolRegistry()
    return reg.get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


def _long_state(symbol, stop=Decimal("95"), take=Decimal("110")) -> WatchState:
    return WatchState(
        watch_id="w",
        symbol=symbol,
        side=WatchSide.LONG,
        entry=Decimal("100"),
        stop=stop,
        take=take,
        size_quote=None,
        started_at_ms=1_000,
        max_duration_sec=3600,
    )


def _short_state(symbol, stop=Decimal("105"), take=Decimal("90")) -> WatchState:
    return WatchState(
        watch_id="w",
        symbol=symbol,
        side=WatchSide.SHORT,
        entry=Decimal("100"),
        stop=stop,
        take=take,
        size_quote=None,
        started_at_ms=1_000,
        max_duration_sec=3600,
    )


class TestTerminalEventsLong:
    def test_stop_hit(self, btc_symbol) -> None:
        state = _long_state(btc_symbol)
        events = EventDetector.detect(state, price=Decimal("95"), now_ms=2_000)
        assert any(e.type is EventType.STOP_HIT for e in events)

    def test_take_hit(self, btc_symbol) -> None:
        state = _long_state(btc_symbol)
        events = EventDetector.detect(state, price=Decimal("110"), now_ms=2_000)
        assert any(e.type is EventType.TAKE_HIT for e in events)

    def test_timeout_when_deadline_passed(self, btc_symbol) -> None:
        state = _long_state(btc_symbol)
        deadline = state.started_at_ms + state.max_duration_sec * 1000
        events = EventDetector.detect(state, price=Decimal("100"), now_ms=deadline + 1)
        assert any(e.type is EventType.TIMEOUT for e in events)


class TestTerminalEventsShort:
    def test_stop_hit_short(self, btc_symbol) -> None:
        state = _short_state(btc_symbol)
        events = EventDetector.detect(state, price=Decimal("105"), now_ms=2_000)
        assert any(e.type is EventType.STOP_HIT for e in events)

    def test_take_hit_short(self, btc_symbol) -> None:
        state = _short_state(btc_symbol)
        events = EventDetector.detect(state, price=Decimal("90"), now_ms=2_000)
        assert any(e.type is EventType.TAKE_HIT for e in events)


class TestApproachEvents:
    def test_price_approaches_stop_long(self, btc_symbol) -> None:
        state = _long_state(btc_symbol, stop=Decimal("95"))
        events = EventDetector.detect(state, price=Decimal("95.4"), now_ms=2_000)
        types = [e.type for e in events]
        assert EventType.PRICE_APPROACHES_STOP in types

    def test_price_approaches_take_long(self, btc_symbol) -> None:
        state = _long_state(btc_symbol, take=Decimal("110"))
        events = EventDetector.detect(state, price=Decimal("109.5"), now_ms=2_000)
        types = [e.type for e in events]
        assert EventType.PRICE_APPROACHES_TAKE in types

    def test_approach_fires_once(self, btc_symbol) -> None:
        state = _long_state(btc_symbol, stop=Decimal("95"))
        first = EventDetector.detect(state, price=Decimal("95.4"), now_ms=2_000)
        state._fired_non_terminal.update(e.type for e in first)
        second = EventDetector.detect(state, price=Decimal("95.4"), now_ms=2_001)
        assert all(e.type is not EventType.PRICE_APPROACHES_STOP for e in second)


class TestBreakeven:
    def test_breakeven_long(self, btc_symbol) -> None:
        state = _long_state(btc_symbol, stop=Decimal("95"))
        events = EventDetector.detect(state, price=Decimal("105"), now_ms=2_000)
        assert any(e.type is EventType.BREAKEVEN_REACHED for e in events)

    def test_breakeven_short(self, btc_symbol) -> None:
        state = _short_state(btc_symbol, stop=Decimal("105"))
        events = EventDetector.detect(state, price=Decimal("95"), now_ms=2_000)
        assert any(e.type is EventType.BREAKEVEN_REACHED for e in events)


class TestNoEvent:
    def test_far_from_levels(self, btc_symbol) -> None:
        state = _long_state(btc_symbol)
        events = EventDetector.detect(state, price=Decimal("100.5"), now_ms=2_000)
        assert events == []

    def test_tight_stop_no_false_approach(self, btc_symbol) -> None:
        """Regression: entry 79286, stop 79100, take 79500 — tight levels.

        With the old 0.5%-of-level band both approach events fired at
        price 79307 (the very first tick after entry). With distance-
        based band (20% of entry↔level) the price must actually close
        in on a level before the event fires.
        """
        state = WatchState(
            watch_id="w",
            symbol=btc_symbol,
            side=WatchSide.LONG,
            entry=Decimal("79286"),
            stop=Decimal("79100"),
            take=Decimal("79500"),
            size_quote=Decimal("10000"),
            started_at_ms=1_000,
            max_duration_sec=3600,
        )
        events = EventDetector.detect(state, price=Decimal("79307"), now_ms=2_000)
        types = [e.type for e in events]
        assert EventType.PRICE_APPROACHES_STOP not in types
        assert EventType.PRICE_APPROACHES_TAKE not in types
