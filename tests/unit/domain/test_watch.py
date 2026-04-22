from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.domain.watch import (
    EventType,
    WatchEvent,
    WatchSide,
    WatchState,
    WatchStatus,
)


class TestWatchEnums:
    def test_side_values(self) -> None:
        assert WatchSide.LONG.value == "long"
        assert WatchSide.SHORT.value == "short"

    def test_status_values(self) -> None:
        assert WatchStatus.RUNNING.value == "running"
        assert WatchStatus.STOP_HIT.value == "stop_hit"
        assert WatchStatus.TAKE_HIT.value == "take_hit"
        assert WatchStatus.TIMEOUT.value == "timeout"
        assert WatchStatus.CANCELLED.value == "cancelled"
        assert WatchStatus.ERROR.value == "error"

    def test_event_type_terminal_flag(self) -> None:
        assert EventType.STOP_HIT.is_terminal
        assert EventType.TAKE_HIT.is_terminal
        assert EventType.TIMEOUT.is_terminal
        assert not EventType.PRICE_APPROACHES_STOP.is_terminal
        assert not EventType.PRICE_APPROACHES_TAKE.is_terminal
        assert not EventType.BREAKEVEN_REACHED.is_terminal


class TestWatchEvent:
    def test_construction(self) -> None:
        event = WatchEvent(
            type=EventType.STOP_HIT,
            ts_ms=1_000_000,
            price=Decimal("79100"),
            details={"reason": "crossed"},
        )
        assert event.type is EventType.STOP_HIT
        assert event.price == Decimal("79100")

    def test_frozen(self) -> None:
        event = WatchEvent(
            type=EventType.STOP_HIT,
            ts_ms=0,
            price=Decimal("0"),
            details={},
        )
        with pytest.raises(FrozenInstanceError):
            event.price = Decimal("1")  # type: ignore[misc]


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


class TestWatchState:
    def test_valid_long(self, btc_symbol) -> None:
        state = WatchState(
            watch_id="abc",
            symbol=btc_symbol,
            side=WatchSide.LONG,
            entry=Decimal("100"),
            stop=Decimal("95"),
            take=Decimal("110"),
            size_quote=None,
            started_at_ms=1_000,
            max_duration_sec=3600,
        )
        assert state.status is WatchStatus.RUNNING
        assert state.events == []

    def test_long_stop_must_be_below_entry(self, btc_symbol) -> None:
        with pytest.raises(ValidationError, match="stop < entry"):
            WatchState(
                watch_id="abc",
                symbol=btc_symbol,
                side=WatchSide.LONG,
                entry=Decimal("100"),
                stop=Decimal("105"),
                take=Decimal("110"),
                size_quote=None,
                started_at_ms=0,
                max_duration_sec=60,
            )

    def test_short_take_must_be_below_entry(self, btc_symbol) -> None:
        with pytest.raises(ValidationError, match="take < entry"):
            WatchState(
                watch_id="abc",
                symbol=btc_symbol,
                side=WatchSide.SHORT,
                entry=Decimal("100"),
                stop=Decimal("110"),
                take=Decimal("105"),
                size_quote=None,
                started_at_ms=0,
                max_duration_sec=60,
            )

    def test_duration_bounds(self, btc_symbol) -> None:
        with pytest.raises(ValidationError, match="max_duration_sec"):
            WatchState(
                watch_id="abc",
                symbol=btc_symbol,
                side=WatchSide.LONG,
                entry=Decimal("100"),
                stop=Decimal("95"),
                take=Decimal("110"),
                size_quote=None,
                started_at_ms=0,
                max_duration_sec=30,
            )
