"""Compute-tool response DTOs: backtest report shapes + their envelopes.

Separated from `strategy_dtos.py` so the payload module stays focused on
wire-format inputs; this module holds only result-shape types consumed by
backtest_strategy / compare_strategies / stress_test / save_strategy.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cryptozavr.application.analytics.backtest_report import (
    BacktestReport,
    BacktestTrade,
    EquityPoint,
)


class BacktestTradeDTO(BaseModel):
    """Wire-format BacktestTrade. Times as epoch-ms int, decimals as Decimal."""

    model_config = ConfigDict(frozen=True)

    opened_at_ms: int
    closed_at_ms: int
    side: str  # "long" | "short"
    entry_price: Decimal
    exit_price: Decimal
    size: Decimal
    pnl: Decimal

    @classmethod
    def from_domain(cls, trade: BacktestTrade) -> BacktestTradeDTO:
        return cls(
            opened_at_ms=trade.opened_at.to_ms(),
            closed_at_ms=trade.closed_at.to_ms(),
            side=trade.side.value,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            size=trade.size,
            pnl=trade.pnl,
        )


class EquityPointDTO(BaseModel):
    """Wire-format EquityPoint — (observed_at_ms, equity)."""

    model_config = ConfigDict(frozen=True)

    observed_at_ms: int
    equity: Decimal

    @classmethod
    def from_domain(cls, point: EquityPoint) -> EquityPointDTO:
        return cls(observed_at_ms=point.observed_at.to_ms(), equity=point.equity)


class BacktestReportDTO(BaseModel):
    """Wire-format BacktestReport. `period` is flattened into two epoch-ms fields
    to avoid nested DTO clutter for a simple half-open interval."""

    model_config = ConfigDict(frozen=True)

    strategy_name: str
    period_start_ms: int
    period_end_ms: int
    initial_equity: Decimal
    final_equity: Decimal
    trades: list[BacktestTradeDTO]
    equity_curve: list[EquityPointDTO]

    @classmethod
    def from_domain(cls, report: BacktestReport) -> BacktestReportDTO:
        return cls(
            strategy_name=report.strategy_name,
            period_start_ms=report.period.start.to_ms(),
            period_end_ms=report.period.end.to_ms(),
            initial_equity=report.initial_equity,
            final_equity=report.final_equity,
            trades=[BacktestTradeDTO.from_domain(t) for t in report.trades],
            equity_curve=[EquityPointDTO.from_domain(p) for p in report.equity_curve],
        )


class BacktestStrategyResponse(BaseModel):
    """Response for backtest_strategy tool.

    Coherence: either success (report required, error None) or failure
    (error set, no report / metrics). `reason_codes` may accompany either
    outcome so clients can still see where the OHLCV pipeline got to when
    the backtest itself fails mid-engine.
    """

    model_config = ConfigDict(frozen=True)

    report: BacktestReportDTO | None = None
    metrics: dict[str, Decimal | None] = Field(default_factory=dict)
    reason_codes: list[str] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def _coherence(self) -> BacktestStrategyResponse:
        if self.error is not None and (self.report is not None or self.metrics):
            raise ValueError(
                "BacktestStrategyResponse: error set but report/metrics present",
            )
        if self.error is None and self.report is None:
            raise ValueError("BacktestStrategyResponse: success path requires report")
        return self


class NamedBacktestDTO(BaseModel):
    """One entry in compare_strategies / stress_test results.

    Each entry is associated with a name (strategy.name for compare,
    scenario key for stress). `report` + `metrics` present on success,
    `error` present on failure — but we don't enforce error-vs-report
    coherence here because compare_strategies needs to surface the
    strategy_name even if the OHLCV fetch failed mid-iteration.
    """

    model_config = ConfigDict(frozen=True)

    strategy_name: str
    report: BacktestReportDTO | None = None
    metrics: dict[str, Decimal | None] = Field(default_factory=dict)
    error: str | None = None


class CompareStrategiesResponse(BaseModel):
    """Response for compare_strategies.

    `comparison` is shaped metric → {strategy_name → value} so a client can
    render a side-by-side table. Duplicate strategy names: last wins in
    `comparison`; `results` preserves all in order.
    """

    model_config = ConfigDict(frozen=True)

    results: list[NamedBacktestDTO] = Field(default_factory=list)
    comparison: dict[str, dict[str, Decimal | None]] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _comparison_keys_are_result_names(self) -> CompareStrategiesResponse:
        result_names = {r.strategy_name for r in self.results if r.report is not None}
        for metric, per_strategy in self.comparison.items():
            stray = set(per_strategy) - result_names
            if stray:
                raise ValueError(
                    f"CompareStrategiesResponse.comparison[{metric!r}] references "
                    f"strategy_name(s) {sorted(stray)!r} with no successful result",
                )
        return self


class StressTestResponse(BaseModel):
    """Response for stress_test. `results` is keyed by scenario name;
    `errors` collects payload-level messages (unknown scenario, bad
    initial_equity). Engine-level failures surface per-scenario via
    `NamedBacktestDTO.error` inside `results`."""

    model_config = ConfigDict(frozen=True)

    results: dict[str, NamedBacktestDTO] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class SaveStrategyResponse(BaseModel):
    """Response for save_strategy. Success: id set, note='saved', error None.
    Failure: id None, note empty, error carries the message."""

    model_config = ConfigDict(frozen=True)

    id: str | None = None
    note: str
    error: str | None = None

    @model_validator(mode="after")
    def _coherence(self) -> SaveStrategyResponse:
        if self.error is not None and self.id is not None:
            raise ValueError("SaveStrategyResponse: error set but id also set")
        if self.error is None and self.id is None:
            raise ValueError("SaveStrategyResponse: success path requires id")
        return self
