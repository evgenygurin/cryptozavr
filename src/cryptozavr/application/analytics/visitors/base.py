"""BacktestVisitor Protocol — each metric is a Visitor instance."""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from cryptozavr.application.analytics.backtest_report import BacktestReport

T_co = TypeVar("T_co", covariant=True)


@runtime_checkable
class BacktestVisitor(Protocol[T_co]):
    """Single-metric post-backtest computation.

    `name` is the key under which the composer stores the result; it must be
    unique across a `BacktestAnalyticsService` instance's visitor list.
    """

    name: str

    def visit(self, report: BacktestReport) -> T_co: ...
