# Phase 2 Sub-project A — BacktestEngine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `cryptozavr.application.backtest` — a hybrid (vectorized
indicators + streaming trade simulator) backtesting engine that executes
a `StrategySpec` (from 2A) against an OHLCV DataFrame and produces a
`BacktestReport` (from 2C).

**Architecture:** Indicators compute full series in one numpy-backed
pass returning `pd.Series[float]` with NaN during warm-up. Evaluator
reads pre-computed series per bar with `None`-propagation on NaN. Trade
simulator is streaming (event-driven) — opens/closes positions,
applies slippage + fees, emits `BacktestTrade`s and an equity point per
bar. Engine facade wires it all and returns a `BacktestReport`.

**Tech Stack:** Python 3.12, pandas 2.2+ (new dep), numpy (transitive
via ccxt), Pydantic v2 (from 2A), `BacktestReport` DTO (from 2C),
hypothesis for property tests, pytest + ruff + mypy.

---

## File Structure

```text
src/cryptozavr/application/backtest/
├── __init__.py
├── indicators/
│   ├── __init__.py
│   ├── base.py              # Indicator Protocol
│   ├── price.py             # extract_price_series(df, source) -> pd.Series
│   ├── sma.py               # SimpleMovingAverage
│   ├── ema.py               # ExponentialMovingAverage
│   ├── rsi.py               # RelativeStrengthIndex (Wilder)
│   ├── macd.py              # MACD line
│   ├── atr.py               # AverageTrueRange (Wilder)
│   ├── volume.py            # VolumeIndicator
│   └── factory.py           # create_indicator + compute_all
├── evaluator/
│   ├── __init__.py
│   ├── signals.py           # SignalTick
│   ├── condition.py         # evaluate_condition
│   └── strategy_evaluator.py
├── simulator/
│   ├── __init__.py
│   ├── slippage.py          # SlippageModel Protocol + PctSlippageModel
│   ├── fees.py              # FeeModel Protocol + FixedBpsFeeModel
│   ├── position.py          # OpenPosition
│   └── trade_simulator.py
└── engine.py                # BacktestEngine

tests/unit/application/backtest/
├── __init__.py
├── fixtures.py              # candle_df() helper
├── indicators/
│   ├── __init__.py
│   ├── test_price.py
│   ├── test_sma.py
│   ├── test_ema.py
│   ├── test_rsi.py
│   ├── test_macd.py
│   ├── test_atr.py
│   ├── test_volume.py
│   └── test_factory.py
├── evaluator/
│   ├── __init__.py
│   ├── test_condition.py
│   └── test_strategy_evaluator.py
├── simulator/
│   ├── __init__.py
│   ├── test_slippage.py
│   ├── test_fees.py
│   ├── test_position.py
│   └── test_trade_simulator.py
└── test_engine_e2e.py
```

---

## Task 1: Dependency + module skeleton

**Files:**
- Modify: `pyproject.toml` (add `pandas>=2.2` to `dependencies`)
- Create: `src/cryptozavr/application/backtest/__init__.py`
- Create: `src/cryptozavr/application/backtest/indicators/__init__.py`
- Create: `src/cryptozavr/application/backtest/evaluator/__init__.py`
- Create: `src/cryptozavr/application/backtest/simulator/__init__.py`
- Create: `tests/unit/application/backtest/__init__.py`
- Create: `tests/unit/application/backtest/indicators/__init__.py`
- Create: `tests/unit/application/backtest/evaluator/__init__.py`
- Create: `tests/unit/application/backtest/simulator/__init__.py`

- [ ] **Step 1: Add pandas to pyproject.toml**

Find the `[project]` → `dependencies` list and append:

```toml
    "pandas>=2.2",
```

- [ ] **Step 2: Sync dependency**

Run: `uv lock && uv sync`
Expected: `pandas` installed, `uv.lock` updated.

- [ ] **Step 3: Create module dirs + empty __init__.py files**

```bash
mkdir -p src/cryptozavr/application/backtest/{indicators,evaluator,simulator}
mkdir -p tests/unit/application/backtest/{indicators,evaluator,simulator}
```

Then create these exact files (each one-line or empty):

`src/cryptozavr/application/backtest/__init__.py`:
```python
"""Phase 2 sub-project A: hybrid backtesting engine."""
```

`src/cryptozavr/application/backtest/indicators/__init__.py`:
```python
"""Vectorized streaming indicators (SMA/EMA/RSI/MACD/ATR/Volume)."""
```

`src/cryptozavr/application/backtest/evaluator/__init__.py`:
```python
"""Per-bar condition evaluation with None-propagation on warm-up."""
```

`src/cryptozavr/application/backtest/simulator/__init__.py`:
```python
"""Event-driven trade lifecycle: slippage, fees, TP/SL, equity curve."""
```

All `tests/unit/application/backtest/**/__init__.py`: empty.

- [ ] **Step 4: Smoke-run existing suite**

Run: `uv run pytest tests/unit tests/contract -m "not integration" -q`
Expected: 555 passed (baseline unchanged — no code yet).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/cryptozavr/application/backtest tests/unit/application/backtest
git commit -F /tmp/commit-msg.txt
```

Write to `/tmp/commit-msg.txt` first:
```bash
chore(backtest): add pandas dep + empty module skeleton for sub-project A

First commit of Phase 2 sub-project A. Adds pandas>=2.2 as the only new
runtime dependency and scaffolds the application/backtest package tree
(indicators/evaluator/simulator subpackages + test mirror). No logic
yet — every subsequent commit adds a vertical slice with TDD.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## Task 2: Indicator Protocol + PriceSource extractor

**Files:**
- Create: `src/cryptozavr/application/backtest/indicators/base.py`
- Create: `src/cryptozavr/application/backtest/indicators/price.py`
- Create: `tests/unit/application/backtest/fixtures.py`
- Create: `tests/unit/application/backtest/indicators/test_price.py`

- [ ] **Step 1: Write failing tests + candle_df fixture**

`tests/unit/application/backtest/fixtures.py`:
```python
"""Shared test fixture: build a candle DataFrame from close prices."""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

import pandas as pd

def candle_df(
    closes: Sequence[str],
    *,
    high_bump: str = "1",
    low_bump: str = "1",
    volume: str = "1000",
) -> pd.DataFrame:
    """Build a DataFrame with len(closes) bars. Open == close for each bar;
    high = close + high_bump, low = close - low_bump. Timestamps are
    contiguous 1-minute UTC.

    Returned columns: open, high, low, close, volume, timestamp (dtype
    datetime64[ns, UTC] via pd.Timestamp). Numeric columns are float64.
    """
    import datetime as dt

    n = len(closes)
    start = dt.datetime(2026, 1, 1, 0, 0, 0, tzinfo=dt.UTC)
    rows = []
    for i, c in enumerate(closes):
        close_d = Decimal(c)
        rows.append(
            {
                "timestamp": start + dt.timedelta(minutes=i),
                "open": float(close_d),
                "high": float(close_d + Decimal(high_bump)),
                "low": float(close_d - Decimal(low_bump)),
                "close": float(close_d),
                "volume": float(Decimal(volume)),
            }
        )
    return pd.DataFrame(rows)
```

`tests/unit/application/backtest/indicators/test_price.py`:
```python
"""extract_price_series: DataFrame + PriceSource -> pd.Series[float]."""

from __future__ import annotations

import pandas as pd

from cryptozavr.application.backtest.indicators.price import extract_price_series
from cryptozavr.application.strategy.enums import PriceSource
from tests.unit.application.backtest.fixtures import candle_df

def test_open_source() -> None:
    df = candle_df(["100", "105", "110"])
    series = extract_price_series(df, PriceSource.OPEN)
    assert list(series) == [100.0, 105.0, 110.0]

def test_high_source() -> None:
    df = candle_df(["100", "105"], high_bump="2")
    series = extract_price_series(df, PriceSource.HIGH)
    assert list(series) == [102.0, 107.0]

def test_low_source() -> None:
    df = candle_df(["100", "105"], low_bump="3")
    series = extract_price_series(df, PriceSource.LOW)
    assert list(series) == [97.0, 102.0]

def test_close_source() -> None:
    df = candle_df(["100", "105", "110"])
    series = extract_price_series(df, PriceSource.CLOSE)
    assert list(series) == [100.0, 105.0, 110.0]

def test_hlc3_source() -> None:
    """HLC3 = (high + low + close) / 3 element-wise."""
    df = candle_df(["99"], high_bump="3", low_bump="0")
    # high=102, low=99, close=99 → HLC3 = 100
    series = extract_price_series(df, PriceSource.HLC3)
    assert series.iloc[0] == pd.Series([100.0]).iloc[0]
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `uv run pytest tests/unit/application/backtest/indicators/test_price.py -v`
Expected: FAIL with `ModuleNotFoundError: cryptozavr.application.backtest.indicators.price`.

- [ ] **Step 3: Implement base.py + price.py**

`src/cryptozavr/application/backtest/indicators/base.py`:
```python
"""Indicator Protocol shared by every streaming indicator.

All vectorized: compute() consumes a full DataFrame and returns a
pd.Series aligned to df.index with NaN during warm-up bars.
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd

class Indicator(Protocol):
    @property
    def period(self) -> int: ...

    def compute(self, df: pd.DataFrame) -> pd.Series:
        """One-pass vectorized compute. NaN entries represent warm-up.
        Series dtype is float64; evaluator converts to Decimal at read
        time when comparing against Decimal constants."""
        ...
```

`src/cryptozavr/application/backtest/indicators/price.py`:
```python
"""PriceSource -> pd.Series[float] extractor.

HLC3 is computed element-wise in float64 (tolerance-checked in tests).
Float math here is intentional — the full indicator pipeline runs on
numpy for speed, with Decimal conversion happening at the evaluator
boundary.
"""

from __future__ import annotations

import pandas as pd

from cryptozavr.application.strategy.enums import PriceSource

def extract_price_series(df: pd.DataFrame, source: PriceSource) -> pd.Series:
    if source is PriceSource.OPEN:
        return df["open"]
    if source is PriceSource.HIGH:
        return df["high"]
    if source is PriceSource.LOW:
        return df["low"]
    if source is PriceSource.CLOSE:
        return df["close"]
    if source is PriceSource.HLC3:
        return (df["high"] + df["low"] + df["close"]) / 3.0
    raise ValueError(f"unhandled PriceSource: {source!r}")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/application/backtest/indicators/test_price.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

`/tmp/commit-msg.txt`:
```bash
feat(backtest): Indicator Protocol + PriceSource series extractor

Base building block for sub-project A. `extract_price_series(df, source)`
resolves each PriceSource to the matching DataFrame column; HLC3 is
element-wise mean. Tests use `candle_df(closes, ...)` helper that we'll
reuse throughout the indicator suite.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/application/backtest/indicators/base.py \
        src/cryptozavr/application/backtest/indicators/price.py \
        tests/unit/application/backtest/fixtures.py \
        tests/unit/application/backtest/indicators/test_price.py
git commit -F /tmp/commit-msg.txt
```

---

## Task 3: SimpleMovingAverage (vectorized)

**Files:**
- Create: `src/cryptozavr/application/backtest/indicators/sma.py`
- Create: `tests/unit/application/backtest/indicators/test_sma.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/application/backtest/indicators/test_sma.py
"""SimpleMovingAverage vectorized: rolling mean over `period` bars."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cryptozavr.application.backtest.indicators.sma import SimpleMovingAverage
from cryptozavr.application.strategy.enums import PriceSource
from tests.unit.application.backtest.fixtures import candle_df

def test_warm_up_returns_nan_until_period_bars() -> None:
    sma = SimpleMovingAverage(period=3)
    series = sma.compute(candle_df(["10", "20"]))
    assert math.isnan(series.iloc[0])
    assert math.isnan(series.iloc[1])

def test_first_warm_value_matches_mean() -> None:
    sma = SimpleMovingAverage(period=3)
    series = sma.compute(candle_df(["10", "20", "30"]))
    assert math.isnan(series.iloc[1])
    assert series.iloc[2] == pytest.approx(20.0)

def test_window_rolls_on_subsequent_bars() -> None:
    sma = SimpleMovingAverage(period=3)
    series = sma.compute(candle_df(["10", "20", "30", "40"]))
    # window at bar 3 = (20, 30, 40), mean = 30
    assert series.iloc[3] == pytest.approx(30.0)

def test_period_one_emits_latest_every_bar() -> None:
    sma = SimpleMovingAverage(period=1)
    series = sma.compute(candle_df(["50", "55"]))
    assert series.iloc[0] == 50.0
    assert series.iloc[1] == 55.0

def test_uses_source_field() -> None:
    sma = SimpleMovingAverage(period=2, source=PriceSource.HIGH)
    df = candle_df(["100", "200"], high_bump="0")  # high == close
    series = sma.compute(df)
    assert series.iloc[1] == pytest.approx(150.0)

def test_period_zero_raises() -> None:
    with pytest.raises(ValueError, match="period must be > 0"):
        SimpleMovingAverage(period=0)

def test_period_negative_raises() -> None:
    with pytest.raises(ValueError, match="period must be > 0"):
        SimpleMovingAverage(period=-1)

@given(
    st.lists(
        st.floats(
            min_value=1.0,
            max_value=1_000_000.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=5,
        max_size=30,
    )
)
def test_property_sma_matches_naive_sliding_mean(values: list[float]) -> None:
    period = 3
    sma = SimpleMovingAverage(period=period)
    df = candle_df([str(v) for v in values])
    series = sma.compute(df)
    for i in range(period - 1):
        assert math.isnan(series.iloc[i])
    for i in range(period - 1, len(values)):
        expected = sum(values[i - period + 1 : i + 1]) / period
        assert series.iloc[i] == pytest.approx(expected, rel=1e-9)
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `uv run pytest tests/unit/application/backtest/indicators/test_sma.py -v`
Expected: FAIL with `ModuleNotFoundError` on `sma`.

- [ ] **Step 3: Implement SimpleMovingAverage**

```python
# src/cryptozavr/application/backtest/indicators/sma.py
"""SimpleMovingAverage: pd.Series.rolling(period).mean()."""

from __future__ import annotations

import pandas as pd

from cryptozavr.application.backtest.indicators.price import extract_price_series
from cryptozavr.application.strategy.enums import PriceSource

class SimpleMovingAverage:
    def __init__(
        self, period: int, source: PriceSource = PriceSource.CLOSE
    ) -> None:
        if period <= 0:
            raise ValueError(f"SMA period must be > 0 (got {period!r})")
        self._period = period
        self._source = source

    @property
    def period(self) -> int:
        return self._period

    def compute(self, df: pd.DataFrame) -> pd.Series:
        source_series = extract_price_series(df, self._source)
        return source_series.rolling(window=self._period, min_periods=self._period).mean()
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/application/backtest/indicators/test_sma.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

`/tmp/commit-msg.txt`:
```text
feat(backtest): SimpleMovingAverage vectorized (pd.Series.rolling.mean)

One-pass rolling mean over the selected PriceSource. NaN during warm-up
(first period-1 bars); match-within-tolerance property test against
naive sliding-window mean across random bounded series.
```

```bash
git add src/cryptozavr/application/backtest/indicators/sma.py \
        tests/unit/application/backtest/indicators/test_sma.py
git commit -F /tmp/commit-msg.txt
```

---

## Task 4: ExponentialMovingAverage (vectorized, SMA-seeded)

**Files:**
- Create: `src/cryptozavr/application/backtest/indicators/ema.py`
- Create: `tests/unit/application/backtest/indicators/test_ema.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/application/backtest/indicators/test_ema.py
"""ExponentialMovingAverage: SMA-seeded + alpha recurrence, vectorized."""

from __future__ import annotations

import math

import pytest

from cryptozavr.application.backtest.indicators.ema import (
    ExponentialMovingAverage,
)
from tests.unit.application.backtest.fixtures import candle_df

def test_warm_up_returns_nan_until_period_bars() -> None:
    ema = ExponentialMovingAverage(period=3)
    series = ema.compute(candle_df(["10", "20"]))
    assert math.isnan(series.iloc[0])
    assert math.isnan(series.iloc[1])

def test_first_warm_value_is_sma_of_first_period_bars() -> None:
    ema = ExponentialMovingAverage(period=3)
    series = ema.compute(candle_df(["10", "20", "30"]))
    assert series.iloc[2] == pytest.approx(20.0)

def test_subsequent_bar_applies_alpha_smoothing() -> None:
    """alpha = 2/(period+1) = 2/4 = 0.5 for period=3.
    seed at bar 2 = 20, next price = 40
    expected = 0.5 * 40 + 0.5 * 20 = 30"""
    ema = ExponentialMovingAverage(period=3)
    series = ema.compute(candle_df(["10", "20", "30", "40"]))
    assert series.iloc[3] == pytest.approx(30.0)

def test_constant_input_converges_to_that_value() -> None:
    ema = ExponentialMovingAverage(period=5)
    series = ema.compute(candle_df(["42.5"] * 10))
    assert series.iloc[-1] == pytest.approx(42.5)

def test_period_zero_raises() -> None:
    with pytest.raises(ValueError, match="period must be > 0"):
        ExponentialMovingAverage(period=0)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/application/backtest/indicators/test_ema.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement EMA**

```python
# src/cryptozavr/application/backtest/indicators/ema.py
"""ExponentialMovingAverage: SMA seed for first `period` bars, then
alpha * price + (1-alpha) * prev recurrence.

Implementation is a manual loop because pandas `.ewm(adjust=False)`
emits values from bar 0 without an SMA warm-up (produces a different
curve from the TA-Lib / TradingView convention). We keep the loop but
operate on numpy arrays — faster than per-row pandas access.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from cryptozavr.application.backtest.indicators.price import extract_price_series
from cryptozavr.application.strategy.enums import PriceSource

class ExponentialMovingAverage:
    def __init__(
        self, period: int, source: PriceSource = PriceSource.CLOSE
    ) -> None:
        if period <= 0:
            raise ValueError(f"EMA period must be > 0 (got {period!r})")
        self._period = period
        self._source = source

    @property
    def period(self) -> int:
        return self._period

    def compute(self, df: pd.DataFrame) -> pd.Series:
        prices = extract_price_series(df, self._source).to_numpy(dtype=np.float64)
        n = len(prices)
        out = np.full(n, np.nan, dtype=np.float64)
        if n < self._period:
            return pd.Series(out, index=df.index)
        alpha = 2.0 / (self._period + 1)
        # Seed: SMA of first `period` bars.
        seed = prices[: self._period].mean()
        out[self._period - 1] = seed
        prev = seed
        for i in range(self._period, n):
            prev = alpha * prices[i] + (1.0 - alpha) * prev
            out[i] = prev
        return pd.Series(out, index=df.index)
```

- [ ] **Step 4: Verify green**

Run: `uv run pytest tests/unit/application/backtest/indicators/test_ema.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

`/tmp/commit-msg.txt`:
```bash
feat(backtest): ExponentialMovingAverage (SMA-seeded, alpha smoothing)

Numpy-backed loop: SMA of first `period` bars as seed, then
EMA_t = alpha * price + (1-alpha) * EMA_{t-1} with alpha = 2/(period+1).
Matches TA-Lib / TradingView convention. Pandas `.ewm` gives a
different curve (no warm-up), so we use manual numpy iteration.
```

```bash
git add src/cryptozavr/application/backtest/indicators/ema.py \
        tests/unit/application/backtest/indicators/test_ema.py
git commit -F /tmp/commit-msg.txt
```

---

## Task 5: RelativeStrengthIndex (Wilder, vectorized)

**Files:**
- Create: `src/cryptozavr/application/backtest/indicators/rsi.py`
- Create: `tests/unit/application/backtest/indicators/test_rsi.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/application/backtest/indicators/test_rsi.py
"""RelativeStrengthIndex: Wilder smoothing with RSI=100 on no-loss."""

from __future__ import annotations

import math

import pytest

from cryptozavr.application.backtest.indicators.rsi import RelativeStrengthIndex
from tests.unit.application.backtest.fixtures import candle_df

def test_first_period_bars_nan() -> None:
    rsi = RelativeStrengthIndex(period=3)
    series = rsi.compute(candle_df(["100", "101", "102"]))
    assert math.isnan(series.iloc[0])
    assert math.isnan(series.iloc[1])
    assert math.isnan(series.iloc[2])

def test_all_gains_gives_rsi_100() -> None:
    """All deltas positive ⇒ avg_loss = 0 ⇒ RSI = 100 convention."""
    rsi = RelativeStrengthIndex(period=3)
    series = rsi.compute(candle_df(["100", "101", "102", "103"]))
    assert series.iloc[3] == pytest.approx(100.0)

def test_all_losses_gives_rsi_zero() -> None:
    rsi = RelativeStrengthIndex(period=3)
    series = rsi.compute(candle_df(["100", "99", "98", "97"]))
    assert series.iloc[3] == pytest.approx(0.0)

def test_balanced_gives_rsi_50() -> None:
    """Symmetric +10 / -10 ⇒ avg_gain == avg_loss ⇒ RS = 1 ⇒ RSI = 50."""
    rsi = RelativeStrengthIndex(period=2)
    series = rsi.compute(candle_df(["100", "110", "100"]))
    assert series.iloc[2] == pytest.approx(50.0)

def test_hand_computed_mixed_series() -> None:
    """period=2; closes [100, 110, 105, 108].
    Deltas: +10, -5, +3. Seed (first 2): avg_gain=5, avg_loss=2.5.
    Next: avg_gain = (5*1 + 3)/2 = 4; avg_loss = (2.5*1 + 0)/2 = 1.25
    RS = 3.2 ⇒ RSI = 100 - 100/4.2 ≈ 76.190476..."""
    rsi = RelativeStrengthIndex(period=2)
    series = rsi.compute(candle_df(["100", "110", "105", "108"]))
    assert series.iloc[3] == pytest.approx(100.0 - 100.0 / 4.2, rel=1e-10)

def test_period_zero_raises() -> None:
    with pytest.raises(ValueError, match="period must be > 0"):
        RelativeStrengthIndex(period=0)
```

- [ ] **Step 2: Verify red**

Run: `uv run pytest tests/unit/application/backtest/indicators/test_rsi.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement RSI**

```python
# src/cryptozavr/application/backtest/indicators/rsi.py
"""RelativeStrengthIndex (Wilder smoothing).

Warm after `period + 1` bars — needs `period` deltas.
Edge: avg_loss == 0 ⇒ RSI = 100 (max-bullish convention).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from cryptozavr.application.backtest.indicators.price import extract_price_series
from cryptozavr.application.strategy.enums import PriceSource

class RelativeStrengthIndex:
    def __init__(
        self, period: int = 14, source: PriceSource = PriceSource.CLOSE
    ) -> None:
        if period <= 0:
            raise ValueError(f"RSI period must be > 0 (got {period!r})")
        self._period = period
        self._source = source

    @property
    def period(self) -> int:
        return self._period

    def compute(self, df: pd.DataFrame) -> pd.Series:
        prices = extract_price_series(df, self._source).to_numpy(dtype=np.float64)
        n = len(prices)
        out = np.full(n, np.nan, dtype=np.float64)
        if n < self._period + 1:
            return pd.Series(out, index=df.index)
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        # Seed: SMA of first `period` gains / losses.
        avg_gain = gains[: self._period].mean()
        avg_loss = losses[: self._period].mean()
        out[self._period] = _rsi_from_avgs(avg_gain, avg_loss)
        # Wilder smoothing for subsequent bars.
        for i in range(self._period + 1, n):
            gain_i = gains[i - 1]
            loss_i = losses[i - 1]
            avg_gain = (avg_gain * (self._period - 1) + gain_i) / self._period
            avg_loss = (avg_loss * (self._period - 1) + loss_i) / self._period
            out[i] = _rsi_from_avgs(avg_gain, avg_loss)
        return pd.Series(out, index=df.index)

def _rsi_from_avgs(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)
```

- [ ] **Step 4: Verify green**

Run: `uv run pytest tests/unit/application/backtest/indicators/test_rsi.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

`/tmp/commit-msg.txt`:
```bash
feat(backtest): RelativeStrengthIndex (Wilder smoothing + RSI=100 convention)

Classic Wilder RSI: seed with SMA of first `period` gains/losses, then
smoothed recurrence. Edge case avg_loss == 0 returns 100 (max bullish).
Hand-computed ground-truth test pins against 100 - 100/(1+RS).
```

```bash
git add src/cryptozavr/application/backtest/indicators/rsi.py \
        tests/unit/application/backtest/indicators/test_rsi.py
git commit -F /tmp/commit-msg.txt
```

---

## Task 6: MACD line (fast EMA − slow EMA)

**Files:**
- Create: `src/cryptozavr/application/backtest/indicators/macd.py`
- Create: `tests/unit/application/backtest/indicators/test_macd.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/application/backtest/indicators/test_macd.py
"""MACD line = fast EMA - slow EMA."""

from __future__ import annotations

import math

import pytest

from cryptozavr.application.backtest.indicators.ema import ExponentialMovingAverage
from cryptozavr.application.backtest.indicators.macd import MACD
from tests.unit.application.backtest.fixtures import candle_df

def test_warm_up_nan_until_slow_period() -> None:
    macd = MACD(fast=2, slow=4)
    series = macd.compute(candle_df(["100", "101", "103"]))
    assert math.isnan(series.iloc[0])
    assert math.isnan(series.iloc[2])

def test_line_equals_fast_ema_minus_slow_ema() -> None:
    macd = MACD(fast=2, slow=4)
    fast_ref = ExponentialMovingAverage(period=2)
    slow_ref = ExponentialMovingAverage(period=4)
    closes = ["100", "101", "103", "102", "105", "104", "107"]
    df = candle_df(closes)
    macd_series = macd.compute(df)
    fast_series = fast_ref.compute(df)
    slow_series = slow_ref.compute(df)
    for i in range(len(closes)):
        if math.isnan(macd_series.iloc[i]):
            assert math.isnan(slow_series.iloc[i])
        else:
            assert macd_series.iloc[i] == pytest.approx(
                fast_series.iloc[i] - slow_series.iloc[i], rel=1e-12
            )

def test_constant_input_gives_zero() -> None:
    macd = MACD(fast=2, slow=4)
    series = macd.compute(candle_df(["100"] * 20))
    assert series.iloc[-1] == pytest.approx(0.0, abs=1e-12)

def test_fast_must_be_less_than_slow() -> None:
    with pytest.raises(ValueError, match="fast must be < slow"):
        MACD(fast=10, slow=10)
    with pytest.raises(ValueError, match="fast must be < slow"):
        MACD(fast=20, slow=10)

def test_nonpositive_periods_raise() -> None:
    with pytest.raises(ValueError, match="fast/slow must be > 0"):
        MACD(fast=0, slow=10)
    with pytest.raises(ValueError, match="fast/slow must be > 0"):
        MACD(fast=5, slow=0)
```

- [ ] **Step 2: Verify red**

Run: `uv run pytest tests/unit/application/backtest/indicators/test_macd.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement MACD**

```python
# src/cryptozavr/application/backtest/indicators/macd.py
"""MACD line (fast EMA - slow EMA). Signal + histogram deferred until
a 2A+1 DSL extension exposes them separately."""

from __future__ import annotations

import pandas as pd

from cryptozavr.application.backtest.indicators.ema import ExponentialMovingAverage
from cryptozavr.application.strategy.enums import PriceSource

class MACD:
    def __init__(
        self,
        *,
        fast: int = 12,
        slow: int = 26,
        source: PriceSource = PriceSource.CLOSE,
    ) -> None:
        if fast <= 0 or slow <= 0:
            raise ValueError(
                f"MACD fast/slow must be > 0 (got fast={fast}, slow={slow})"
            )
        if fast >= slow:
            raise ValueError(
                f"MACD fast must be < slow (got fast={fast}, slow={slow})"
            )
        self._fast = ExponentialMovingAverage(period=fast, source=source)
        self._slow = ExponentialMovingAverage(period=slow, source=source)
        self._slow_period = slow

    @property
    def period(self) -> int:
        return self._slow_period

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return self._fast.compute(df) - self._slow.compute(df)
```

- [ ] **Step 4: Verify green**

Run: `uv run pytest tests/unit/application/backtest/indicators/test_macd.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

`/tmp/commit-msg.txt`:
```text
feat(backtest): MACD line (fast EMA - slow EMA)

Composes two ExponentialMovingAverage instances. Signal + histogram
deferred until a 2A+1 DSL extension exposes them. Rejects fast >= slow
at construction.
```

```bash
git add src/cryptozavr/application/backtest/indicators/macd.py \
        tests/unit/application/backtest/indicators/test_macd.py
git commit -F /tmp/commit-msg.txt
```

---

## Task 7: AverageTrueRange (Wilder, vectorized)

**Files:**
- Create: `src/cryptozavr/application/backtest/indicators/atr.py`
- Create: `tests/unit/application/backtest/indicators/test_atr.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/application/backtest/indicators/test_atr.py
"""AverageTrueRange: Wilder-smoothed TR = max(H-L, |H-prevC|, |L-prevC|)."""

from __future__ import annotations

import math

import pytest

from cryptozavr.application.backtest.indicators.atr import AverageTrueRange
from tests.unit.application.backtest.fixtures import candle_df

def test_first_period_bars_nan() -> None:
    atr = AverageTrueRange(period=3)
    # Period=3 needs prev_close bar + 3 TR bars = 4 bars before warm.
    series = atr.compute(candle_df(["100", "101", "102"]))
    assert math.isnan(series.iloc[0])
    assert math.isnan(series.iloc[2])

def test_seeded_mean_of_first_period_trs() -> None:
    """closes = [100, 103, 105, 107], bumps high=+1/low=-1 by fixture default.
    Bar 0: h=101, l=99, c=100 (seeds prev_close)
    Bar 1: h=104, l=102, c=103, prev_close=100 → TR=max(2, |104-100|, |102-100|)=4
    Bar 2: h=106, l=104, c=105, prev_close=103 → TR=max(2, |106-103|, |104-103|)=3
    Bar 3: h=108, l=106, c=107, prev_close=105 → TR=max(2, |108-105|, |106-105|)=3
    Seed (period=3): (4+3+3)/3 = 10/3 ≈ 3.333"""
    atr = AverageTrueRange(period=3)
    series = atr.compute(candle_df(["100", "103", "105", "107"]))
    assert series.iloc[3] == pytest.approx(10.0 / 3.0, rel=1e-12)

def test_wilder_smoothing_after_seed() -> None:
    """Continue the series above: bar 4 adds TR.
    Bar 4: h=114, l=110, c=113, prev_close=107 → TR=max(4, |114-107|, |110-107|)=7
    ATR_4 = (ATR_3 * (period-1) + TR_4) / period
          = (10/3 * 2 + 7) / 3 = (20/3 + 7) / 3 = (41/3)/3 = 41/9"""
    atr = AverageTrueRange(period=3)
    closes = ["100", "103", "105", "107", "113"]
    # Need to override high/low bumps for bar 4 — simplest: recompute via fixture.
    # fixture defaults: high=close+1, low=close-1. That gives h=114, l=112 for c=113.
    # Recompute bar 4 TR: prev_close=107. h=114, l=112 → |114-107|=7, |112-107|=5, h-l=2. max=7. OK.
    series = atr.compute(candle_df(closes))
    assert series.iloc[4] == pytest.approx(41.0 / 9.0, rel=1e-12)

def test_period_zero_raises() -> None:
    with pytest.raises(ValueError, match="period must be > 0"):
        AverageTrueRange(period=0)

def test_period_one_valid() -> None:
    atr = AverageTrueRange(period=1)
    series = atr.compute(candle_df(["100", "103"]))
    # Bar 1: h=104, l=102, prev_close=100. TR=max(2, 4, 2)=4. Seed mean of 1 TR = 4.
    assert series.iloc[1] == pytest.approx(4.0)
```

- [ ] **Step 2: Verify red**

Run: `uv run pytest tests/unit/application/backtest/indicators/test_atr.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement ATR**

```python
# src/cryptozavr/application/backtest/indicators/atr.py
"""AverageTrueRange (Wilder smoothing).

TR_t = max(high_t - low_t, |high_t - close_{t-1}|, |low_t - close_{t-1}|)
Seed: mean of first `period` TRs. Warm after period+1 bars (bar 0 seeds
prev_close without emitting a TR). Not parameterised by PriceSource —
TR is an OHLC-specific concept.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

class AverageTrueRange:
    def __init__(self, period: int = 14) -> None:
        if period <= 0:
            raise ValueError(f"ATR period must be > 0 (got {period!r})")
        self._period = period

    @property
    def period(self) -> int:
        return self._period

    def compute(self, df: pd.DataFrame) -> pd.Series:
        highs = df["high"].to_numpy(dtype=np.float64)
        lows = df["low"].to_numpy(dtype=np.float64)
        closes = df["close"].to_numpy(dtype=np.float64)
        n = len(closes)
        out = np.full(n, np.nan, dtype=np.float64)
        if n < self._period + 1:
            return pd.Series(out, index=df.index)
        prev_close = closes[:-1]
        tr_from_bar1 = np.maximum.reduce(
            [
                highs[1:] - lows[1:],
                np.abs(highs[1:] - prev_close),
                np.abs(lows[1:] - prev_close),
            ]
        )
        # Seed: mean of first `period` TRs (tr_from_bar1 starts at bar index 1).
        seed = tr_from_bar1[: self._period].mean()
        out[self._period] = seed
        prev_atr = seed
        for i in range(self._period + 1, n):
            tr_i = tr_from_bar1[i - 1]
            prev_atr = (prev_atr * (self._period - 1) + tr_i) / self._period
            out[i] = prev_atr
        return pd.Series(out, index=df.index)
```

- [ ] **Step 4: Verify green**

Run: `uv run pytest tests/unit/application/backtest/indicators/test_atr.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

`/tmp/commit-msg.txt`:
```text
feat(backtest): AverageTrueRange (Wilder smoothing, vectorized TR)

TR_t = max(high-low, |high-prev_close|, |low-prev_close|), computed
element-wise via numpy.maximum.reduce. Seed = mean of first `period`
TRs; post-seed uses Wilder's (ATR_prev * (n-1) + TR_t) / n recurrence.
OHLC-only — ignores PriceSource by construction.
```

```bash
git add src/cryptozavr/application/backtest/indicators/atr.py \
        tests/unit/application/backtest/indicators/test_atr.py
git commit -F /tmp/commit-msg.txt
```

---

## Task 8: Volume + IndicatorFactory

**Files:**
- Create: `src/cryptozavr/application/backtest/indicators/volume.py`
- Create: `src/cryptozavr/application/backtest/indicators/factory.py`
- Create: `tests/unit/application/backtest/indicators/test_volume.py`
- Create: `tests/unit/application/backtest/indicators/test_factory.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/application/backtest/indicators/test_volume.py
"""VolumeIndicator: identity on df['volume']."""

from __future__ import annotations

import pytest

from cryptozavr.application.backtest.indicators.volume import VolumeIndicator
from tests.unit.application.backtest.fixtures import candle_df

def test_returns_volume_series() -> None:
    v = VolumeIndicator()
    df = candle_df(["100", "105"], volume="1234.5")
    series = v.compute(df)
    assert list(series) == [1234.5, 1234.5]

def test_no_warm_up_period_one() -> None:
    assert VolumeIndicator().period == 1

def test_different_volumes_per_bar() -> None:
    """Manually build a DataFrame with varying volume."""
    import pandas as pd
    df = pd.DataFrame(
        {
            "open": [1.0, 1.0],
            "high": [2.0, 2.0],
            "low": [0.5, 0.5],
            "close": [1.0, 1.0],
            "volume": [100.0, 250.0],
        }
    )
    series = VolumeIndicator().compute(df)
    assert list(series) == [100.0, 250.0]
```

```python
# tests/unit/application/backtest/indicators/test_factory.py
"""create_indicator + compute_all: IndicatorRef -> computed pd.Series."""

from __future__ import annotations

from cryptozavr.application.backtest.indicators.atr import AverageTrueRange
from cryptozavr.application.backtest.indicators.ema import ExponentialMovingAverage
from cryptozavr.application.backtest.indicators.factory import (
    compute_all,
    create_indicator,
)
from cryptozavr.application.backtest.indicators.macd import MACD
from cryptozavr.application.backtest.indicators.rsi import RelativeStrengthIndex
from cryptozavr.application.backtest.indicators.sma import SimpleMovingAverage
from cryptozavr.application.backtest.indicators.volume import VolumeIndicator
from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
    StrategySide,
)
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    IndicatorRef,
    StrategyEntry,
    StrategyExit,
    StrategySpec,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from tests.unit.application.backtest.fixtures import candle_df
from decimal import Decimal

def _symbol() -> Symbol:
    return Symbol(
        venue=VenueId.KUCOIN,
        base="BTC",
        quote="USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )

def test_sma_ref_creates_sma() -> None:
    ind = create_indicator(IndicatorRef(kind=IndicatorKind.SMA, period=20))
    assert isinstance(ind, SimpleMovingAverage)
    assert ind.period == 20

def test_ema_ref_creates_ema() -> None:
    assert isinstance(
        create_indicator(IndicatorRef(kind=IndicatorKind.EMA, period=12)),
        ExponentialMovingAverage,
    )

def test_rsi_ref_creates_rsi() -> None:
    assert isinstance(
        create_indicator(IndicatorRef(kind=IndicatorKind.RSI, period=14)),
        RelativeStrengthIndex,
    )

def test_macd_ref_creates_macd_slow_from_period() -> None:
    ind = create_indicator(IndicatorRef(kind=IndicatorKind.MACD, period=26))
    assert isinstance(ind, MACD)
    assert ind.period == 26

def test_atr_ref_creates_atr() -> None:
    assert isinstance(
        create_indicator(IndicatorRef(kind=IndicatorKind.ATR, period=14)),
        AverageTrueRange,
    )

def test_volume_ref_creates_volume() -> None:
    assert isinstance(
        create_indicator(IndicatorRef(kind=IndicatorKind.VOLUME, period=1)),
        VolumeIndicator,
    )

def test_compute_all_interns_same_ref_once() -> None:
    """A spec referencing the same IndicatorRef in entry + exit must yield
    exactly one Series (interning)."""
    fast = IndicatorRef(kind=IndicatorKind.EMA, period=12)
    slow = IndicatorRef(kind=IndicatorKind.EMA, period=26)
    spec = StrategySpec(
        name="crossover",
        description="d",
        venue=VenueId.KUCOIN,
        symbol=_symbol(),
        timeframe=Timeframe.H1,
        entry=StrategyEntry(
            side=StrategySide.LONG,
            conditions=(
                Condition(lhs=fast, op=ComparatorOp.CROSSES_ABOVE, rhs=slow),
            ),
        ),
        exit=StrategyExit(
            conditions=(
                Condition(lhs=fast, op=ComparatorOp.CROSSES_BELOW, rhs=slow),
            ),
            take_profit_pct=Decimal("0.05"),
        ),
        size_pct=Decimal("0.25"),
    )
    df = candle_df([str(100 + i) for i in range(30)])
    series_map = compute_all(spec, df)
    assert set(series_map.keys()) == {fast, slow}  # exactly 2 unique refs
    assert len(series_map[fast]) == 30
```

- [ ] **Step 2: Verify red**

Run: `uv run pytest tests/unit/application/backtest/indicators/test_volume.py tests/unit/application/backtest/indicators/test_factory.py -v`
Expected: FAIL `ModuleNotFoundError` on volume / factory.

- [ ] **Step 3: Implement Volume + Factory**

```python
# src/cryptozavr/application/backtest/indicators/volume.py
"""VolumeIndicator: identity on df['volume']."""

from __future__ import annotations

import pandas as pd

class VolumeIndicator:
    @property
    def period(self) -> int:
        return 1

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["volume"].astype("float64")
```

```python
# src/cryptozavr/application/backtest/indicators/factory.py
"""IndicatorFactory: IndicatorRef -> computed pd.Series.

`compute_all(spec, df)` walks entry + exit conditions, collects unique
IndicatorRef instances (Pydantic frozen model — hashable), and invokes
each indicator once. Returns a dict keyed by ref.
"""

from __future__ import annotations

import pandas as pd

from cryptozavr.application.backtest.indicators.atr import AverageTrueRange
from cryptozavr.application.backtest.indicators.base import Indicator
from cryptozavr.application.backtest.indicators.ema import ExponentialMovingAverage
from cryptozavr.application.backtest.indicators.macd import MACD
from cryptozavr.application.backtest.indicators.rsi import RelativeStrengthIndex
from cryptozavr.application.backtest.indicators.sma import SimpleMovingAverage
from cryptozavr.application.backtest.indicators.volume import VolumeIndicator
from cryptozavr.application.strategy.enums import IndicatorKind
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    IndicatorRef,
    StrategySpec,
)

def create_indicator(ref: IndicatorRef) -> Indicator:
    if ref.kind is IndicatorKind.SMA:
        return SimpleMovingAverage(period=ref.period, source=ref.source)
    if ref.kind is IndicatorKind.EMA:
        return ExponentialMovingAverage(period=ref.period, source=ref.source)
    if ref.kind is IndicatorKind.RSI:
        return RelativeStrengthIndex(period=ref.period, source=ref.source)
    if ref.kind is IndicatorKind.MACD:
        return MACD(fast=12, slow=ref.period, source=ref.source)
    if ref.kind is IndicatorKind.ATR:
        return AverageTrueRange(period=ref.period)
    if ref.kind is IndicatorKind.VOLUME:
        return VolumeIndicator()
    raise ValueError(f"unhandled IndicatorKind: {ref.kind!r}")

def _collect_refs_from_conditions(
    conditions: tuple[Condition, ...],
) -> list[IndicatorRef]:
    refs: list[IndicatorRef] = []
    for c in conditions:
        refs.append(c.lhs)
        if isinstance(c.rhs, IndicatorRef):
            refs.append(c.rhs)
    return refs

def compute_all(
    spec: StrategySpec, df: pd.DataFrame
) -> dict[IndicatorRef, pd.Series]:
    all_refs: list[IndicatorRef] = [
        *_collect_refs_from_conditions(spec.entry.conditions),
        *_collect_refs_from_conditions(spec.exit.conditions),
    ]
    unique: dict[IndicatorRef, pd.Series] = {}
    for ref in all_refs:
        if ref not in unique:
            unique[ref] = create_indicator(ref).compute(df)
    return unique
```

- [ ] **Step 4: Verify green**

Run: `uv run pytest tests/unit/application/backtest/indicators/ -q`
Expected: all indicator tests pass (cumulative: ~40).

- [ ] **Step 5: Commit**

`/tmp/commit-msg.txt`:
```text
feat(backtest): VolumeIndicator + IndicatorFactory (spec -> series dict)

Volume is identity on the volume column. `create_indicator` maps one
IndicatorRef to the right concrete class; `compute_all(spec, df)`
interns same-IndicatorRef occurrences across entry + exit so we only
compute each series once.
```

```bash
git add src/cryptozavr/application/backtest/indicators/volume.py \
        src/cryptozavr/application/backtest/indicators/factory.py \
        tests/unit/application/backtest/indicators/test_volume.py \
        tests/unit/application/backtest/indicators/test_factory.py
git commit -F /tmp/commit-msg.txt
```

---

## Task 9: Condition evaluator + StrategyEvaluator + SignalTick

**Files:**
- Create: `src/cryptozavr/application/backtest/evaluator/signals.py`
- Create: `src/cryptozavr/application/backtest/evaluator/condition.py`
- Create: `src/cryptozavr/application/backtest/evaluator/strategy_evaluator.py`
- Create: `tests/unit/application/backtest/evaluator/test_condition.py`
- Create: `tests/unit/application/backtest/evaluator/test_strategy_evaluator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/application/backtest/evaluator/test_condition.py
"""evaluate_condition: all 6 ComparatorOps, None-propagation on NaN."""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd

from cryptozavr.application.backtest.evaluator.condition import evaluate_condition
from cryptozavr.application.strategy.enums import ComparatorOp, IndicatorKind
from cryptozavr.application.strategy.strategy_spec import Condition, IndicatorRef

_REF_A = IndicatorRef(kind=IndicatorKind.SMA, period=1)
_REF_B = IndicatorRef(kind=IndicatorKind.SMA, period=2)

def _series_map(a: list[float], b: list[float] | None = None) -> dict:
    sm: dict = {_REF_A: pd.Series(a, dtype="float64")}
    if b is not None:
        sm[_REF_B] = pd.Series(b, dtype="float64")
    return sm

def test_gt_true() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.GT, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([100.0]), 0) is True

def test_gt_false() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.GT, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([10.0]), 0) is False

def test_gte_equal() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.GTE, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([50.0]), 0) is True

def test_lt_true() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.LT, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([10.0]), 0) is True

def test_lte_equal() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.LTE, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([50.0]), 0) is True

def test_crosses_above_true_on_crossing_bar() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.CROSSES_ABOVE, rhs=Decimal("50"))
    # prev=40, curr=60 → crosses above 50
    assert evaluate_condition(cond, _series_map([40.0, 60.0]), 1) is True

def test_crosses_above_false_when_both_above() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.CROSSES_ABOVE, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([60.0, 70.0]), 1) is False

def test_crosses_below_true() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.CROSSES_BELOW, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([60.0, 40.0]), 1) is True

def test_crosses_op_none_on_bar_zero() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.CROSSES_ABOVE, rhs=Decimal("50"))
    # bar 0: no previous value available
    assert evaluate_condition(cond, _series_map([40.0]), 0) is None

def test_none_on_nan_lhs() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.GT, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([float("nan")]), 0) is None

def test_indicator_vs_indicator() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.GTE, rhs=_REF_B)
    assert evaluate_condition(cond, _series_map([100.0], [100.0]), 0) is True
    assert evaluate_condition(cond, _series_map([50.0], [100.0]), 0) is False

def test_equal_then_cross_fires() -> None:
    """prev_lhs == prev_rhs AND curr_lhs > curr_rhs ⇒ CROSSES_ABOVE True
    (canonical `<=` left side)."""
    cond = Condition(lhs=_REF_A, op=ComparatorOp.CROSSES_ABOVE, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([50.0, 51.0]), 1) is True

def test_nan_in_previous_returns_none_for_crossing() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.CROSSES_ABOVE, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([float("nan"), 60.0]), 1) is None
```

```python
# tests/unit/application/backtest/evaluator/test_strategy_evaluator.py
"""StrategyEvaluator.tick → SignalTick(entry, exit) AND/OR-folded."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from cryptozavr.application.backtest.evaluator.signals import SignalTick
from cryptozavr.application.backtest.evaluator.strategy_evaluator import (
    StrategyEvaluator,
)
from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
    StrategySide,
)
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    IndicatorRef,
    StrategyEntry,
    StrategyExit,
    StrategySpec,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import MarketType, VenueId

def _symbol() -> Symbol:
    return Symbol(
        venue=VenueId.KUCOIN,
        base="BTC",
        quote="USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )

def _spec_with_conditions(
    *,
    entry_conds: tuple,
    exit_conds: tuple,
    tp: Decimal | None = None,
    sl: Decimal | None = None,
) -> StrategySpec:
    return StrategySpec(
        name="test",
        description="d",
        venue=VenueId.KUCOIN,
        symbol=_symbol(),
        timeframe=Timeframe.H1,
        entry=StrategyEntry(side=StrategySide.LONG, conditions=entry_conds),
        exit=StrategyExit(conditions=exit_conds, take_profit_pct=tp, stop_loss_pct=sl),
        size_pct=Decimal("0.25"),
    )

_REF = IndicatorRef(kind=IndicatorKind.SMA, period=1)

def test_tick_returns_signal_tick() -> None:
    spec = _spec_with_conditions(
        entry_conds=(
            Condition(lhs=_REF, op=ComparatorOp.GT, rhs=Decimal("50")),
        ),
        exit_conds=(
            Condition(lhs=_REF, op=ComparatorOp.LT, rhs=Decimal("50")),
        ),
    )
    evalr = StrategyEvaluator(spec, {_REF: pd.Series([100.0], dtype="float64")})
    tick = evalr.tick(0)
    assert tick == SignalTick(bar_index=0, entry_signal=True, exit_signal=False)

def test_and_fold_entry_multi_condition() -> None:
    spec = _spec_with_conditions(
        entry_conds=(
            Condition(lhs=_REF, op=ComparatorOp.GT, rhs=Decimal("50")),
            Condition(lhs=_REF, op=ComparatorOp.LT, rhs=Decimal("200")),
        ),
        exit_conds=(),
        tp=Decimal("0.05"),
    )
    evalr = StrategyEvaluator(spec, {_REF: pd.Series([100.0, 40.0, 300.0], dtype="float64")})
    assert evalr.tick(0).entry_signal is True  # 100 in (50, 200)
    assert evalr.tick(1).entry_signal is False  # 40 < 50
    assert evalr.tick(2).entry_signal is False  # 300 > 200

def test_or_fold_exit() -> None:
    spec = _spec_with_conditions(
        entry_conds=(
            Condition(lhs=_REF, op=ComparatorOp.GT, rhs=Decimal("0")),
        ),
        exit_conds=(
            Condition(lhs=_REF, op=ComparatorOp.LT, rhs=Decimal("10")),
            Condition(lhs=_REF, op=ComparatorOp.GT, rhs=Decimal("1000")),
        ),
    )
    evalr = StrategyEvaluator(spec, {_REF: pd.Series([5.0, 500.0, 2000.0], dtype="float64")})
    assert evalr.tick(0).exit_signal is True  # 5 < 10
    assert evalr.tick(1).exit_signal is False  # neither branch
    assert evalr.tick(2).exit_signal is True  # 2000 > 1000

def test_exit_with_zero_conditions_emits_false() -> None:
    """TP/SL-only exit: exit_signal must be False (not None) so simulator
    knows TP/SL is the only way out."""
    spec = _spec_with_conditions(
        entry_conds=(
            Condition(lhs=_REF, op=ComparatorOp.GT, rhs=Decimal("0")),
        ),
        exit_conds=(),
        tp=Decimal("0.05"),
    )
    evalr = StrategyEvaluator(spec, {_REF: pd.Series([10.0], dtype="float64")})
    assert evalr.tick(0).exit_signal is False

def test_none_propagates_on_warmup() -> None:
    spec = _spec_with_conditions(
        entry_conds=(
            Condition(lhs=_REF, op=ComparatorOp.GT, rhs=Decimal("0")),
        ),
        exit_conds=(),
        tp=Decimal("0.05"),
    )
    evalr = StrategyEvaluator(spec, {_REF: pd.Series([float("nan"), 10.0], dtype="float64")})
    tick0 = evalr.tick(0)
    assert tick0.entry_signal is None
    assert tick0.exit_signal is False  # no exit conditions so False regardless
    tick1 = evalr.tick(1)
    assert tick1.entry_signal is True
```

- [ ] **Step 2: Verify red**

Run: `uv run pytest tests/unit/application/backtest/evaluator/ -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement evaluator modules**

```python
# src/cryptozavr/application/backtest/evaluator/signals.py
"""Per-bar signal output from StrategyEvaluator."""

from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class SignalTick:
    bar_index: int
    entry_signal: bool | None
    exit_signal: bool | None
```

```python
# src/cryptozavr/application/backtest/evaluator/condition.py
"""evaluate_condition: read pre-computed series at bar_index, apply op.

Returns None when:
- Any referenced IndicatorRef has NaN at bar_index (warming up).
- A crossing op has no previous bar (bar_index == 0) or NaN in previous.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from decimal import Decimal

import pandas as pd

from cryptozavr.application.strategy.enums import ComparatorOp
from cryptozavr.application.strategy.strategy_spec import Condition, IndicatorRef

def _current_value(
    side: IndicatorRef | Decimal,
    series_map: dict[IndicatorRef, pd.Series],
    bar_index: int,
) -> float | None:
    if isinstance(side, Decimal):
        return float(side)
    v = series_map[side].iloc[bar_index]
    if isinstance(v, float) and math.isnan(v):
        return None
    return float(v)

def _previous_value(
    side: IndicatorRef | Decimal,
    series_map: dict[IndicatorRef, pd.Series],
    bar_index: int,
) -> float | None:
    if bar_index == 0:
        return float(side) if isinstance(side, Decimal) else None
    if isinstance(side, Decimal):
        return float(side)
    v = series_map[side].iloc[bar_index - 1]
    if isinstance(v, float) and math.isnan(v):
        return None
    return float(v)

_SIMPLE_OPS: dict[ComparatorOp, Callable[[float, float], bool]] = {
    ComparatorOp.GT: lambda a, b: a > b,
    ComparatorOp.GTE: lambda a, b: a >= b,
    ComparatorOp.LT: lambda a, b: a < b,
    ComparatorOp.LTE: lambda a, b: a <= b,
}

def evaluate_condition(
    condition: Condition,
    series_map: dict[IndicatorRef, pd.Series],
    bar_index: int,
) -> bool | None:
    curr_lhs = _current_value(condition.lhs, series_map, bar_index)
    curr_rhs = _current_value(condition.rhs, series_map, bar_index)
    if curr_lhs is None or curr_rhs is None:
        return None
    op = condition.op
    simple = _SIMPLE_OPS.get(op)
    if simple is not None:
        return simple(curr_lhs, curr_rhs)
    prev_lhs = _previous_value(condition.lhs, series_map, bar_index)
    prev_rhs = _previous_value(condition.rhs, series_map, bar_index)
    if prev_lhs is None or prev_rhs is None:
        return None
    if op is ComparatorOp.CROSSES_ABOVE:
        return prev_lhs <= prev_rhs and curr_lhs > curr_rhs
    if op is ComparatorOp.CROSSES_BELOW:
        return prev_lhs >= prev_rhs and curr_lhs < curr_rhs
    raise ValueError(f"unhandled ComparatorOp: {op!r}")
```

```python
# src/cryptozavr/application/backtest/evaluator/strategy_evaluator.py
"""StrategyEvaluator.tick(bar_index) -> SignalTick.

Entry conditions AND-folded; exit conditions OR-folded. Either fold
returns None if any contributing condition is None (warm-up propagates).
Zero exit conditions emit exit_signal=False (not None) once at least
one entry is past warm-up — so the simulator can still act on TP/SL.
"""

from __future__ import annotations

import pandas as pd

from cryptozavr.application.backtest.evaluator.condition import evaluate_condition
from cryptozavr.application.backtest.evaluator.signals import SignalTick
from cryptozavr.application.strategy.strategy_spec import (
    IndicatorRef,
    StrategySpec,
)

def _fold_and(signals: list[bool | None]) -> bool | None:
    if any(s is None for s in signals):
        return None
    return all(s for s in signals if s is not None)

def _fold_or(signals: list[bool | None]) -> bool | None:
    if any(s is None for s in signals):
        return None
    return any(s for s in signals if s is not None)

class StrategyEvaluator:
    def __init__(
        self,
        spec: StrategySpec,
        series_map: dict[IndicatorRef, pd.Series],
    ) -> None:
        self._spec = spec
        self._series = series_map

    def tick(self, bar_index: int) -> SignalTick:
        entry_results = [
            evaluate_condition(c, self._series, bar_index)
            for c in self._spec.entry.conditions
        ]
        entry_signal = _fold_and(entry_results)
        if self._spec.exit.conditions:
            exit_results = [
                evaluate_condition(c, self._series, bar_index)
                for c in self._spec.exit.conditions
            ]
            exit_signal = _fold_or(exit_results)
        else:
            # TP/SL-only exit: explicit False lets simulator act on TP/SL
            # without misreading a None as "still warming".
            exit_signal = False
        return SignalTick(
            bar_index=bar_index,
            entry_signal=entry_signal,
            exit_signal=exit_signal,
        )
```

- [ ] **Step 4: Verify green**

Run: `uv run pytest tests/unit/application/backtest/evaluator/ -v`
Expected: ~18 passed.

- [ ] **Step 5: Commit**

`/tmp/commit-msg.txt`:
```text
feat(backtest): condition evaluator + StrategyEvaluator + SignalTick

evaluate_condition reads pre-computed Series at bar_index, handles all
6 ComparatorOps, returns None on NaN / missing-previous. StrategyEvaluator
AND-folds entry conditions, OR-folds exit conditions; zero-exit case
emits exit_signal=False once entry is warm so the trade simulator can
still act on TP/SL.
```

```bash
git add src/cryptozavr/application/backtest/evaluator/*.py \
        tests/unit/application/backtest/evaluator/*.py
git commit -F /tmp/commit-msg.txt
```

---

## Task 10: Slippage + Fee models + OpenPosition

**Files:**
- Create: `src/cryptozavr/application/backtest/simulator/slippage.py`
- Create: `src/cryptozavr/application/backtest/simulator/fees.py`
- Create: `src/cryptozavr/application/backtest/simulator/position.py`
- Create: `tests/unit/application/backtest/simulator/test_slippage.py`
- Create: `tests/unit/application/backtest/simulator/test_fees.py`
- Create: `tests/unit/application/backtest/simulator/test_position.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/application/backtest/simulator/test_slippage.py
from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.backtest.simulator.slippage import PctSlippageModel
from cryptozavr.application.strategy.enums import StrategySide

def test_long_entry_adds_slippage() -> None:
    m = PctSlippageModel(bps=10)  # 10 bps = 0.001
    fill = m.adjust(reference=Decimal("100"), side=StrategySide.LONG, is_entry=True)
    assert fill == Decimal("100.1")

def test_long_exit_subtracts_slippage() -> None:
    m = PctSlippageModel(bps=10)
    fill = m.adjust(reference=Decimal("100"), side=StrategySide.LONG, is_entry=False)
    assert fill == Decimal("99.9")

def test_short_entry_subtracts_slippage() -> None:
    m = PctSlippageModel(bps=10)
    fill = m.adjust(reference=Decimal("100"), side=StrategySide.SHORT, is_entry=True)
    assert fill == Decimal("99.9")

def test_short_exit_adds_slippage() -> None:
    m = PctSlippageModel(bps=10)
    fill = m.adjust(reference=Decimal("100"), side=StrategySide.SHORT, is_entry=False)
    assert fill == Decimal("100.1")

def test_zero_bps_is_noop() -> None:
    m = PctSlippageModel(bps=0)
    fill = m.adjust(reference=Decimal("100"), side=StrategySide.LONG, is_entry=True)
    assert fill == Decimal("100")

def test_negative_bps_raises() -> None:
    with pytest.raises(ValueError, match="bps must be >= 0"):
        PctSlippageModel(bps=-1)
```

```python
# tests/unit/application/backtest/simulator/test_fees.py
from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.backtest.simulator.fees import FixedBpsFeeModel

def test_five_bps_on_notional() -> None:
    m = FixedBpsFeeModel(bps=5)  # 0.0005
    assert m.compute(notional=Decimal("10000"), is_entry=True) == Decimal("5")

def test_zero_bps_is_zero_fee() -> None:
    assert FixedBpsFeeModel(bps=0).compute(notional=Decimal("10000"), is_entry=True) == Decimal("0")

def test_entry_and_exit_use_same_bps() -> None:
    m = FixedBpsFeeModel(bps=10)  # 0.001
    assert m.compute(notional=Decimal("1000"), is_entry=True) == Decimal("1")
    assert m.compute(notional=Decimal("1000"), is_entry=False) == Decimal("1")

def test_negative_bps_raises() -> None:
    with pytest.raises(ValueError, match="bps must be >= 0"):
        FixedBpsFeeModel(bps=-1)

def test_zero_notional_is_zero_fee() -> None:
    assert FixedBpsFeeModel(bps=5).compute(notional=Decimal("0"), is_entry=True) == Decimal("0")
```

```python
# tests/unit/application/backtest/simulator/test_position.py
from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.backtest.simulator.position import OpenPosition
from cryptozavr.application.strategy.enums import StrategySide

def test_open_position_construction() -> None:
    pos = OpenPosition(
        side=StrategySide.LONG,
        entry_price=Decimal("100"),
        size=Decimal("1.5"),
        entry_bar_index=5,
        take_profit_level=Decimal("105"),
        stop_loss_level=Decimal("98"),
    )
    assert pos.side is StrategySide.LONG
    assert pos.size == Decimal("1.5")

def test_open_position_is_frozen() -> None:
    pos = OpenPosition(
        side=StrategySide.LONG,
        entry_price=Decimal("100"),
        size=Decimal("1"),
        entry_bar_index=0,
        take_profit_level=None,
        stop_loss_level=None,
    )
    with pytest.raises((AttributeError, Exception)):
        pos.size = Decimal("2")  # type: ignore[misc]
```

- [ ] **Step 2: Verify red**

Run: `uv run pytest tests/unit/application/backtest/simulator/ -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement slippage / fees / position**

```python
# src/cryptozavr/application/backtest/simulator/slippage.py
"""Slippage model: price adjustment when entering/exiting a position.

LONG pays more to enter (fill >= reference), receives less to exit.
SHORT mirrors. Deterministic — same reference price always yields the
same fill.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from cryptozavr.application.strategy.enums import StrategySide

_BPS_PER_UNIT = Decimal("10000")

class SlippageModel(Protocol):
    def adjust(
        self,
        *,
        reference: Decimal,
        side: StrategySide,
        is_entry: bool,
    ) -> Decimal: ...

class PctSlippageModel:
    def __init__(self, *, bps: int = 10) -> None:
        if bps < 0:
            raise ValueError(f"bps must be >= 0 (got {bps!r})")
        self._rate = Decimal(bps) / _BPS_PER_UNIT

    def adjust(
        self,
        *,
        reference: Decimal,
        side: StrategySide,
        is_entry: bool,
    ) -> Decimal:
        # LONG entry: buy HIGHER; LONG exit: sell LOWER.
        # SHORT entry: sell LOWER; SHORT exit: buy HIGHER.
        is_buy = (side is StrategySide.LONG) == is_entry
        delta = reference * self._rate
        return reference + delta if is_buy else reference - delta
```

```python
# src/cryptozavr/application/backtest/simulator/fees.py
"""Fee model: per-fill charge, deducted from equity."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

_BPS_PER_UNIT = Decimal("10000")

class FeeModel(Protocol):
    def compute(self, *, notional: Decimal, is_entry: bool) -> Decimal: ...

class FixedBpsFeeModel:
    def __init__(self, *, bps: int = 5) -> None:
        if bps < 0:
            raise ValueError(f"bps must be >= 0 (got {bps!r})")
        self._rate = Decimal(bps) / _BPS_PER_UNIT

    def compute(self, *, notional: Decimal, is_entry: bool) -> Decimal:
        return notional * self._rate
```

```python
# src/cryptozavr/application/backtest/simulator/position.py
"""OpenPosition: immutable snapshot of an open trade."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from cryptozavr.application.strategy.enums import StrategySide

@dataclass(frozen=True, slots=True)
class OpenPosition:
    side: StrategySide
    entry_price: Decimal
    size: Decimal
    entry_bar_index: int
    take_profit_level: Decimal | None
    stop_loss_level: Decimal | None
```

- [ ] **Step 4: Verify green**

Run: `uv run pytest tests/unit/application/backtest/simulator/ -v`
Expected: ~13 passed.

- [ ] **Step 5: Commit**

`/tmp/commit-msg.txt`:
```bash
feat(backtest): SlippageModel + FeeModel Protocols + OpenPosition

PctSlippageModel(bps) adjusts fill price in the direction that costs
the taker (LONG entry up, LONG exit down). FixedBpsFeeModel charges
bps of notional on every fill. OpenPosition is a frozen dataclass
snapshot with precomputed absolute TP/SL levels.
```

```bash
git add src/cryptozavr/application/backtest/simulator/slippage.py \
        src/cryptozavr/application/backtest/simulator/fees.py \
        src/cryptozavr/application/backtest/simulator/position.py \
        tests/unit/application/backtest/simulator/test_slippage.py \
        tests/unit/application/backtest/simulator/test_fees.py \
        tests/unit/application/backtest/simulator/test_position.py
git commit -F /tmp/commit-msg.txt
```

---

## Task 11: TradeSimulator (streaming trade lifecycle)

**Files:**
- Create: `src/cryptozavr/application/backtest/simulator/trade_simulator.py`
- Create: `tests/unit/application/backtest/simulator/test_trade_simulator.py`

This is the biggest task. Decimal conversion from candle float columns
happens here at the boundary.

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/application/backtest/simulator/test_trade_simulator.py
"""TradeSimulator: per-bar position lifecycle with slippage + fees."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
import pytest

from cryptozavr.application.analytics.backtest_report import (
    BacktestTrade,
    PositionSide,
)
from cryptozavr.application.backtest.evaluator.signals import SignalTick
from cryptozavr.application.backtest.simulator.fees import FixedBpsFeeModel
from cryptozavr.application.backtest.simulator.slippage import PctSlippageModel
from cryptozavr.application.backtest.simulator.trade_simulator import TradeSimulator
from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
    StrategySide,
)
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    IndicatorRef,
    StrategyEntry,
    StrategyExit,
    StrategySpec,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import MarketType, VenueId

def _symbol() -> Symbol:
    return Symbol(
        venue=VenueId.KUCOIN,
        base="BTC",
        quote="USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )

def _spec(
    *,
    tp: Decimal | None = Decimal("0.05"),
    sl: Decimal | None = Decimal("0.02"),
    size_pct: Decimal = Decimal("0.5"),
    side: StrategySide = StrategySide.LONG,
) -> StrategySpec:
    ref = IndicatorRef(kind=IndicatorKind.SMA, period=1)
    return StrategySpec(
        name="t",
        description="d",
        venue=VenueId.KUCOIN,
        symbol=_symbol(),
        timeframe=Timeframe.H1,
        entry=StrategyEntry(
            side=side,
            conditions=(Condition(lhs=ref, op=ComparatorOp.GT, rhs=Decimal("0")),),
        ),
        exit=StrategyExit(
            conditions=(),
            take_profit_pct=tp,
            stop_loss_pct=sl,
        ),
        size_pct=size_pct,
    )

def _row(open_: str, high: str, low: str, close: str, volume: str = "1000") -> pd.Series:
    return pd.Series(
        {
            "open": float(open_),
            "high": float(high),
            "low": float(low),
            "close": float(close),
            "volume": float(volume),
        }
    )

def test_initial_state_no_position_no_trades() -> None:
    sim = TradeSimulator(
        _spec(),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    assert sim.open_position is None
    assert sim.trades == ()
    assert sim.equity == Decimal("10000")

def test_entry_signal_opens_long_position_frictionless() -> None:
    sim = TradeSimulator(
        _spec(size_pct=Decimal("0.5")),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    assert sim.open_position is not None
    assert sim.open_position.side is StrategySide.LONG
    # size = 0.5 * 10000 / 100 = 50
    assert sim.open_position.size == Decimal("50")
    # TP level = 100 * 1.05 = 105; SL level = 100 * 0.98 = 98
    assert sim.open_position.take_profit_level == Decimal("105.00")
    assert sim.open_position.stop_loss_level == Decimal("98.00")

def test_entry_signal_without_signal_stays_flat() -> None:
    sim = TradeSimulator(
        _spec(),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=None, exit_signal=False),
    )
    assert sim.open_position is None
    assert sim.equity_curve[0].equity == Decimal("10000")

def test_tp_hit_closes_long_at_tp_level() -> None:
    sim = TradeSimulator(
        _spec(tp=Decimal("0.05"), sl=None),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    # Bar 1: high = 106, above TP=105 → TP fires.
    sim.tick(
        _row("101", "106", "100", "103"),
        SignalTick(bar_index=1, entry_signal=False, exit_signal=False),
    )
    assert sim.open_position is None
    assert len(sim.trades) == 1
    # pnl = (105 - 100) * 50 = 250
    assert sim.trades[0].pnl == Decimal("250.00")
    assert sim.trades[0].exit_price == Decimal("105.00")

def test_sl_hit_closes_long_at_sl_level() -> None:
    sim = TradeSimulator(
        _spec(tp=None, sl=Decimal("0.02")),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    # Bar 1: low = 97, below SL=98 → SL fires.
    sim.tick(
        _row("100", "101", "97", "98"),
        SignalTick(bar_index=1, entry_signal=False, exit_signal=False),
    )
    assert len(sim.trades) == 1
    # pnl = (98 - 100) * 50 = -100
    assert sim.trades[0].pnl == Decimal("-100.00")
    assert sim.trades[0].exit_price == Decimal("98.00")

def test_tp_and_sl_both_inside_worst_case_long_sl_wins() -> None:
    sim = TradeSimulator(
        _spec(tp=Decimal("0.05"), sl=Decimal("0.02")),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    # Bar 1: low=97 (< SL=98), high=107 (> TP=105). Both inside.
    # Worst-case-first for LONG: SL wins.
    sim.tick(
        _row("100", "107", "97", "101"),
        SignalTick(bar_index=1, entry_signal=False, exit_signal=False),
    )
    assert sim.trades[0].exit_price == Decimal("98.00")

def test_exit_signal_closes_at_close_price() -> None:
    sim = TradeSimulator(
        _spec(tp=None, sl=None),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    # With tp=None, sl=None we need a condition-based exit. Modify spec in-line:
    ref = IndicatorRef(kind=IndicatorKind.SMA, period=1)
    spec = StrategySpec(
        name="t",
        description="d",
        venue=VenueId.KUCOIN,
        symbol=_symbol(),
        timeframe=Timeframe.H1,
        entry=StrategyEntry(
            side=StrategySide.LONG,
            conditions=(Condition(lhs=ref, op=ComparatorOp.GT, rhs=Decimal("0")),),
        ),
        exit=StrategyExit(
            conditions=(Condition(lhs=ref, op=ComparatorOp.LT, rhs=Decimal("0")),),
        ),
        size_pct=Decimal("0.5"),
    )
    sim = TradeSimulator(
        spec,
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    sim.tick(
        _row("100", "105", "99", "104"),
        SignalTick(bar_index=1, entry_signal=False, exit_signal=True),
    )
    assert len(sim.trades) == 1
    # Closed at close=104, entry=100, size=50 → pnl = 4 * 50 = 200
    assert sim.trades[0].exit_price == Decimal("104")
    assert sim.trades[0].pnl == Decimal("200")

def test_dust_trade_skipped_zero_size() -> None:
    sim = TradeSimulator(
        _spec(size_pct=Decimal("0.0000000001")),  # tiny
        initial_equity=Decimal("10"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    # At price 1e18 size rounds to 0 — skip
    sim.tick(
        _row("1000000000000000000", "1000000000000000000", "1000000000000000000", "1000000000000000000"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    assert sim.open_position is None

def test_min_notional_skips_small_trade() -> None:
    sim = TradeSimulator(
        _spec(size_pct=Decimal("0.001")),
        initial_equity=Decimal("100"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
        min_notional=Decimal("10"),
    )
    # size_pct * equity = 0.1 < min_notional = 10 → skip
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    assert sim.open_position is None

def test_fees_reduce_pnl() -> None:
    sim = TradeSimulator(
        _spec(tp=Decimal("0.05"), sl=None),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=10),  # 10 bps = 0.001 = 0.1%
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    sim.tick(
        _row("101", "106", "100", "103"),
        SignalTick(bar_index=1, entry_signal=False, exit_signal=False),
    )
    # Entry fee: size=50, entry_price=100, notional=5000, fee=5
    # Exit fee: exit_price=105, notional=5250, fee=5.25
    # Gross pnl = 250. Fees = 10.25. Net = 239.75.
    assert sim.trades[0].pnl == Decimal("239.75")

def test_short_position_pnl_sign() -> None:
    sim = TradeSimulator(
        _spec(side=StrategySide.SHORT, tp=Decimal("0.05"), sl=None),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    # Price falls → short profits. TP for short is 100 * 0.95 = 95.
    sim.tick(
        _row("98", "98", "94", "95"),
        SignalTick(bar_index=1, entry_signal=False, exit_signal=False),
    )
    # entry=100, exit=95, size=50 → pnl for SHORT = (100 - 95) * 50 = 250
    assert sim.trades[0].pnl == Decimal("250.00")

def test_equity_curve_length_matches_bars() -> None:
    sim = TradeSimulator(
        _spec(),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    for i in range(5):
        sim.tick(
            _row("100", "101", "99", "100"),
            SignalTick(bar_index=i, entry_signal=None, exit_signal=False),
        )
    assert len(sim.equity_curve) == 5

def test_position_still_open_closed_externally() -> None:
    """Simulator does not auto-close at series end — caller (engine) does."""
    sim = TradeSimulator(
        _spec(),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    assert sim.open_position is not None
    # caller uses close_open_position to flush at end
    sim.close_open_position(close_price=Decimal("103"), bar_index=0)
    assert sim.open_position is None
    assert len(sim.trades) == 1
    assert sim.trades[0].exit_price == Decimal("103")
```

- [ ] **Step 2: Verify red**

Run: `uv run pytest tests/unit/application/backtest/simulator/test_trade_simulator.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement TradeSimulator**

```python
# src/cryptozavr/application/backtest/simulator/trade_simulator.py
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
from decimal import Decimal

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

def _d(v: float) -> Decimal:
    """Float → Decimal via str() to avoid binary float artifacts."""
    return Decimal(str(v))

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
        fill = self.slippage.adjust(
            reference=close_price, side=side, is_entry=True
        )
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
        if size == 0:
            _LOG.warning(
                "simulator: dust entry (size=0) at bar %d for spec=%r; skipping",
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

    def _maybe_close_intrabar_or_on_signal(
        self, candle: pd.Series, signal: SignalTick
    ) -> None:
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
                self._close(reference=sl, bar_index=bar_index, at_level=sl)  # type: ignore[arg-type]
            else:
                self._close(reference=tp, bar_index=bar_index, at_level=tp)  # type: ignore[arg-type]
        elif sl_inside:
            self._close(reference=sl, bar_index=bar_index, at_level=sl)  # type: ignore[arg-type]
        elif tp_inside:
            self._close(reference=tp, bar_index=bar_index, at_level=tp)  # type: ignore[arg-type]
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
        assumption — the level was touched intrabar, no further slippage
        on top of the level). If `at_level` is None, apply slippage to
        the reference (typically the close price)."""
        assert self._position is not None
        pos = self._position
        if at_level is None:
            exit_price = self.slippage.adjust(
                reference=reference, side=pos.side, is_entry=False
            )
        else:
            exit_price = at_level
        notional = pos.size * exit_price
        exit_fee = self.fees.compute(notional=notional, is_entry=False)
        # Realize pnl. For LONG pnl = (exit - entry) * size; SHORT mirror.
        if pos.side is StrategySide.LONG:
            gross = (exit_price - pos.entry_price) * pos.size
        else:
            gross = (pos.entry_price - exit_price) * pos.size
        # Entry fee was already debited at open, so gross already reflects
        # post-entry-fee equity. We subtract exit fee to get realized pnl
        # on the trade (as reported to BacktestReport).
        pnl = gross - exit_fee
        self._equity += pnl  # entry_fee already deducted at open
        assert self._entry_opened_at_ms is not None
        side_enum = (
            PositionSide.LONG if pos.side is StrategySide.LONG else PositionSide.SHORT
        )
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

    def _mark_to_market(self, close_price: Decimal) -> Decimal:
        """Current equity if we marked the open position to `close_price`."""
        assert self._position is not None
        pos = self._position
        if pos.side is StrategySide.LONG:
            unrealized = (close_price - pos.entry_price) * pos.size
        else:
            unrealized = (pos.entry_price - close_price) * pos.size
        return self._equity + unrealized

def _instant_for_bar(bar_index: int) -> Instant:
    """Monotonic placeholder Instants; engine facade overrides with real
    timestamps from the candle DataFrame when it has them."""
    return Instant.from_ms(1_700_000_000_000 + bar_index * 60_000)
```

- [ ] **Step 4: Verify green**

Run: `uv run pytest tests/unit/application/backtest/simulator/test_trade_simulator.py -v`
Expected: 13 passed.

- [ ] **Step 5: Commit**

`/tmp/commit-msg.txt`:
```text
feat(backtest): TradeSimulator (per-bar lifecycle, intrabar TP/SL)

Single-position event-driven simulator. Entry on signal.entry==True,
close on: (1) SL+TP both inside → worst-case-first (SL/LONG, TP/SHORT),
(2) single side inside, (3) exit_signal==True (close price + slippage).
Dust + min_notional skips log WARNING. Mark-to-market equity per bar so
the curve is exactly len(candles) long.
```

```bash
git add src/cryptozavr/application/backtest/simulator/trade_simulator.py \
        tests/unit/application/backtest/simulator/test_trade_simulator.py
git commit -F /tmp/commit-msg.txt
```

---

## Task 12: BacktestEngine facade

**Files:**
- Create: `src/cryptozavr/application/backtest/engine.py`
- Create: `tests/unit/application/backtest/test_engine.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/application/backtest/test_engine.py
"""BacktestEngine.run: candles + spec -> BacktestReport."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
import pytest

from cryptozavr.application.analytics.backtest_report import BacktestReport
from cryptozavr.application.backtest.engine import BacktestEngine
from cryptozavr.application.backtest.simulator.fees import FixedBpsFeeModel
from cryptozavr.application.backtest.simulator.slippage import PctSlippageModel
from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
    StrategySide,
)
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    IndicatorRef,
    StrategyEntry,
    StrategyExit,
    StrategySpec,
)
from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from tests.unit.application.backtest.fixtures import candle_df

def _symbol() -> Symbol:
    return Symbol(
        venue=VenueId.KUCOIN,
        base="BTC",
        quote="USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )

def _tp_sl_spec() -> StrategySpec:
    ref = IndicatorRef(kind=IndicatorKind.SMA, period=1)
    return StrategySpec(
        name="always",
        description="d",
        venue=VenueId.KUCOIN,
        symbol=_symbol(),
        timeframe=Timeframe.H1,
        entry=StrategyEntry(
            side=StrategySide.LONG,
            conditions=(Condition(lhs=ref, op=ComparatorOp.GT, rhs=Decimal("0")),),
        ),
        exit=StrategyExit(
            conditions=(),
            take_profit_pct=Decimal("0.05"),
            stop_loss_pct=Decimal("0.02"),
        ),
        size_pct=Decimal("0.5"),
    )

def test_run_returns_backtest_report() -> None:
    engine = BacktestEngine()
    report = engine.run(
        _tp_sl_spec(),
        candle_df(["100", "101", "102", "103"]),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    assert isinstance(report, BacktestReport)
    assert report.strategy_name == "always"
    assert report.initial_equity == Decimal("10000")

def test_run_raises_on_empty_candles() -> None:
    engine = BacktestEngine()
    with pytest.raises(ValidationError, match="empty"):
        engine.run(
            _tp_sl_spec(),
            pd.DataFrame(columns=["open", "high", "low", "close", "volume"]),
            initial_equity=Decimal("10000"),
        )

def test_run_raises_on_missing_columns() -> None:
    engine = BacktestEngine()
    bad = pd.DataFrame({"open": [1.0], "close": [1.0]})
    with pytest.raises(ValidationError, match="columns"):
        engine.run(_tp_sl_spec(), bad, initial_equity=Decimal("10000"))

def test_run_closes_open_position_at_end() -> None:
    engine = BacktestEngine()
    # TP = 5%, SL = 2%. Upward-drifting series that never hits either →
    # position remains open till end → engine closes it.
    df = candle_df(["100", "100.5", "101", "101.5"])
    report = engine.run(
        _tp_sl_spec(),
        df,
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    assert len(report.trades) >= 1  # at least the final auto-close
    # Final equity must be the last equity curve point.
    assert report.final_equity == report.equity_curve[-1].equity

def test_equity_curve_length_matches_candles() -> None:
    engine = BacktestEngine()
    df = candle_df(["100"] * 20)
    report = engine.run(
        _tp_sl_spec(),
        df,
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    assert len(report.equity_curve) == 20
```

- [ ] **Step 2: Verify red**

Run: `uv run pytest tests/unit/application/backtest/test_engine.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement BacktestEngine**

```python
# src/cryptozavr/application/backtest/engine.py
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
            simulator._equity_curve = old_curve  # noqa: SLF001 — controlled mutation here
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
```

- [ ] **Step 4: Verify green**

Run: `uv run pytest tests/unit/application/backtest/test_engine.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

`/tmp/commit-msg.txt`:
```bash
feat(backtest): BacktestEngine facade (compute indicators + stream trades)

run(spec, candles, initial_equity, ...) validates the DataFrame,
computes every referenced indicator in one pass, iterates bars through
evaluator + simulator, auto-closes any still-open position at the
last close, and packs a BacktestReport consumable by the 2C visitors.
```

```bash
git add src/cryptozavr/application/backtest/engine.py \
        tests/unit/application/backtest/test_engine.py
git commit -F /tmp/commit-msg.txt
```

---

## Task 13: E2E tests against synthetic series + 2C visitors

**Files:**
- Create: `tests/unit/application/backtest/test_engine_e2e.py`

- [ ] **Step 1: Write E2E tests**

```python
# tests/unit/application/backtest/test_engine_e2e.py
"""End-to-end: realistic specs against synthetic series, 2C visitors
consume the produced BacktestReport."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st

from cryptozavr.application.analytics.analytics_service import (
    BacktestAnalyticsService,
)
from cryptozavr.application.analytics.visitors.max_drawdown import MaxDrawdownVisitor
from cryptozavr.application.analytics.visitors.profit_factor import ProfitFactorVisitor
from cryptozavr.application.analytics.visitors.sharpe import SharpeRatioVisitor
from cryptozavr.application.analytics.visitors.total_return import TotalReturnVisitor
from cryptozavr.application.analytics.visitors.win_rate import WinRateVisitor
from cryptozavr.application.backtest.engine import BacktestEngine
from cryptozavr.application.backtest.simulator.fees import FixedBpsFeeModel
from cryptozavr.application.backtest.simulator.slippage import PctSlippageModel
from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
    StrategySide,
)
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    IndicatorRef,
    StrategyEntry,
    StrategyExit,
    StrategySpec,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from tests.unit.application.backtest.fixtures import candle_df

def _symbol() -> Symbol:
    return Symbol(
        venue=VenueId.KUCOIN,
        base="BTC",
        quote="USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )

def _ema_crossover_spec() -> StrategySpec:
    fast = IndicatorRef(kind=IndicatorKind.EMA, period=3)
    slow = IndicatorRef(kind=IndicatorKind.EMA, period=8)
    return StrategySpec(
        name="crossover",
        description="EMA crossover",
        venue=VenueId.KUCOIN,
        symbol=_symbol(),
        timeframe=Timeframe.H1,
        entry=StrategyEntry(
            side=StrategySide.LONG,
            conditions=(
                Condition(lhs=fast, op=ComparatorOp.CROSSES_ABOVE, rhs=slow),
            ),
        ),
        exit=StrategyExit(
            conditions=(
                Condition(lhs=fast, op=ComparatorOp.CROSSES_BELOW, rhs=slow),
            ),
            take_profit_pct=Decimal("0.05"),
            stop_loss_pct=Decimal("0.02"),
        ),
        size_pct=Decimal("0.25"),
    )

def test_crossover_on_trending_series_makes_trades_and_visitors_run() -> None:
    engine = BacktestEngine()
    # Strong uptrend then pullback then uptrend — crossover should fire.
    closes = [str(100 + i) for i in range(5)]  # ramp
    closes += [str(105 - i) for i in range(1, 6)]  # pullback
    closes += [str(100 + i * 2) for i in range(1, 15)]  # ramp up more
    report = engine.run(
        _ema_crossover_spec(),
        candle_df(closes),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    assert len(report.trades) >= 1  # at least one trade
    # 2C visitors work against the produced report
    service = BacktestAnalyticsService(
        [
            TotalReturnVisitor(),
            WinRateVisitor(),
            MaxDrawdownVisitor(),
            ProfitFactorVisitor(),
            SharpeRatioVisitor(),
        ]
    )
    results = service.run_all(report)
    assert "total_return" in results
    assert "win_rate" in results
    assert "max_drawdown" in results
    assert "profit_factor" in results
    assert "sharpe_ratio" in results

def test_report_equity_curve_matches_candles_length() -> None:
    engine = BacktestEngine()
    closes = [str(100 + i) for i in range(30)]
    report = engine.run(
        _ema_crossover_spec(),
        candle_df(closes),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    assert len(report.equity_curve) == 30
    assert report.equity_curve[0].equity == Decimal("10000")

def test_flat_series_no_trades_zero_return() -> None:
    engine = BacktestEngine()
    report = engine.run(
        _ema_crossover_spec(),
        candle_df(["100"] * 20),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    assert report.trades == ()
    assert report.final_equity == Decimal("10000")

def test_single_candle_no_trades() -> None:
    engine = BacktestEngine()
    report = engine.run(
        _ema_crossover_spec(),
        candle_df(["100"]),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    assert report.trades == ()
    assert len(report.equity_curve) == 1

@given(
    closes=st.lists(
        st.floats(min_value=50.0, max_value=200.0, allow_nan=False, allow_infinity=False),
        min_size=5,
        max_size=40,
    )
)
@settings(max_examples=25, deadline=None)
def test_property_bounded_series_never_raises(closes: list[float]) -> None:
    """Random bounded series + a standard spec → engine returns a valid
    BacktestReport and 2C visitors never raise."""
    engine = BacktestEngine()
    report = engine.run(
        _ema_crossover_spec(),
        candle_df([str(round(c, 4)) for c in closes]),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=5),
        fees=FixedBpsFeeModel(bps=2),
    )
    service = BacktestAnalyticsService(
        [
            TotalReturnVisitor(),
            WinRateVisitor(),
            MaxDrawdownVisitor(),
            ProfitFactorVisitor(),
            SharpeRatioVisitor(),
        ]
    )
    results = service.run_all(report)
    for name, value in results.items():
        assert value is None or value.is_finite(), f"{name} returned non-finite {value!r}"
```

- [ ] **Step 2: Verify green**

Run: `uv run pytest tests/unit/application/backtest/test_engine_e2e.py -v`
Expected: 5 passed (including hypothesis property test).

- [ ] **Step 3: Full sweep**

Run:
```bash
uv run pytest tests/unit tests/contract -m "not integration" -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Expected: all green. Tests ≈ 645.

- [ ] **Step 4: Commit E2E + CHANGELOG**

Update `CHANGELOG.md` — add entry under `[Unreleased]` ABOVE the existing
Phase 2A entry:

```markdown
### Added — Phase 2 Sub-project A — BacktestEngine

- `cryptozavr.application.backtest` package — hybrid backtesting engine
  (vectorized indicators + streaming trade simulator).
- 6 indicators (SMA/EMA/RSI/MACD/ATR/Volume) computed vectorized over a
  candle DataFrame in one pass; `IndicatorFactory` interns same
  `IndicatorRef` across entry + exit so a shared reference computes once.
- `StrategyEvaluator` reads pre-computed Series per bar with
  None-propagation on NaN (warm-up). Exit with zero conditions +
  TP/SL-only emits `exit_signal=False` once warm.
- `TradeSimulator`: single-position lifecycle, intrabar TP/SL collision
  resolves worst-case-first (SL wins for LONG, TP wins for SHORT),
  dust + `min_notional` skip with WARNING log, mark-to-market equity
  per bar.
- `PctSlippageModel` / `FixedBpsFeeModel` with Protocols so future
  `MarketDrivenFeeModel` (CCXT-backed) drops in without changing
  `TradeSimulator`.
- `BacktestEngine.run(spec, candles, initial_equity, slippage, fees,
  min_notional)` facade — validates DataFrame, wires everything, closes
  any open position at the last bar, returns `BacktestReport` consumed
  by the 2C `BacktestAnalyticsService` smoke-tested end-to-end.
- New dep: `pandas>=2.2`.
- ≈90 new unit + E2E tests (sweep 555 → 645).

```

`/tmp/commit-msg.txt`:
```bash
feat(backtest): E2E tests + CHANGELOG for sub-project A

End-to-end tests: EMA-crossover spec on a trending synthetic series
produces at least one trade and every 2C visitor accepts the report.
Property test (hypothesis): random bounded series + standard spec
always produces a valid report with finite visitor results.
```

```bash
git add tests/unit/application/backtest/test_engine_e2e.py CHANGELOG.md
git commit -F /tmp/commit-msg.txt
```

---

## Task 14: Create PR + merge

**Files:** none (git + gh)

- [ ] **Step 1: Push branch**

```bash
git push -u origin feat/phase-2-subproject-a-backtest-engine
```

- [ ] **Step 2: Create PR**

`/tmp/pr-body.md`:
```markdown
## Summary

Phase 2 sub-project A — hybrid BacktestEngine.

- Vectorized indicators (6): SMA / EMA / RSI / MACD / ATR / Volume with
  hand-computed ground truth + property tests.
- Streaming evaluator + simulator: 6 ComparatorOps, AND/OR fold,
  single-position TP/SL lifecycle, dust + min_notional skips.
- `BacktestEngine.run(...)` produces a `BacktestReport` that the 2C
  `BacktestAnalyticsService` runs through all 5 visitors end-to-end.

**Tests:** ≈90 new (555 → 645), all green. Ruff + format + mypy clean.

**New dep:** `pandas>=2.2`.

**Design:** docs/superpowers/specs/2026-04-22-phase-2-subproject-a-backtest-engine-design.md
**Plan:** docs/superpowers/plans/2026-04-22-phase-2-subproject-a-backtest-engine.md

## Test plan

- [x] Every indicator: warm-up + hand-computed reference + edge cases.
- [x] Evaluator: all 6 comparator ops + AND/OR fold + None-propagation.
- [x] Simulator: entry, exit-signal, TP hit, SL hit, both-inside-worst-case, dust, min_notional, fees-reduce-pnl, LONG/SHORT pnl sign, multi-trade, open-at-end.
- [x] Engine E2E: crossover on trending series → 2C visitors happy; flat series → no trades; single candle; property test on bounded series never raises.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

```bash
gh pr create --title "Phase 2 Sub-project A: BacktestEngine (hybrid)" \
             --body-file /tmp/pr-body.md --base main
```

- [ ] **Step 3: Request user review before merge**

Do NOT merge autonomously. Report the PR URL and ask the user to review
and approve merge. Per contract IRON RULE "Merge в main без явной
команды пользователя — ЗАПРЕЩЕНО".

- [ ] **Step 4: After user approval — merge**

```bash
gh pr merge <N> --squash --delete-branch
git checkout main && git pull --ff-only
```

---

## Self-Review (plan vs. spec)

1. **Spec coverage:**
   - Goal: every module in spec file tree has a corresponding task (Tasks 2-12).
   - Non-goals: explicitly echoed in spec — not duplicated here. ✓
   - Indicator Protocol + 6 indicators: Tasks 2, 3, 4, 5, 6, 7, 8. ✓
   - Evaluator: Task 9. ✓
   - Simulator (slippage/fees/position/trade_simulator): Tasks 10, 11. ✓
   - Engine facade: Task 12. ✓
   - Edge cases table (9 items): covered in Task 11 + Task 12 + Task 13 E2E. ✓
   - Testing breakdown (~80 unit + ~10 E2E): Tasks 2-12 add ≈75 unit; Task 13 adds E2E + property. Total ≥85. ✓
   - `min_notional` (added in spec v2): Task 10 constructor arg propagated through Task 11 → Task 12 run signature. ✓
   - Future extensions: spec-only, no task (correctly — deferred). ✓
   - pandas dep: Task 1. ✓
   - CHANGELOG: Task 13 Step 4. ✓

2. **Placeholder scan:**
   - No "TBD" / "TODO" / "implement later" / "similar to task N".
   - Every code step has real code.
   - Every run command has an expected output.
   - Commit messages written out in full.

3. **Type consistency:**
   - `Indicator.compute(df) → pd.Series` used uniformly Tasks 2-8.
   - `evaluate_condition(cond, series_map, bar_index) → bool | None` signature identical in Task 9 impl + Task 11 consumer.
   - `SlippageModel.adjust(*, reference, side, is_entry)` matches across
     slippage.py (Task 10), trade_simulator.py open/close (Task 11),
     engine.py run signature (Task 12).
   - `FeeModel.compute(*, notional, is_entry)` matches.
   - `OpenPosition` field names (`entry_price`, `size`, `take_profit_level`, `stop_loss_level`) identical across definition and reads.
   - `TradeSimulator.tick(candle: pd.Series, signal: SignalTick)` signature same in Task 11 tests and Task 12 engine.
   - `BacktestReport` construction pulls `strategy_name`, `period`, `initial_equity`, `final_equity`, `trades`, `equity_curve` — all fields present in 2C DTO.
   - `PositionSide.LONG/SHORT` (from 2C) mapped from `StrategySide.LONG/SHORT` (from 2A) in `_close` — consistent with 2C `PositionSide` vs 2A `StrategySide` split.

All checks pass. Plan is internally consistent and implements the spec.
