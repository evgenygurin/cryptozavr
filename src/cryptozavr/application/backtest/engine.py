"""BacktestEngine: spec + candles → BacktestReport.

Hybrid orchestration: indicators computed in one vectorized pass,
trade simulator runs streaming, report produced at the end.
"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from cryptozavr.application.analytics.backtest_report import (
    BacktestReport,
    EquityPoint,
)
from cryptozavr.application.backtest.evaluator.strategy_evaluator import (
    StrategyEvaluator,
)
from cryptozavr.application.backtest.indicators.factory import compute_all
from cryptozavr.application.backtest.simulator.fees import (
    FeeModel,
    FixedBpsFeeModel,
)
from cryptozavr.application.backtest.simulator.slippage import (
    PctSlippageModel,
    SlippageModel,
)
from cryptozavr.application.backtest.simulator.trade_simulator import (
    TradeSimulator,
    _d,
    _instant_for_bar,
)
from cryptozavr.application.strategy.strategy_spec import StrategySpec
from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.value_objects import TimeRange

_REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}


class BacktestEngine:
    def run(
        self,
        spec: StrategySpec,
        candles: pd.DataFrame,
        *,
        initial_equity: Decimal,
        slippage: SlippageModel | None = None,
        fees: FeeModel | None = None,
        min_notional: Decimal | None = None,
    ) -> BacktestReport:
        self._validate(candles)
        slippage = slippage or PctSlippageModel(bps=10)
        fees = fees or FixedBpsFeeModel(bps=5)
        series_map = compute_all(spec, candles)
        evaluator = StrategyEvaluator(spec, series_map)
        simulator = TradeSimulator(
            spec=spec,
            initial_equity=initial_equity,
            slippage=slippage,
            fees=fees,
            min_notional=min_notional,
        )
        for bar_index in range(len(candles)):
            row = candles.iloc[bar_index]
            signal = evaluator.tick(bar_index)
            simulator.tick(row, signal)
        # Auto-close if still open at the end.
        if simulator.open_position is not None:
            simulator.close_open_position(
                close_price=_d(candles.iloc[-1]["close"]),
                bar_index=len(candles) - 1,
            )
            # Replace last equity point with updated equity post-close.
            old_curve = list(simulator.equity_curve)
            old_curve[-1] = EquityPoint(
                observed_at=_instant_for_bar(len(candles) - 1),
                equity=simulator.equity,
            )
            # Rebuild tuple
            simulator._equity_curve = old_curve
        start = _instant_for_bar(0)
        end = _instant_for_bar(len(candles) - 1)
        return BacktestReport(
            strategy_name=spec.name,
            period=TimeRange(start=start, end=end),
            initial_equity=initial_equity,
            final_equity=simulator.equity,
            trades=simulator.trades,
            equity_curve=simulator.equity_curve,
        )

    @staticmethod
    def _validate(candles: pd.DataFrame) -> None:
        if len(candles) == 0:
            raise ValidationError("BacktestEngine: candles DataFrame is empty")
        missing = _REQUIRED_COLUMNS - set(candles.columns)
        if missing:
            raise ValidationError(
                f"BacktestEngine: candles missing required columns: {sorted(missing)!r}",
            )
