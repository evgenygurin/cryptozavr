"""BacktestEngine: spec + candles → BacktestReport.

Hybrid orchestration: indicators computed in one vectorized pass,
trade simulator runs streaming, report produced at the end.
"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from cryptozavr.application.analytics.backtest_report import (
    BacktestReport,
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
    instant_for_bar,
    to_decimal,
)
from cryptozavr.application.strategy.strategy_spec import StrategySpec
from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.value_objects import TimeRange

_REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}
_MIN_CANDLES = 2


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
                close_price=to_decimal(candles.iloc[-1]["close"]),
                bar_index=len(candles) - 1,
            )
            simulator.replace_last_equity_point(simulator.equity)
        start = instant_for_bar(0)
        end = instant_for_bar(len(candles) - 1)
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
        if len(candles) < _MIN_CANDLES:
            raise ValidationError(
                "BacktestEngine: at least 2 candles required (single-bar backtest is meaningless)"
            )
        missing = _REQUIRED_COLUMNS - set(candles.columns)
        if missing:
            raise ValidationError(
                f"BacktestEngine: candles missing required columns: {sorted(missing)!r}",
            )
