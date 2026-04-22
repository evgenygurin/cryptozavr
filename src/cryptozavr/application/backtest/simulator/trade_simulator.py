"""TradeSimulator: per-bar position lifecycle.

Event-driven, streaming — intentionally not vectorized. Intrabar TP/SL
collision: SL wins for LONG, TP wins for SHORT (worst-case-first).

Decimal conversion happens here at the boundary: candle values come in
as floats via pd.Series (fast numpy path inside indicators), and we
convert to Decimal for money math via `str(float_value)` to avoid
float-rounding surprises.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal

import pandas as pd

from cryptozavr.application.analytics.backtest_report import (
    BacktestTrade,
    EquityPoint,
    PositionSide,
)
from cryptozavr.application.backtest.evaluator.signals import SignalTick
from cryptozavr.application.backtest.simulator.fees import FeeModel
from cryptozavr.application.backtest.simulator.position import OpenPosition
from cryptozavr.application.backtest.simulator.slippage import SlippageModel
from cryptozavr.application.strategy.enums import StrategySide
from cryptozavr.application.strategy.strategy_spec import StrategySpec
from cryptozavr.domain.value_objects import Instant

_LOG = logging.getLogger(__name__)

# Quantum for "dust" detection: if size rounded DOWN to 10 decimal places is
# zero, the position is unrepresentable at realistic crypto precision
# (satoshi = 1e-8 BTC still fits comfortably). Only the skip-check uses the
# quantized value; BacktestTrade records the unquantized size.
_DUST_QUANTUM = Decimal("1E-10")


def _d(v: float) -> Decimal:
    """Float -> Decimal via str() to avoid binary float artifacts."""
    return Decimal(str(v))


def _is_dust(size: Decimal) -> bool:
    """True when size is too small to represent at realistic crypto precision."""
    return size.quantize(_DUST_QUANTUM, rounding=ROUND_DOWN) == 0


def _instant_for_bar(bar_index: int) -> Instant:
    """Monotonic placeholder Instants; engine facade overrides with real
    timestamps from the candle DataFrame when it has them."""
    return Instant.from_ms(1_700_000_000_000 + bar_index * 60_000)


@dataclass
class TradeSimulator:
    spec: StrategySpec
    initial_equity: Decimal
    slippage: SlippageModel
    fees: FeeModel
    min_notional: Decimal | None = None
    _equity: Decimal = field(init=False)
    _position: OpenPosition | None = field(init=False, default=None)
    _trades: list[BacktestTrade] = field(init=False, default_factory=list)
    _equity_curve: list[EquityPoint] = field(init=False, default_factory=list)
    _entry_opened_at_ms: int | None = field(init=False, default=None)
    _entry_fee: Decimal = field(init=False, default=Decimal("0"))

    def __post_init__(self) -> None:
        self._equity = self.initial_equity

    @property
    def equity(self) -> Decimal:
        return self._equity

    @property
    def open_position(self) -> OpenPosition | None:
        return self._position

    @property
    def trades(self) -> tuple[BacktestTrade, ...]:
        return tuple(self._trades)

    @property
    def equity_curve(self) -> tuple[EquityPoint, ...]:
        return tuple(self._equity_curve)

    def tick(self, candle: pd.Series, signal: SignalTick) -> None:
        bar_index = signal.bar_index
        close_price = _d(candle["close"])
        if self._position is None and signal.entry_signal is True:
            self._open_position(candle, bar_index)
        elif self._position is not None:
            self._maybe_close_intrabar_or_on_signal(candle, signal)
        # Mark-to-market equity for this bar (if still open, use close).
        mark_equity = self._equity
        if self._position is not None:
            mark_equity = self._mark_to_market(close_price)
        self._equity_curve.append(
            EquityPoint(
                observed_at=_instant_for_bar(bar_index),
                equity=mark_equity,
            )
        )

    def close_open_position(self, close_price: Decimal, bar_index: int) -> None:
        """Used by the engine to flush a still-open position at series end."""
        if self._position is None:
            return
        self._close(reference=close_price, bar_index=bar_index, at_level=None)

    def _open_position(self, candle: pd.Series, bar_index: int) -> None:
        side = self.spec.entry.side
        close_price = _d(candle["close"])
        fill = self.slippage.adjust(reference=close_price, side=side, is_entry=True)
        if fill <= 0:
            _LOG.warning(
                "simulator: non-positive fill %r at bar %d for spec=%r; skipping",
                fill,
                bar_index,
                self.spec.name,
            )
            return
        size = (self._equity * self.spec.size_pct) / fill
        notional = size * fill
        if _is_dust(size):
            _LOG.warning(
                "simulator: dust entry (size=%s rounds to 0 at %s precision) "
                "at bar %d for spec=%r; skipping",
                size,
                _DUST_QUANTUM,
                bar_index,
                self.spec.name,
            )
            return
        if self.min_notional is not None and notional < self.min_notional:
            _LOG.warning(
                "simulator: below_min_notional (%s < %s) at bar %d for spec=%r; skipping",
                notional,
                self.min_notional,
                bar_index,
                self.spec.name,
            )
            return
        entry_fee = self.fees.compute(notional=notional, is_entry=True)
        self._equity -= entry_fee
        self._entry_fee = entry_fee
        tp = None
        sl = None
        if self.spec.exit.take_profit_pct is not None:
            if side is StrategySide.LONG:
                tp = fill * (Decimal("1") + self.spec.exit.take_profit_pct)
            else:
                tp = fill * (Decimal("1") - self.spec.exit.take_profit_pct)
        if self.spec.exit.stop_loss_pct is not None:
            if side is StrategySide.LONG:
                sl = fill * (Decimal("1") - self.spec.exit.stop_loss_pct)
            else:
                sl = fill * (Decimal("1") + self.spec.exit.stop_loss_pct)
        self._position = OpenPosition(
            side=side,
            entry_price=fill,
            size=size,
            entry_bar_index=bar_index,
            take_profit_level=tp,
            stop_loss_level=sl,
        )
        self._entry_opened_at_ms = _instant_for_bar(bar_index).to_ms()

    def _maybe_close_intrabar_or_on_signal(self, candle: pd.Series, signal: SignalTick) -> None:
        assert self._position is not None
        pos = self._position
        bar_high = _d(candle["high"])
        bar_low = _d(candle["low"])
        bar_close = _d(candle["close"])
        bar_index = signal.bar_index

        tp = pos.take_profit_level
        sl = pos.stop_loss_level
        tp_inside = tp is not None and bar_low <= tp <= bar_high
        sl_inside = sl is not None and bar_low <= sl <= bar_high
        if tp_inside and sl_inside:
            # Worst-case-first: SL wins for LONG, TP wins for SHORT.
            if pos.side is StrategySide.LONG:
                assert sl is not None
                self._close(reference=sl, bar_index=bar_index, at_level=sl)
            else:
                assert tp is not None
                self._close(reference=tp, bar_index=bar_index, at_level=tp)
        elif sl_inside:
            assert sl is not None
            self._close(reference=sl, bar_index=bar_index, at_level=sl)
        elif tp_inside:
            assert tp is not None
            self._close(reference=tp, bar_index=bar_index, at_level=tp)
        elif signal.exit_signal is True:
            self._close(reference=bar_close, bar_index=bar_index, at_level=None)

    def _close(
        self,
        *,
        reference: Decimal,
        bar_index: int,
        at_level: Decimal | None,
    ) -> None:
        """Close the current position.

        If `at_level` is given, the price is the TP/SL level itself (fair
        assumption - the level was touched intrabar, no further slippage
        on top of the level). If `at_level` is None, apply slippage to
        the reference (typically the close price).
        """
        assert self._position is not None
        pos = self._position
        if at_level is None:
            exit_price = self.slippage.adjust(reference=reference, side=pos.side, is_entry=False)
        else:
            exit_price = at_level
        notional = pos.size * exit_price
        exit_fee = self.fees.compute(notional=notional, is_entry=False)
        # Realize pnl. For LONG pnl = (exit - entry) * size; SHORT mirror.
        if pos.side is StrategySide.LONG:
            gross = (exit_price - pos.entry_price) * pos.size
        else:
            gross = (pos.entry_price - exit_price) * pos.size
        # BacktestTrade.pnl is the full net: gross minus BOTH fees. Equity
        # math only adds (gross - exit_fee) here because entry_fee was
        # already debited at open — so equity stays consistent while the
        # trade record carries the full round-trip cost.
        pnl = gross - self._entry_fee - exit_fee
        self._equity += gross - exit_fee
        assert self._entry_opened_at_ms is not None
        side_enum = PositionSide.LONG if pos.side is StrategySide.LONG else PositionSide.SHORT
        self._trades.append(
            BacktestTrade(
                opened_at=Instant.from_ms(self._entry_opened_at_ms),
                closed_at=_instant_for_bar(bar_index),
                side=side_enum,
                entry_price=pos.entry_price,
                exit_price=exit_price,
                size=pos.size,
                pnl=pnl,
            )
        )
        self._position = None
        self._entry_opened_at_ms = None
        self._entry_fee = Decimal("0")

    def _mark_to_market(self, close_price: Decimal) -> Decimal:
        """Current equity if we marked the open position to `close_price`."""
        assert self._position is not None
        pos = self._position
        if pos.side is StrategySide.LONG:
            unrealized = (close_price - pos.entry_price) * pos.size
        else:
            unrealized = (pos.entry_price - close_price) * pos.size
        return self._equity + unrealized
