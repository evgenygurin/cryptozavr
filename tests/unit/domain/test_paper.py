from decimal import Decimal
from uuid import uuid4

import pytest

from cryptozavr.domain.exceptions import TradeNotFoundError, ValidationError
from cryptozavr.domain.paper import (
    PaperSide,
    PaperStats,
    PaperStatus,
    PaperTrade,
)


class TestPaperEnums:
    def test_side_values(self) -> None:
        assert PaperSide.LONG.value == "long"
        assert PaperSide.SHORT.value == "short"

    def test_status_values(self) -> None:
        assert PaperStatus.RUNNING.value == "running"
        assert PaperStatus.CLOSED.value == "closed"
        assert PaperStatus.ABANDONED.value == "abandoned"


class TestPaperTrade:
    def _base_args(self) -> dict:
        return {
            "id": uuid4(),
            "side": PaperSide.LONG,
            "venue": "kucoin",
            "symbol_native": "BTC-USDT",
            "entry": Decimal("100"),
            "stop": Decimal("95"),
            "take": Decimal("110"),
            "size_quote": Decimal("1000"),
            "opened_at_ms": 1_000_000,
            "max_duration_sec": 3600,
            "status": PaperStatus.RUNNING,
        }

    def test_valid_long(self) -> None:
        trade = PaperTrade(**self._base_args())
        assert trade.status is PaperStatus.RUNNING
        assert trade.exit_price is None
        assert trade.pnl_quote is None

    def test_long_requires_stop_below_entry(self) -> None:
        args = self._base_args() | {"stop": Decimal("105")}
        with pytest.raises(ValidationError, match="stop < entry"):
            PaperTrade(**args)

    def test_short_requires_take_below_entry(self) -> None:
        args = self._base_args() | {
            "side": PaperSide.SHORT,
            "stop": Decimal("110"),
            "take": Decimal("105"),
        }
        with pytest.raises(ValidationError, match="take < entry"):
            PaperTrade(**args)

    def test_size_must_be_positive(self) -> None:
        args = self._base_args() | {"size_quote": Decimal("0")}
        with pytest.raises(ValidationError, match="size_quote"):
            PaperTrade(**args)

    def test_compute_pnl_long_profit(self) -> None:
        trade = PaperTrade(**self._base_args())
        pnl = trade.compute_pnl(exit_price=Decimal("110"))
        assert pnl == Decimal("100.00")

    def test_compute_pnl_long_loss(self) -> None:
        trade = PaperTrade(**self._base_args())
        pnl = trade.compute_pnl(exit_price=Decimal("95"))
        assert pnl == Decimal("-50.00")

    def test_compute_pnl_short_profit(self) -> None:
        args = self._base_args() | {
            "side": PaperSide.SHORT,
            "stop": Decimal("105"),
            "take": Decimal("90"),
        }
        trade = PaperTrade(**args)
        pnl = trade.compute_pnl(exit_price=Decimal("95"))
        assert pnl == Decimal("50.00")


class TestTradeNotFoundError:
    def test_message(self) -> None:
        tid = uuid4()
        exc = TradeNotFoundError(trade_id=str(tid))
        assert str(tid) in str(exc)
        assert exc.trade_id == str(tid)


class TestPaperStats:
    def test_construction(self) -> None:
        stats = PaperStats(
            trades_count=5,
            wins=3,
            losses=2,
            open_count=1,
            net_pnl_quote=Decimal("12.5"),
            avg_win_quote=Decimal("10"),
            avg_loss_quote=Decimal("-5"),
        )
        assert stats.win_rate == Decimal("0.6")
