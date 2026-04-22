"""VolumeIndicator: identity on candle.volume."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.backtest.indicators.volume import VolumeIndicator
from tests.unit.application.backtest.indicators.fixtures import candle


def test_not_warm_before_first_update() -> None:
    ind = VolumeIndicator()
    assert ind.is_warm is False


def test_first_update_returns_volume_and_is_warm() -> None:
    ind = VolumeIndicator()
    result = ind.update(candle(0, volume="1234.5"))
    assert result == Decimal("1234.5")
    assert ind.is_warm is True


def test_subsequent_updates_track_latest_volume() -> None:
    ind = VolumeIndicator()
    ind.update(candle(0, volume="100"))
    result = ind.update(candle(1, volume="250"))
    assert result == Decimal("250")


def test_period_is_one() -> None:
    assert VolumeIndicator().period == 1
