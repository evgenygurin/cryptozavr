"""BacktestVisitor Protocol — each metric is a Visitor instance.

Notes:
- `name` is declared as `ClassVar[str]` so every visitor advertises its metric
  key at the class level. This is what `BacktestAnalyticsService` uses for
  result-dict keys and duplicate-name detection.
- We intentionally do NOT use `@runtime_checkable` here: `isinstance(x, BacktestVisitor)`
  only validates attribute presence (not signature), which gives a false sense of
  type safety. The composer reads `.name` / `.visit(...)` directly — an `AttributeError`
  there is more informative than a silently-passed `isinstance` check.
"""

from __future__ import annotations

from typing import ClassVar, Protocol, TypeVar

from cryptozavr.application.analytics.backtest_report import BacktestReport

T_co = TypeVar("T_co", covariant=True)


class BacktestVisitor(Protocol[T_co]):
    """Single-metric post-backtest computation.

    Implementers declare `name: ClassVar[str]` and implement `visit`.
    """

    name: ClassVar[str]

    def visit(self, report: BacktestReport) -> T_co: ...
