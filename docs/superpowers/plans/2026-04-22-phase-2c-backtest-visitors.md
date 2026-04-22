# Phase 2C — Backtest-analytics Visitor pattern — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the post-backtest analytics layer (`BacktestReport` DTO + 5 concrete Visitor metrics + composer) under `src/cryptozavr/application/analytics/`, independently testable and ready for 2B's `BacktestEngine` to populate later.

**Architecture:** Contract-first. Build `BacktestReport` + Visitor Protocol first, then each metric as its own file. Composer glues them. TDD throughout: one failing test → minimum code → pass → commit.

**Tech Stack:** Python 3.12, Pydantic/dataclass for DTOs, `decimal.Decimal` for money math, `hypothesis` for property-based tests (already in `dev` group), `pytest-asyncio` NOT needed (pure computation, no IO).

**Spec reference:** [docs/superpowers/specs/2026-04-22-phase-2c-backtest-visitors-design.md](../specs/2026-04-22-phase-2c-backtest-visitors-design.md).

---

## File structure

**New files:**
- `src/cryptozavr/application/analytics/__init__.py`
- `src/cryptozavr/application/analytics/backtest_report.py` — DTOs (`TradeSide`, `BacktestTrade`, `EquityPoint`, `BacktestReport`)
- `src/cryptozavr/application/analytics/visitors/__init__.py`
- `src/cryptozavr/application/analytics/visitors/base.py` — `BacktestVisitor` Protocol
- `src/cryptozavr/application/analytics/visitors/total_return.py` — `TotalReturnVisitor`
- `src/cryptozavr/application/analytics/visitors/win_rate.py` — `WinRateVisitor`
- `src/cryptozavr/application/analytics/visitors/profit_factor.py` — `ProfitFactorVisitor`
- `src/cryptozavr/application/analytics/visitors/max_drawdown.py` — `MaxDrawdownVisitor`
- `src/cryptozavr/application/analytics/visitors/sharpe.py` — `SharpeRatioVisitor`
- `src/cryptozavr/application/analytics/analytics_service.py` — `BacktestAnalyticsService`
- `tests/unit/application/analytics/__init__.py`
- `tests/unit/application/analytics/fixtures.py` — reusable hand-built reports
- `tests/unit/application/analytics/test_backtest_report.py`
- `tests/unit/application/analytics/test_total_return_visitor.py`
- `tests/unit/application/analytics/test_win_rate_visitor.py`
- `tests/unit/application/analytics/test_profit_factor_visitor.py`
- `tests/unit/application/analytics/test_max_drawdown_visitor.py`
- `tests/unit/application/analytics/test_sharpe_visitor.py`
- `tests/unit/application/analytics/test_analytics_service.py`

**Modified files:**
- `CHANGELOG.md` (short `[Unreleased]` entry)

---

## Task 1 — `BacktestReport` data model

**Files:**
- Create: `src/cryptozavr/application/analytics/__init__.py`
- Create: `src/cryptozavr/application/analytics/backtest_report.py`
- Create: `tests/unit/application/analytics/__init__.py`
- Create: `tests/unit/application/analytics/test_backtest_report.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/application/analytics/test_backtest_report.py
"""BacktestReport DTO validation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.analytics.backtest_report import (
    BacktestReport,
    BacktestTrade,
    EquityPoint,
    TradeSide,
)
from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.value_objects import Instant, TimeRange

def _tr(start_ms: int = 1_700_000_000_000, end_ms: int = 1_700_086_400_000) -> TimeRange:
    return TimeRange(start=Instant.from_ms(start_ms), end=Instant.from_ms(end_ms))

class TestBacktestTrade:
    def test_accepts_positive_values(self) -> None:
        t = BacktestTrade(
            opened_at=Instant.from_ms(1_700_000_000_000),
            closed_at=Instant.from_ms(1_700_000_060_000),
            side=TradeSide.LONG,
            entry_price=Decimal("100"),
            exit_price=Decimal("110"),
            size=Decimal("1"),
            pnl=Decimal("10"),
        )
        assert t.pnl == Decimal("10")

    def test_rejects_closed_before_opened(self) -> None:
        with pytest.raises(ValidationError, match="closed_at must be >= opened_at"):
            BacktestTrade(
                opened_at=Instant.from_ms(1_700_000_060_000),
                closed_at=Instant.from_ms(1_700_000_000_000),
                side=TradeSide.LONG,
                entry_price=Decimal("100"),
                exit_price=Decimal("110"),
                size=Decimal("1"),
                pnl=Decimal("10"),
            )

    def test_rejects_non_positive_size(self) -> None:
        with pytest.raises(ValidationError, match="size must be > 0"):
            BacktestTrade(
                opened_at=Instant.from_ms(1_700_000_000_000),
                closed_at=Instant.from_ms(1_700_000_060_000),
                side=TradeSide.LONG,
                entry_price=Decimal("100"),
                exit_price=Decimal("110"),
                size=Decimal("0"),
                pnl=Decimal("0"),
            )

class TestBacktestReport:
    def test_accepts_valid_report(self) -> None:
        r = BacktestReport(
            strategy_name="vwap_mean_revert",
            period=_tr(),
            initial_equity=Decimal("1000"),
            final_equity=Decimal("1100"),
            trades=(),
            equity_curve=(
                EquityPoint(observed_at=Instant.from_ms(1_700_000_000_000), equity=Decimal("1000")),
                EquityPoint(observed_at=Instant.from_ms(1_700_086_400_000), equity=Decimal("1100")),
            ),
        )
        assert r.strategy_name == "vwap_mean_revert"

    def test_rejects_non_positive_initial_equity(self) -> None:
        with pytest.raises(ValidationError, match="initial_equity must be > 0"):
            BacktestReport(
                strategy_name="x",
                period=_tr(),
                initial_equity=Decimal("0"),
                final_equity=Decimal("0"),
                trades=(),
                equity_curve=(),
            )

    def test_rejects_trades_out_of_chronological_order(self) -> None:
        t_late = BacktestTrade(
            opened_at=Instant.from_ms(1_700_000_060_000),
            closed_at=Instant.from_ms(1_700_000_120_000),
            side=TradeSide.LONG,
            entry_price=Decimal("100"),
            exit_price=Decimal("110"),
            size=Decimal("1"),
            pnl=Decimal("10"),
        )
        t_early = BacktestTrade(
            opened_at=Instant.from_ms(1_700_000_000_000),
            closed_at=Instant.from_ms(1_700_000_030_000),
            side=TradeSide.LONG,
            entry_price=Decimal("100"),
            exit_price=Decimal("105"),
            size=Decimal("1"),
            pnl=Decimal("5"),
        )
        with pytest.raises(ValidationError, match="trades must be sorted"):
            BacktestReport(
                strategy_name="x",
                period=_tr(),
                initial_equity=Decimal("1000"),
                final_equity=Decimal("1015"),
                trades=(t_late, t_early),
                equity_curve=(),
            )
```

- [ ] **Step 2: Run test — expect import-error / failure**

```text
uv run pytest tests/unit/application/analytics/test_backtest_report.py -q
```

Expected: `ModuleNotFoundError: cryptozavr.application.analytics.backtest_report`.

- [ ] **Step 3: Implement DTOs**

```python
# src/cryptozavr/application/analytics/__init__.py
"""Post-backtest analytics (Phase 2C) — Visitor pattern over BacktestReport."""
```

```python
# src/cryptozavr/application/analytics/backtest_report.py
"""BacktestReport DTO + supporting value types for post-backtest analytics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.value_objects import Instant, TimeRange

class TradeSide(StrEnum):
    LONG = "long"
    SHORT = "short"

@dataclass(frozen=True, slots=True)
class BacktestTrade:
    opened_at: Instant
    closed_at: Instant
    side: TradeSide
    entry_price: Decimal
    exit_price: Decimal
    size: Decimal
    pnl: Decimal

    def __post_init__(self) -> None:
        if self.closed_at.to_ms() < self.opened_at.to_ms():
            raise ValidationError("BacktestTrade: closed_at must be >= opened_at")
        if self.size <= 0:
            raise ValidationError("BacktestTrade: size must be > 0")

@dataclass(frozen=True, slots=True)
class EquityPoint:
    observed_at: Instant
    equity: Decimal

@dataclass(frozen=True, slots=True)
class BacktestReport:
    strategy_name: str
    period: TimeRange
    initial_equity: Decimal
    final_equity: Decimal
    trades: tuple[BacktestTrade, ...]
    equity_curve: tuple[EquityPoint, ...]

    def __post_init__(self) -> None:
        if self.initial_equity <= 0:
            raise ValidationError("BacktestReport: initial_equity must be > 0")
        for a, b in zip(self.trades, self.trades[1:], strict=False):
            if b.opened_at.to_ms() < a.opened_at.to_ms():
                raise ValidationError(
                    "BacktestReport: trades must be sorted by opened_at ascending",
                )
```

- [ ] **Step 4: Run test — expect PASS**

```text
uv run pytest tests/unit/application/analytics/test_backtest_report.py -q
```

Expected: `6 passed` (3 tests + class setup).

- [ ] **Step 5: Commit**

```bash
git add src/cryptozavr/application/analytics/__init__.py \
        src/cryptozavr/application/analytics/backtest_report.py \
        tests/unit/application/analytics/__init__.py \
        tests/unit/application/analytics/test_backtest_report.py
git commit -m "feat(analytics): add BacktestReport DTO (2C)

BacktestTrade validates chronology + positive size; BacktestReport
validates positive initial_equity + chronological trades.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 — Visitor Protocol + shared fixtures

**Files:**
- Create: `src/cryptozavr/application/analytics/visitors/__init__.py`
- Create: `src/cryptozavr/application/analytics/visitors/base.py`
- Create: `tests/unit/application/analytics/fixtures.py`

- [ ] **Step 1: Write the protocol + fixtures (no test — Protocol needs a consumer)**

```python
# src/cryptozavr/application/analytics/visitors/__init__.py
"""Concrete BacktestVisitor implementations."""
```

```python
# src/cryptozavr/application/analytics/visitors/base.py
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
```

```python
# tests/unit/application/analytics/fixtures.py
"""Hand-built BacktestReport fixtures for visitor tests."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.backtest_report import (
    BacktestReport,
    BacktestTrade,
    EquityPoint,
    TradeSide,
)
from cryptozavr.domain.value_objects import Instant, TimeRange

_DAY_MS = 86_400_000

def _point(day: int, equity: str) -> EquityPoint:
    return EquityPoint(
        observed_at=Instant.from_ms(1_700_000_000_000 + day * _DAY_MS),
        equity=Decimal(equity),
    )

def _trade(day: int, pnl: str, *, size: str = "1") -> BacktestTrade:
    open_ms = 1_700_000_000_000 + day * _DAY_MS
    return BacktestTrade(
        opened_at=Instant.from_ms(open_ms),
        closed_at=Instant.from_ms(open_ms + 60_000),
        side=TradeSide.LONG,
        entry_price=Decimal("100"),
        exit_price=Decimal("100") + Decimal(pnl),
        size=Decimal(size),
        pnl=Decimal(pnl),
    )

def make_report(
    *,
    initial: str = "1000",
    final: str = "1100",
    equity_curve: tuple[str, ...] = ("1000", "1050", "1100"),
    trades: tuple[BacktestTrade, ...] = (),
) -> BacktestReport:
    return BacktestReport(
        strategy_name="test",
        period=TimeRange(
            start=Instant.from_ms(1_700_000_000_000),
            end=Instant.from_ms(1_700_000_000_000 + len(equity_curve) * _DAY_MS),
        ),
        initial_equity=Decimal(initial),
        final_equity=Decimal(final),
        trades=trades,
        equity_curve=tuple(_point(i, v) for i, v in enumerate(equity_curve)),
    )
```

- [ ] **Step 2: Verify module imports cleanly**

```text
uv run python -c "from cryptozavr.application.analytics.visitors.base import BacktestVisitor; print(BacktestVisitor)"
```

Expected: prints the Protocol class, no traceback.

- [ ] **Step 3: Commit**

```bash
git add src/cryptozavr/application/analytics/visitors/__init__.py \
        src/cryptozavr/application/analytics/visitors/base.py \
        tests/unit/application/analytics/fixtures.py
git commit -m "feat(analytics): add BacktestVisitor Protocol + shared test fixtures

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 — `TotalReturnVisitor`

**Files:**
- Create: `src/cryptozavr/application/analytics/visitors/total_return.py`
- Create: `tests/unit/application/analytics/test_total_return_visitor.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/application/analytics/test_total_return_visitor.py
"""TotalReturnVisitor: (final - initial) / initial."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.visitors.total_return import TotalReturnVisitor

from tests.unit.application.analytics.fixtures import make_report

def test_ten_percent_gain() -> None:
    report = make_report(initial="1000", final="1100")
    assert TotalReturnVisitor().visit(report) == Decimal("0.1")

def test_twenty_percent_loss() -> None:
    report = make_report(initial="1000", final="800")
    assert TotalReturnVisitor().visit(report) == Decimal("-0.2")

def test_zero_return_when_final_equals_initial() -> None:
    report = make_report(initial="1000", final="1000")
    assert TotalReturnVisitor().visit(report) == Decimal("0")

def test_visitor_has_stable_name() -> None:
    assert TotalReturnVisitor().name == "total_return"
```

- [ ] **Step 2: Run test — expect FAIL (module not found)**

```text
uv run pytest tests/unit/application/analytics/test_total_return_visitor.py -q
```

- [ ] **Step 3: Implement the visitor**

```python
# src/cryptozavr/application/analytics/visitors/total_return.py
"""TotalReturnVisitor: (final_equity - initial_equity) / initial_equity."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.backtest_report import BacktestReport

class TotalReturnVisitor:
    name = "total_return"

    def visit(self, report: BacktestReport) -> Decimal:
        return (report.final_equity - report.initial_equity) / report.initial_equity
```

- [ ] **Step 4: Run test — expect PASS**

```text
uv run pytest tests/unit/application/analytics/test_total_return_visitor.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/cryptozavr/application/analytics/visitors/total_return.py \
        tests/unit/application/analytics/test_total_return_visitor.py
git commit -m "feat(analytics): add TotalReturnVisitor

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 — `WinRateVisitor`

**Files:**
- Create: `src/cryptozavr/application/analytics/visitors/win_rate.py`
- Create: `tests/unit/application/analytics/test_win_rate_visitor.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/application/analytics/test_win_rate_visitor.py
"""WinRateVisitor: sum(pnl > 0) / len(trades)."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.visitors.win_rate import WinRateVisitor

from tests.unit.application.analytics.fixtures import _trade, make_report

def test_half_winners() -> None:
    trades = (_trade(0, "10"), _trade(1, "-5"), _trade(2, "8"), _trade(3, "-3"))
    report = make_report(trades=trades)
    assert WinRateVisitor().visit(report) == Decimal("0.5")

def test_all_winners() -> None:
    trades = (_trade(0, "10"), _trade(1, "5"))
    report = make_report(trades=trades)
    assert WinRateVisitor().visit(report) == Decimal("1")

def test_all_losers() -> None:
    trades = (_trade(0, "-10"), _trade(1, "-5"))
    report = make_report(trades=trades)
    assert WinRateVisitor().visit(report) == Decimal("0")

def test_empty_trades_returns_zero() -> None:
    report = make_report(trades=())
    assert WinRateVisitor().visit(report) == Decimal("0")

def test_zero_pnl_trade_is_not_a_win() -> None:
    trades = (_trade(0, "0"), _trade(1, "10"))
    report = make_report(trades=trades)
    assert WinRateVisitor().visit(report) == Decimal("0.5")

def test_visitor_name() -> None:
    assert WinRateVisitor().name == "win_rate"
```

- [ ] **Step 2: Run — expect FAIL**

```text
uv run pytest tests/unit/application/analytics/test_win_rate_visitor.py -q
```

- [ ] **Step 3: Implement**

```python
# src/cryptozavr/application/analytics/visitors/win_rate.py
"""WinRateVisitor: proportion of trades with positive pnl."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.backtest_report import BacktestReport

class WinRateVisitor:
    name = "win_rate"

    def visit(self, report: BacktestReport) -> Decimal:
        if not report.trades:
            return Decimal("0")
        winners = sum(1 for t in report.trades if t.pnl > 0)
        return Decimal(winners) / Decimal(len(report.trades))
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/cryptozavr/application/analytics/visitors/win_rate.py \
        tests/unit/application/analytics/test_win_rate_visitor.py
git commit -m "feat(analytics): add WinRateVisitor

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 — `ProfitFactorVisitor`

**Files:**
- Create: `src/cryptozavr/application/analytics/visitors/profit_factor.py`
- Create: `tests/unit/application/analytics/test_profit_factor_visitor.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/application/analytics/test_profit_factor_visitor.py
"""ProfitFactorVisitor: gross_profit / |gross_loss|, None if no losses."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.visitors.profit_factor import (
    ProfitFactorVisitor,
)

from tests.unit.application.analytics.fixtures import _trade, make_report

def test_two_to_one_ratio() -> None:
    # gross profit = 20, gross loss = 10 → factor = 2.0
    trades = (_trade(0, "15"), _trade(1, "-10"), _trade(2, "5"))
    report = make_report(trades=trades)
    assert ProfitFactorVisitor().visit(report) == Decimal("2")

def test_all_winners_returns_none() -> None:
    trades = (_trade(0, "10"), _trade(1, "5"))
    report = make_report(trades=trades)
    assert ProfitFactorVisitor().visit(report) is None

def test_all_losers_returns_zero() -> None:
    trades = (_trade(0, "-10"), _trade(1, "-5"))
    report = make_report(trades=trades)
    assert ProfitFactorVisitor().visit(report) == Decimal("0")

def test_empty_returns_none() -> None:
    report = make_report(trades=())
    assert ProfitFactorVisitor().visit(report) is None

def test_name() -> None:
    assert ProfitFactorVisitor().name == "profit_factor"
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

```python
# src/cryptozavr/application/analytics/visitors/profit_factor.py
"""ProfitFactorVisitor: gross_profit / |gross_loss|."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.backtest_report import BacktestReport

class ProfitFactorVisitor:
    name = "profit_factor"

    def visit(self, report: BacktestReport) -> Decimal | None:
        gross_profit = Decimal("0")
        gross_loss = Decimal("0")
        for t in report.trades:
            if t.pnl > 0:
                gross_profit += t.pnl
            elif t.pnl < 0:
                gross_loss += -t.pnl
        if gross_loss == 0:
            # All-winners or empty → ratio undefined
            return None
        return gross_profit / gross_loss
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/cryptozavr/application/analytics/visitors/profit_factor.py \
        tests/unit/application/analytics/test_profit_factor_visitor.py
git commit -m "feat(analytics): add ProfitFactorVisitor (returns None on no-loss)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 — `MaxDrawdownVisitor` + property-based tests

**Files:**
- Create: `src/cryptozavr/application/analytics/visitors/max_drawdown.py`
- Create: `tests/unit/application/analytics/test_max_drawdown_visitor.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/application/analytics/test_max_drawdown_visitor.py
"""MaxDrawdownVisitor: max (peak - equity) / peak across the equity curve."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from cryptozavr.application.analytics.backtest_report import (
    BacktestReport,
    EquityPoint,
)
from cryptozavr.application.analytics.visitors.max_drawdown import (
    MaxDrawdownVisitor,
)
from cryptozavr.domain.value_objects import Instant, TimeRange

from tests.unit.application.analytics.fixtures import make_report

def test_simple_drawdown() -> None:
    # 1000 → 1200 → 900 → 1100: peak 1200, trough 900, dd = 300/1200 = 0.25
    report = make_report(equity_curve=("1000", "1200", "900", "1100"))
    assert MaxDrawdownVisitor().visit(report) == Decimal("0.25")

def test_monotone_increasing_has_zero_drawdown() -> None:
    report = make_report(equity_curve=("1000", "1100", "1200", "1500"))
    assert MaxDrawdownVisitor().visit(report) == Decimal("0")

def test_total_loss_returns_one() -> None:
    report = make_report(equity_curve=("1000", "500", "0"))
    assert MaxDrawdownVisitor().visit(report) == Decimal("1")

def test_empty_curve_returns_zero() -> None:
    report = make_report(equity_curve=())
    # override via direct construction so fixtures don't reject empty
    bare = BacktestReport(
        strategy_name="x",
        period=TimeRange(
            start=Instant.from_ms(1_700_000_000_000),
            end=Instant.from_ms(1_700_000_060_000),
        ),
        initial_equity=Decimal("1000"),
        final_equity=Decimal("1000"),
        trades=(),
        equity_curve=(),
    )
    assert MaxDrawdownVisitor().visit(bare) == Decimal("0")

def test_name() -> None:
    assert MaxDrawdownVisitor().name == "max_drawdown"

@given(
    st.lists(
        st.decimals(min_value="1", max_value="1e6", allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=50,
    ).map(lambda xs: sorted(xs))
)
def test_property_monotone_increasing_curve_has_zero_drawdown(values: list[Decimal]) -> None:
    curve = tuple(
        EquityPoint(observed_at=Instant.from_ms(1_700_000_000_000 + i * 60_000), equity=v)
        for i, v in enumerate(values)
    )
    report = BacktestReport(
        strategy_name="x",
        period=TimeRange(
            start=Instant.from_ms(1_700_000_000_000),
            end=Instant.from_ms(1_700_000_000_000 + len(values) * 60_000),
        ),
        initial_equity=values[0],
        final_equity=values[-1],
        trades=(),
        equity_curve=curve,
    )
    assert MaxDrawdownVisitor().visit(report) == Decimal("0")

@given(
    st.lists(
        st.decimals(min_value="1", max_value="1e6", allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=50,
    )
)
def test_property_drawdown_is_in_zero_one(values: list[Decimal]) -> None:
    curve = tuple(
        EquityPoint(observed_at=Instant.from_ms(1_700_000_000_000 + i * 60_000), equity=v)
        for i, v in enumerate(values)
    )
    report = BacktestReport(
        strategy_name="x",
        period=TimeRange(
            start=Instant.from_ms(1_700_000_000_000),
            end=Instant.from_ms(1_700_000_000_000 + len(values) * 60_000),
        ),
        initial_equity=values[0],
        final_equity=values[-1],
        trades=(),
        equity_curve=curve,
    )
    dd = MaxDrawdownVisitor().visit(report)
    assert Decimal("0") <= dd <= Decimal("1")
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

```python
# src/cryptozavr/application/analytics/visitors/max_drawdown.py
"""MaxDrawdownVisitor: max ((peak - equity) / peak) across equity_curve."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.backtest_report import BacktestReport

class MaxDrawdownVisitor:
    name = "max_drawdown"

    def visit(self, report: BacktestReport) -> Decimal:
        peak = Decimal("0")
        max_dd = Decimal("0")
        for point in report.equity_curve:
            if point.equity > peak:
                peak = point.equity
            if peak > 0:
                dd = (peak - point.equity) / peak
                if dd > max_dd:
                    max_dd = dd
        return max_dd
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/cryptozavr/application/analytics/visitors/max_drawdown.py \
        tests/unit/application/analytics/test_max_drawdown_visitor.py
git commit -m "feat(analytics): add MaxDrawdownVisitor + hypothesis property tests

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7 — `SharpeRatioVisitor` + property tests

**Files:**
- Create: `src/cryptozavr/application/analytics/visitors/sharpe.py`
- Create: `tests/unit/application/analytics/test_sharpe_visitor.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/application/analytics/test_sharpe_visitor.py
"""SharpeRatioVisitor: annualised (mean - rf) / stdev."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from cryptozavr.application.analytics.backtest_report import (
    BacktestReport,
    EquityPoint,
)
from cryptozavr.application.analytics.visitors.sharpe import SharpeRatioVisitor
from cryptozavr.domain.value_objects import Instant, TimeRange

def _curve(values: tuple[str, ...]) -> tuple[EquityPoint, ...]:
    return tuple(
        EquityPoint(observed_at=Instant.from_ms(1_700_000_000_000 + i * 86_400_000), equity=Decimal(v))
        for i, v in enumerate(values)
    )

def _report(values: tuple[str, ...]) -> BacktestReport:
    curve = _curve(values)
    return BacktestReport(
        strategy_name="x",
        period=TimeRange(
            start=curve[0].observed_at,
            end=curve[-1].observed_at,
        ),
        initial_equity=Decimal(values[0]),
        final_equity=Decimal(values[-1]),
        trades=(),
        equity_curve=curve,
    )

def test_constant_equity_has_zero_sharpe() -> None:
    # No variance → mean=0, stdev=0 → Sharpe = 0 by convention.
    report = _report(("1000", "1000", "1000", "1000"))
    assert SharpeRatioVisitor().visit(report) == Decimal("0")

def test_fewer_than_two_points_returns_zero() -> None:
    report = _report(("1000",))
    assert SharpeRatioVisitor().visit(report) == Decimal("0")

def test_positive_sharpe_for_steady_growth() -> None:
    # 1% daily growth, annualised factor=365 → Sharpe is very large.
    report = _report(("1000", "1010", "1020.1", "1030.3", "1040.6"))
    result = SharpeRatioVisitor().visit(report)
    assert result > Decimal("0")

def test_name_default() -> None:
    assert SharpeRatioVisitor().name == "sharpe_ratio"

def test_annualisation_factor_scales_linearly_by_sqrt() -> None:
    report = _report(("1000", "1010", "1020.1", "1030.3", "1040.6"))
    a = SharpeRatioVisitor(annualisation_factor=Decimal("365")).visit(report)
    b = SharpeRatioVisitor(annualisation_factor=Decimal("1460")).visit(report)  # 4x
    # sqrt(4) = 2 → b ≈ 2 * a (allow 0.1% tolerance for decimal rounding)
    ratio = b / a
    assert Decimal("1.99") < ratio < Decimal("2.01")

@given(
    st.lists(
        st.decimals(
            min_value="900", max_value="1100", allow_nan=False, allow_infinity=False, places=2
        ),
        min_size=5,
        max_size=30,
    )
)
def test_property_sharpe_finite_for_bounded_curves(values: list[Decimal]) -> None:
    # Any bounded-positive curve produces a finite Decimal; no exceptions.
    report = _report(tuple(str(v) for v in values))
    result = SharpeRatioVisitor().visit(report)
    assert result.is_finite()
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

```python
# src/cryptozavr/application/analytics/visitors/sharpe.py
"""SharpeRatioVisitor: annualised Sharpe = (mean(r) - rf) / stdev(r) * sqrt(k)."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.backtest_report import BacktestReport

_DEFAULT_ANNUALISATION = Decimal("365")

class SharpeRatioVisitor:
    name = "sharpe_ratio"

    def __init__(
        self,
        *,
        risk_free_rate: Decimal = Decimal("0"),
        annualisation_factor: Decimal = _DEFAULT_ANNUALISATION,
    ) -> None:
        self._rf = risk_free_rate
        self._k = annualisation_factor

    def visit(self, report: BacktestReport) -> Decimal:
        curve = report.equity_curve
        if len(curve) < 2:
            return Decimal("0")
        returns: list[Decimal] = []
        for prev, curr in zip(curve, curve[1:], strict=True):
            if prev.equity == 0:
                continue
            returns.append((curr.equity - prev.equity) / prev.equity)
        if not returns:
            return Decimal("0")
        mean = sum(returns, Decimal("0")) / Decimal(len(returns))
        variance = sum(((r - mean) ** 2 for r in returns), Decimal("0")) / Decimal(len(returns))
        if variance == 0:
            return Decimal("0")
        stdev = variance.sqrt()
        return (mean - self._rf) / stdev * self._k.sqrt()
```

- [ ] **Step 4: Run — PASS**

Run: `uv run pytest tests/unit/application/analytics/test_sharpe_visitor.py -q`

- [ ] **Step 5: Commit**

```bash
git add src/cryptozavr/application/analytics/visitors/sharpe.py \
        tests/unit/application/analytics/test_sharpe_visitor.py
git commit -m "feat(analytics): add SharpeRatioVisitor (configurable annualisation)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8 — `BacktestAnalyticsService` composer

**Files:**
- Create: `src/cryptozavr/application/analytics/analytics_service.py`
- Create: `tests/unit/application/analytics/test_analytics_service.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/application/analytics/test_analytics_service.py
"""BacktestAnalyticsService runs every registered visitor against a report."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.analytics.analytics_service import (
    BacktestAnalyticsService,
)
from cryptozavr.application.analytics.visitors.total_return import TotalReturnVisitor
from cryptozavr.application.analytics.visitors.win_rate import WinRateVisitor

from tests.unit.application.analytics.fixtures import _trade, make_report

def test_run_all_returns_one_result_per_visitor() -> None:
    service = BacktestAnalyticsService([TotalReturnVisitor(), WinRateVisitor()])
    report = make_report(
        initial="1000",
        final="1100",
        trades=(_trade(0, "10"), _trade(1, "-5")),
    )
    results = service.run_all(report)
    assert results == {"total_return": Decimal("0.1"), "win_rate": Decimal("0.5")}

def test_run_all_preserves_visitor_order() -> None:
    visitors = [TotalReturnVisitor(), WinRateVisitor()]
    service = BacktestAnalyticsService(visitors)
    report = make_report(trades=(_trade(0, "1"),))
    assert list(service.run_all(report).keys()) == ["total_return", "win_rate"]

def test_run_all_rejects_duplicate_visitor_names() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        BacktestAnalyticsService([TotalReturnVisitor(), TotalReturnVisitor()])

def test_run_all_propagates_visitor_exception() -> None:
    class _Boom:
        name = "boom"

        def visit(self, report):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    service = BacktestAnalyticsService([_Boom()])
    report = make_report()
    with pytest.raises(RuntimeError, match="boom"):
        service.run_all(report)
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

```python
# src/cryptozavr/application/analytics/analytics_service.py
"""BacktestAnalyticsService composer — runs a list of Visitor instances."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from cryptozavr.application.analytics.backtest_report import BacktestReport
from cryptozavr.application.analytics.visitors.base import BacktestVisitor

class BacktestAnalyticsService:
    """Runs a list of BacktestVisitor instances against a report.

    Visitor ordering is preserved in the result dict. Visitor exceptions
    propagate — we do not silently swallow metric failures.
    """

    def __init__(self, visitors: Sequence[BacktestVisitor[Any]]) -> None:
        seen: set[str] = set()
        for v in visitors:
            if v.name in seen:
                raise ValueError(f"duplicate visitor name: {v.name!r}")
            seen.add(v.name)
        self._visitors = tuple(visitors)

    def run_all(self, report: BacktestReport) -> dict[str, Any]:
        return {v.name: v.visit(report) for v in self._visitors}
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/cryptozavr/application/analytics/analytics_service.py \
        tests/unit/application/analytics/test_analytics_service.py
git commit -m "feat(analytics): add BacktestAnalyticsService composer

Runs a list of BacktestVisitor instances against a BacktestReport,
preserves order in the result dict, rejects duplicate visitor names,
propagates visitor exceptions (no silent failures).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9 — CHANGELOG entry + full sweep

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add `[Unreleased]` entry**

Open `CHANGELOG.md` and under `## [Unreleased]` (empty section after v0.3.1) insert:

```markdown
### Added — Phase 2C — Post-backtest analytics Visitor pattern

- `BacktestReport` DTO (`BacktestTrade` + `EquityPoint` + `TradeSide`) with
  chronological + positive-value invariants.
- `BacktestVisitor` Protocol + 5 concrete visitors:
  `TotalReturnVisitor`, `WinRateVisitor`, `ProfitFactorVisitor`,
  `MaxDrawdownVisitor`, `SharpeRatioVisitor` (configurable annualisation /
  risk-free rate).
- `BacktestAnalyticsService` composer — preserves visitor order, rejects
  duplicate names, propagates visitor exceptions.
- Hypothesis property-based tests for `MaxDrawdownVisitor` (monotone-curve
  invariant, range `[0,1]`) and `SharpeRatioVisitor` (finiteness on bounded
  curves).
- +~25 unit tests.
```

- [ ] **Step 2: Run full sweep**

```bash
uv run pytest tests/unit tests/contract -m "not integration" -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Expected: all four green, test count = 473 + ~25 (depends on hypothesis-parametrised run counts).

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: log Phase 2C in CHANGELOG Unreleased

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10 — Push + PR + review

**Files:** (none — git operations)

- [ ] **Step 1: Push branch**

```bash
git push -u origin feat/phase-2c-visitors
```

- [ ] **Step 2: Create PR**

Write body to `/tmp/pr-body.md`:

```markdown
## Summary

Phase 2C — post-backtest analytics Visitor pattern (per Phase 2 spec §12).
Contract-first slice: `BacktestReport` DTO + 5 concrete visitors +
composer under `src/cryptozavr/application/analytics/`. Independently
testable, ready for 2B's `BacktestEngine` to populate later.

## Test plan

- [ ] `uv run pytest tests/unit tests/contract -m "not integration" -q`
      → 473 baseline + ~25 new = ~498 passing
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy src`
      → clean
- [ ] Verify hypothesis property tests run without shrinking failures
      (`test_property_drawdown_is_in_zero_one`, `test_property_sharpe_finite_for_bounded_curves`)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Then:

```bash
gh pr create --base main --head feat/phase-2c-visitors \
  --title "Phase 2C: post-backtest analytics Visitor pattern" \
  --body-file /tmp/pr-body.md
```

- [ ] **Step 3: Invoke `pr-review-toolkit:review-pr` skill**

After PR URL is returned, run the review skill against the new PR. Address
Critical/Important findings as follow-up commits on the same branch.

- [ ] **Step 4: Merge**

Once review passes:

```bash
gh pr merge <PR_NUM> --merge --delete-branch=false
git checkout main && git pull --ff-only origin main
```

---

## Self-review checklist (for the plan author)

- [x] Every task has a failing-test step before implementation.
- [x] Every step with code has a runnable code block.
- [x] Exact file paths throughout.
- [x] Exact commands with expected output.
- [x] Type consistency: `BacktestVisitor` Protocol declared in Task 2, used identically in Tasks 3–8; `BacktestReport`/`BacktestTrade`/`EquityPoint`/`TradeSide` declared in Task 1, reused verbatim.
- [x] Visitor names (`total_return`, `win_rate`, `profit_factor`, `max_drawdown`, `sharpe_ratio`) agreed between visitors and their tests.
- [x] CHANGELOG + PR steps include a full-sweep gate before push.
- [x] All spec sections (Data model, Visitor protocol, 5 concrete visitors, Composer, Testing strategy) map to a task.
