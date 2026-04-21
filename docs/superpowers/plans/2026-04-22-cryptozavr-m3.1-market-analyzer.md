# cryptozavr — Milestone 3.1: MarketAnalyzer + Strategy pattern

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Ввести analytical layer. Три pure-function `AnalysisStrategy` реализации (VWAP, Support/Resistance, VolatilityRegime) + `MarketAnalyzer` context (Strategy pattern per spec §5). Без MCP tools — фундамент для M3.3 где эти стратегии станут tools.

**Architecture:** Domain-only layer поверх уже существующего `OHLCVSeries`. Pure functions над candle tuple. `MarketAnalyzer` хранит `dict[str, AnalysisStrategy]`, диспатчит по имени. Легко добавлять новые стратегии (Ichimoku в phase 2) без изменений в context.

**Tech Stack:** Python 3.12, numpy-free (ручной ATR / realized vol на Decimal для точности). No new deps.

**Starting tag:** `v0.1.0`. Target: `v0.1.1`.

---

## File Structure

| Path | Responsibility |
|------|---------------|
| `src/cryptozavr/application/strategies/__init__.py` | NEW — package marker |
| `src/cryptozavr/application/strategies/base.py` | NEW — `AnalysisStrategy` Protocol + `AnalysisResult` dataclass |
| `src/cryptozavr/application/strategies/vwap.py` | NEW — `VwapStrategy` |
| `src/cryptozavr/application/strategies/support_resistance.py` | NEW — `SupportResistanceStrategy` |
| `src/cryptozavr/application/strategies/volatility.py` | NEW — `VolatilityRegimeStrategy` |
| `src/cryptozavr/application/services/market_analyzer.py` | NEW — `MarketAnalyzer` (Strategy context) |
| `tests/unit/application/strategies/__init__.py` | NEW — empty |
| `tests/unit/application/strategies/test_base.py` | NEW — AnalysisResult tests |
| `tests/unit/application/strategies/test_vwap.py` | NEW — 4 tests |
| `tests/unit/application/strategies/test_support_resistance.py` | NEW — 4 tests |
| `tests/unit/application/strategies/test_volatility.py` | NEW — 4 tests |
| `tests/unit/application/services/test_market_analyzer.py` | NEW — 3 tests |

---

## Tasks

### Task 1: `AnalysisStrategy` Protocol + `AnalysisResult` dataclass

**Files:**
- Create: `src/cryptozavr/application/strategies/__init__.py`
- Create: `src/cryptozavr/application/strategies/base.py`
- Create: `tests/unit/application/strategies/__init__.py` (empty)
- Create: `tests/unit/application/strategies/test_base.py`

- [ ] **Step 1: Write failing tests**

Write empty `tests/unit/application/strategies/__init__.py`.

Write `tests/unit/application/strategies/test_base.py`:
```python
"""Test AnalysisResult dataclass + AnalysisStrategy Protocol compliance."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.strategies.base import (
    AnalysisResult,
    AnalysisStrategy,
)
from cryptozavr.domain.market_data import OHLCVSeries
from cryptozavr.domain.quality import Confidence

class TestAnalysisResult:
    def test_result_carries_strategy_name_findings_confidence(self) -> None:
        result = AnalysisResult(
            strategy="test",
            findings={"foo": Decimal("1")},
            confidence=Confidence.HIGH,
        )
        assert result.strategy == "test"
        assert result.findings == {"foo": Decimal("1")}
        assert result.confidence is Confidence.HIGH

    def test_result_is_frozen(self) -> None:
        result = AnalysisResult(
            strategy="test", findings={}, confidence=Confidence.LOW,
        )
        with pytest.raises((AttributeError, Exception)):
            result.strategy = "other"  # type: ignore[misc]

class TestAnalysisStrategyProtocol:
    def test_protocol_has_name_attribute_and_analyze_method(self) -> None:
        class _Impl:
            name = "dummy"

            def analyze(self, series: OHLCVSeries) -> AnalysisResult:
                return AnalysisResult(
                    strategy=self.name, findings={},
                    confidence=Confidence.LOW,
                )

        impl: AnalysisStrategy = _Impl()
        assert impl.name == "dummy"
```

- [ ] **Step 2: FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/application/strategies/test_base.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement**

Write `src/cryptozavr/application/strategies/__init__.py`:
```python
"""Analytical strategies (Strategy pattern). Pure functions over OHLCV."""
```

Write `src/cryptozavr/application/strategies/base.py`:
```python
"""AnalysisStrategy Protocol + AnalysisResult envelope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from cryptozavr.domain.market_data import OHLCVSeries
from cryptozavr.domain.quality import Confidence

@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Envelope returned by every AnalysisStrategy.

    `findings` is a strategy-specific dict. Downstream DTOs serialise
    it via `json.dumps(findings, default=str)` — Decimals round-trip as
    strings.
    """

    strategy: str
    findings: dict[str, Any]
    confidence: Confidence

@runtime_checkable
class AnalysisStrategy(Protocol):
    """Strategy Protocol: stateless analyser over an OHLCV series."""

    name: str

    def analyze(self, series: OHLCVSeries) -> AnalysisResult: ...
```

- [ ] **Step 4: PASS (3 tests).**

```bash
uv run pytest tests/unit/application/strategies/test_base.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```text
feat(app): add AnalysisStrategy Protocol + AnalysisResult

Strategy pattern base per MVP spec §5. Protocol is runtime_checkable
so duck-typed impls satisfy isinstance. AnalysisResult is a frozen
slots dataclass carrying strategy name, typed-dict findings, and a
Confidence flag from the quality layer.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/application/strategies/__init__.py \
    src/cryptozavr/application/strategies/base.py \
    tests/unit/application/strategies/__init__.py \
    tests/unit/application/strategies/test_base.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 2: `VwapStrategy`

**Files:**
- Create: `src/cryptozavr/application/strategies/vwap.py`
- Create: `tests/unit/application/strategies/test_vwap.py`

VWAP (Volume-Weighted Average Price) = Σ(typical_price × volume) / Σ(volume). Typical price = (high + low + close) / 3.

- [ ] **Step 1: Write failing tests**

Write `tests/unit/application/strategies/test_vwap.py`:
```python
"""Test VwapStrategy: volume-weighted average price."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.strategies.vwap import VwapStrategy
from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, TimeRange, Timeframe
from cryptozavr.domain.venues import MarketType, VenueId

def _make_series(candles: tuple[OHLCVCandle, ...]) -> OHLCVSeries:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    quality = DataQuality(
        source=Provenance(venue_id="kucoin", endpoint="fetch_ohlcv"),
        fetched_at=Instant.from_ms(1_700_000_000_000),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )
    if candles:
        tr = TimeRange(
            start=candles[0].opened_at,
            end=Instant.from_ms(candles[-1].opened_at.to_ms() + 60_000),
        )
    else:
        tr = TimeRange(
            start=Instant.from_ms(0),
            end=Instant.from_ms(60_000),
        )
    return OHLCVSeries(
        symbol=symbol,
        timeframe=Timeframe.M1,
        candles=candles,
        range=tr,
        quality=quality,
    )

def _candle(t: int, o: str, h: str, low: str, c: str, v: str) -> OHLCVCandle:
    return OHLCVCandle(
        opened_at=Instant.from_ms(t),
        open=Decimal(o), high=Decimal(h), low=Decimal(low),
        close=Decimal(c), volume=Decimal(v),
    )

class TestVwapStrategy:
    def test_name_is_vwap(self) -> None:
        assert VwapStrategy().name == "vwap"

    def test_single_candle_vwap_equals_typical_price(self) -> None:
        series = _make_series((
            _candle(0, "100", "110", "90", "105", "10"),
        ))
        result = VwapStrategy().analyze(series)
        typical = (Decimal("110") + Decimal("90") + Decimal("105")) / Decimal(3)
        assert result.findings["vwap"] == typical
        assert result.findings["total_volume"] == Decimal("10")
        assert result.findings["bars_used"] == 1

    def test_weighted_by_volume(self) -> None:
        # candle1 typical=100, vol=1 → contributes 100
        # candle2 typical=200, vol=9 → contributes 1800
        # total volume=10, weighted sum=1900, vwap=190
        series = _make_series((
            _candle(0, "100", "100", "100", "100", "1"),
            _candle(60_000, "200", "200", "200", "200", "9"),
        ))
        result = VwapStrategy().analyze(series)
        assert result.findings["vwap"] == Decimal("190")
        assert result.findings["total_volume"] == Decimal("10")
        assert result.findings["bars_used"] == 2

    def test_empty_series_yields_low_confidence_and_none_vwap(self) -> None:
        series = _make_series(())
        result = VwapStrategy().analyze(series)
        assert result.findings["vwap"] is None
        assert result.findings["total_volume"] == Decimal("0")
        assert result.findings["bars_used"] == 0
        assert result.confidence is Confidence.LOW

    def test_zero_volume_candles_skipped_but_bars_counted(self) -> None:
        # zero-volume candle doesn't contribute to VWAP math but is counted
        series = _make_series((
            _candle(0, "100", "100", "100", "100", "0"),
            _candle(60_000, "200", "200", "200", "200", "10"),
        ))
        result = VwapStrategy().analyze(series)
        assert result.findings["vwap"] == Decimal("200")
        assert result.findings["total_volume"] == Decimal("10")
        assert result.findings["bars_used"] == 2
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write `src/cryptozavr/application/strategies/vwap.py`:
```python
"""Volume-Weighted Average Price strategy."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.strategies.base import AnalysisResult
from cryptozavr.domain.market_data import OHLCVSeries
from cryptozavr.domain.quality import Confidence

_THREE = Decimal(3)

class VwapStrategy:
    """Computes VWAP = Σ(typical_price × volume) / Σ(volume).

    Typical price = (high + low + close) / 3. Zero-volume candles are
    counted in `bars_used` but skipped in the weighted sum. Empty series
    yields `vwap=None` + LOW confidence.
    """

    name = "vwap"

    def analyze(self, series: OHLCVSeries) -> AnalysisResult:
        bars_used = len(series.candles)
        total_volume = Decimal(0)
        weighted = Decimal(0)
        for candle in series.candles:
            if candle.volume <= 0:
                continue
            typical = (candle.high + candle.low + candle.close) / _THREE
            weighted += typical * candle.volume
            total_volume += candle.volume

        if total_volume == 0 or bars_used == 0:
            return AnalysisResult(
                strategy=self.name,
                findings={
                    "vwap": None,
                    "total_volume": total_volume,
                    "bars_used": bars_used,
                },
                confidence=Confidence.LOW,
            )

        vwap = weighted / total_volume
        confidence = Confidence.HIGH if bars_used >= 10 else Confidence.MEDIUM
        return AnalysisResult(
            strategy=self.name,
            findings={
                "vwap": vwap,
                "total_volume": total_volume,
                "bars_used": bars_used,
            },
            confidence=confidence,
        )
```

- [ ] **Step 4: PASS (5 tests).**

```bash
uv run pytest tests/unit/application/strategies/test_vwap.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(app): add VwapStrategy

Volume-Weighted Average Price over OHLCVSeries. Uses typical price
(h+l+c)/3 weighted by volume. Zero-volume candles are counted in
bars_used but skipped in the weighted sum. Empty or all-zero series
yields vwap=None + Confidence.LOW. ≥10 bars → HIGH confidence.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/application/strategies/vwap.py \
    tests/unit/application/strategies/test_vwap.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 3: `SupportResistanceStrategy`

**Files:**
- Create: `src/cryptozavr/application/strategies/support_resistance.py`
- Create: `tests/unit/application/strategies/test_support_resistance.py`

Алгоритм (MVP): swing-based. Найти pivot highs (high[i] > high[i±k]) и pivot lows (low[i] < low[i±k]) при k=2. Кластеризовать близкие уровни (разница < 0.5% от средней цены). Вернуть top-N уровней.

- [ ] **Step 1: Write failing tests**

Write `tests/unit/application/strategies/test_support_resistance.py`:
```python
"""Test SupportResistanceStrategy: swing-pivot SR detection."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.strategies.support_resistance import (
    SupportResistanceStrategy,
)
from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, TimeRange, Timeframe
from cryptozavr.domain.venues import MarketType, VenueId

def _make_series(candles: tuple[OHLCVCandle, ...]) -> OHLCVSeries:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    quality = DataQuality(
        source=Provenance(venue_id="kucoin", endpoint="fetch_ohlcv"),
        fetched_at=Instant.from_ms(1_700_000_000_000),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )
    if candles:
        tr = TimeRange(
            start=candles[0].opened_at,
            end=Instant.from_ms(candles[-1].opened_at.to_ms() + 60_000),
        )
    else:
        tr = TimeRange(
            start=Instant.from_ms(0),
            end=Instant.from_ms(60_000),
        )
    return OHLCVSeries(
        symbol=symbol,
        timeframe=Timeframe.M1,
        candles=candles,
        range=tr,
        quality=quality,
    )

def _c(t: int, h: str, low: str) -> OHLCVCandle:
    mid = (Decimal(h) + Decimal(low)) / Decimal(2)
    return OHLCVCandle(
        opened_at=Instant.from_ms(t),
        open=mid, high=Decimal(h), low=Decimal(low),
        close=mid, volume=Decimal("1"),
    )

class TestSupportResistanceStrategy:
    def test_name_is_support_resistance(self) -> None:
        assert SupportResistanceStrategy().name == "support_resistance"

    def test_detects_obvious_pivot_high_and_low(self) -> None:
        # valley at i=2 (low 90), peak at i=5 (high 120)
        series = _make_series((
            _c(0, "110", "100"),
            _c(60_000, "105", "95"),
            _c(120_000, "100", "90"),    # pivot low
            _c(180_000, "108", "98"),
            _c(240_000, "115", "105"),
            _c(300_000, "120", "110"),   # pivot high
            _c(360_000, "118", "108"),
            _c(420_000, "112", "102"),
        ))
        result = SupportResistanceStrategy(window=2).analyze(series)
        assert Decimal("90") in result.findings["supports"]
        assert Decimal("120") in result.findings["resistances"]

    def test_clusters_nearby_levels(self) -> None:
        # two pivot highs within 0.5% — collapse to one level
        series = _make_series((
            _c(0, "100", "95"),
            _c(60_000, "105", "100"),
            _c(120_000, "120", "110"),     # pivot high ~120
            _c(180_000, "118", "108"),
            _c(240_000, "120.3", "110"),   # within 0.5% of 120
            _c(300_000, "115", "105"),
            _c(360_000, "110", "100"),
        ))
        result = SupportResistanceStrategy(
            window=2, cluster_pct=Decimal("0.5"),
        ).analyze(series)
        # Only one ≈120 level, not two
        resistances = result.findings["resistances"]
        near_120 = [r for r in resistances if Decimal("119") <= r <= Decimal("121")]
        assert len(near_120) == 1

    def test_too_few_bars_for_window_yields_low_confidence(self) -> None:
        # window=2 needs 2*2+1=5 bars minimum
        series = _make_series((
            _c(0, "110", "100"),
            _c(60_000, "105", "95"),
            _c(120_000, "100", "90"),
        ))
        result = SupportResistanceStrategy(window=2).analyze(series)
        assert result.confidence is Confidence.LOW
        assert result.findings["supports"] == ()
        assert result.findings["resistances"] == ()
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write `src/cryptozavr/application/strategies/support_resistance.py`:
```python
"""Swing-based Support/Resistance detector."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.strategies.base import AnalysisResult
from cryptozavr.domain.market_data import OHLCVSeries
from cryptozavr.domain.quality import Confidence

class SupportResistanceStrategy:
    """Finds pivot highs/lows (swing bars) and clusters them.

    Pivot high at index i: `high[i] > high[j]` for all j in [i-window, i+window] \\ {i}.
    Pivot low at index i: `low[i] < low[j]` for all j in [i-window, i+window] \\ {i}.

    Levels within `cluster_pct` percent of each other are merged
    (their mean becomes the final level).
    """

    name = "support_resistance"

    def __init__(
        self,
        window: int = 2,
        cluster_pct: Decimal = Decimal("0.5"),
    ) -> None:
        self._window = window
        self._cluster_pct = cluster_pct

    def analyze(self, series: OHLCVSeries) -> AnalysisResult:
        min_bars = 2 * self._window + 1
        if len(series.candles) < min_bars:
            return AnalysisResult(
                strategy=self.name,
                findings={
                    "supports": (),
                    "resistances": (),
                    "bars_used": len(series.candles),
                    "window": self._window,
                },
                confidence=Confidence.LOW,
            )

        raw_supports: list[Decimal] = []
        raw_resistances: list[Decimal] = []
        for i in range(self._window, len(series.candles) - self._window):
            center = series.candles[i]
            window_slice = (
                series.candles[i - self._window : i]
                + series.candles[i + 1 : i + self._window + 1]
            )
            if all(center.high > other.high for other in window_slice):
                raw_resistances.append(center.high)
            if all(center.low < other.low for other in window_slice):
                raw_supports.append(center.low)

        supports = tuple(self._cluster(sorted(raw_supports)))
        resistances = tuple(
            self._cluster(sorted(raw_resistances, reverse=True))
        )

        confidence = (
            Confidence.HIGH
            if supports and resistances and len(series.candles) >= 20
            else Confidence.MEDIUM
            if supports or resistances
            else Confidence.LOW
        )
        return AnalysisResult(
            strategy=self.name,
            findings={
                "supports": supports,
                "resistances": resistances,
                "bars_used": len(series.candles),
                "window": self._window,
            },
            confidence=confidence,
        )

    def _cluster(self, levels: list[Decimal]) -> list[Decimal]:
        """Merge levels within `cluster_pct` percent — return their means."""
        if not levels:
            return []
        pct = self._cluster_pct / Decimal(100)
        clusters: list[list[Decimal]] = [[levels[0]]]
        for level in levels[1:]:
            anchor = clusters[-1][0]
            if anchor == 0:
                clusters.append([level])
                continue
            diff = abs(level - anchor) / anchor
            if diff <= pct:
                clusters[-1].append(level)
            else:
                clusters.append([level])
        return [
            sum(group, Decimal(0)) / Decimal(len(group))
            for group in clusters
        ]
```

- [ ] **Step 4: PASS (4 tests).**

```bash
uv run pytest tests/unit/application/strategies/test_support_resistance.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(app): add SupportResistanceStrategy

Swing-pivot SR detector: high[i] > neighbours within window = pivot
high; mirror for pivot low. Window default=2 (needs ≥5 bars total).
Clusters levels within cluster_pct (default 0.5%) → mean of group.
Confidence HIGH when both sides present + ≥20 bars; MEDIUM if only
one side; LOW if too few bars.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/application/strategies/support_resistance.py \
    tests/unit/application/strategies/test_support_resistance.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 4: `VolatilityRegimeStrategy`

**Files:**
- Create: `src/cryptozavr/application/strategies/volatility.py`
- Create: `tests/unit/application/strategies/test_volatility.py`

ATR (Average True Range, Wilder): `TR = max(high - low, abs(high - prev_close), abs(low - prev_close))`. ATR = SMA(TR, window). Regime thresholds (ATR as % of close): calm <1, normal 1-3, high 3-6, extreme >6.

- [ ] **Step 1: Write failing tests**

Write `tests/unit/application/strategies/test_volatility.py`:
```python
"""Test VolatilityRegimeStrategy: ATR + regime classification."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.strategies.volatility import (
    VolatilityRegimeStrategy,
)
from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, TimeRange, Timeframe
from cryptozavr.domain.venues import MarketType, VenueId

def _make_series(candles: tuple[OHLCVCandle, ...]) -> OHLCVSeries:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    quality = DataQuality(
        source=Provenance(venue_id="kucoin", endpoint="fetch_ohlcv"),
        fetched_at=Instant.from_ms(1_700_000_000_000),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )
    if candles:
        tr = TimeRange(
            start=candles[0].opened_at,
            end=Instant.from_ms(candles[-1].opened_at.to_ms() + 60_000),
        )
    else:
        tr = TimeRange(
            start=Instant.from_ms(0), end=Instant.from_ms(60_000),
        )
    return OHLCVSeries(
        symbol=symbol,
        timeframe=Timeframe.M1,
        candles=candles,
        range=tr,
        quality=quality,
    )

def _c(t: int, o: str, h: str, low: str, c: str) -> OHLCVCandle:
    return OHLCVCandle(
        opened_at=Instant.from_ms(t),
        open=Decimal(o), high=Decimal(h),
        low=Decimal(low), close=Decimal(c),
        volume=Decimal("1"),
    )

class TestVolatilityRegimeStrategy:
    def test_name_is_volatility_regime(self) -> None:
        assert VolatilityRegimeStrategy().name == "volatility_regime"

    def test_tight_candles_classify_as_calm(self) -> None:
        # high-low = 0.5 on close=100 → TR%=0.5 — calm (<1)
        candles = tuple(
            _c(i * 60_000, "100", "100.25", "99.75", "100")
            for i in range(15)
        )
        result = VolatilityRegimeStrategy(window=14).analyze(_make_series(candles))
        assert result.findings["regime"] == "calm"
        assert result.findings["atr"] is not None
        assert result.findings["atr_pct"] < Decimal("1")

    def test_wide_candles_classify_as_high_or_extreme(self) -> None:
        # high-low = 5 on close=100 → TR%=5 — high (3-6)
        candles = tuple(
            _c(i * 60_000, "100", "102.5", "97.5", "100")
            for i in range(15)
        )
        result = VolatilityRegimeStrategy(window=14).analyze(_make_series(candles))
        assert result.findings["regime"] == "high"
        assert result.findings["atr_pct"] >= Decimal("3")
        assert result.findings["atr_pct"] < Decimal("6")

    def test_extremely_wide_candles_classify_as_extreme(self) -> None:
        candles = tuple(
            _c(i * 60_000, "100", "105", "95", "100") for i in range(15)
        )
        result = VolatilityRegimeStrategy(window=14).analyze(_make_series(candles))
        assert result.findings["regime"] == "extreme"
        assert result.findings["atr_pct"] >= Decimal("6")

    def test_too_few_bars_yields_low_confidence(self) -> None:
        candles = tuple(
            _c(i * 60_000, "100", "101", "99", "100") for i in range(5)
        )
        result = VolatilityRegimeStrategy(window=14).analyze(_make_series(candles))
        assert result.confidence is Confidence.LOW
        assert result.findings["atr"] is None
        assert result.findings["regime"] == "unknown"
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write `src/cryptozavr/application/strategies/volatility.py`:
```python
"""Volatility regime classifier via ATR."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from cryptozavr.application.strategies.base import AnalysisResult
from cryptozavr.domain.market_data import OHLCVSeries
from cryptozavr.domain.quality import Confidence

_THRESHOLDS: tuple[tuple[Decimal, str], ...] = (
    (Decimal(1), "calm"),
    (Decimal(3), "normal"),
    (Decimal(6), "high"),
)

class VolatilityRegimeStrategy:
    """Computes ATR over a window + classifies regime by ATR-as-%-of-close.

    Regime thresholds (atr / last_close × 100):
      < 1%  → calm
      < 3%  → normal
      < 6%  → high
      ≥ 6%  → extreme

    Needs at least `window + 1` candles (ATR needs prev close for the
    first bar). Fewer bars → `regime="unknown"`, `atr=None`, LOW conf.
    """

    name = "volatility_regime"

    def __init__(self, window: int = 14) -> None:
        self._window = window

    def analyze(self, series: OHLCVSeries) -> AnalysisResult:
        n = len(series.candles)
        if n < self._window + 1:
            return AnalysisResult(
                strategy=self.name,
                findings={
                    "atr": None,
                    "atr_pct": None,
                    "regime": "unknown",
                    "bars_used": n,
                    "window": self._window,
                },
                confidence=Confidence.LOW,
            )

        true_ranges: list[Decimal] = []
        for i in range(1, n):
            cur = series.candles[i]
            prev_close = series.candles[i - 1].close
            tr = max(
                cur.high - cur.low,
                abs(cur.high - prev_close),
                abs(cur.low - prev_close),
            )
            true_ranges.append(tr)

        recent_tr = true_ranges[-self._window :]
        atr = sum(recent_tr, Decimal(0)) / Decimal(len(recent_tr))
        last_close = series.candles[-1].close
        atr_pct = (
            atr / last_close * Decimal(100) if last_close > 0 else Decimal(0)
        )
        regime = self._classify(atr_pct)

        findings: dict[str, Any] = {
            "atr": atr,
            "atr_pct": atr_pct,
            "regime": regime,
            "bars_used": n,
            "window": self._window,
        }
        return AnalysisResult(
            strategy=self.name,
            findings=findings,
            confidence=Confidence.HIGH if n >= 2 * self._window else Confidence.MEDIUM,
        )

    @staticmethod
    def _classify(atr_pct: Decimal) -> str:
        for threshold, label in _THRESHOLDS:
            if atr_pct < threshold:
                return label
        return "extreme"
```

- [ ] **Step 4: PASS (4 tests).**

```bash
uv run pytest tests/unit/application/strategies/test_volatility.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```text
feat(app): add VolatilityRegimeStrategy

ATR-based regime classifier. True Range = max(h-l, |h-pc|, |l-pc|),
ATR = SMA(TR, window=14). Regime bands on ATR/close %: <1 calm,
<3 normal, <6 high, ≥6 extreme. Needs window+1 bars minimum;
less → regime="unknown" + LOW conf. ≥2×window bars → HIGH conf.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/application/strategies/volatility.py \
    tests/unit/application/strategies/test_volatility.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 5: `MarketAnalyzer` Strategy context

**Files:**
- Create: `src/cryptozavr/application/services/market_analyzer.py`
- Create: `tests/unit/application/services/test_market_analyzer.py`

- [ ] **Step 1: Write failing tests**

Write `tests/unit/application/services/test_market_analyzer.py`:
```python
"""Test MarketAnalyzer: dispatches to registered AnalysisStrategy by name."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.services.market_analyzer import (
    AnalysisReport,
    MarketAnalyzer,
)
from cryptozavr.application.strategies.base import AnalysisResult
from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, TimeRange, Timeframe
from cryptozavr.domain.venues import MarketType, VenueId

def _series() -> OHLCVSeries:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    quality = DataQuality(
        source=Provenance(venue_id="kucoin", endpoint="fetch_ohlcv"),
        fetched_at=Instant.from_ms(1_700_000_000_000),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )
    candles = (
        OHLCVCandle(
            opened_at=Instant.from_ms(0),
            open=Decimal("100"), high=Decimal("110"),
            low=Decimal("90"), close=Decimal("105"),
            volume=Decimal("10"),
        ),
    )
    return OHLCVSeries(
        symbol=symbol,
        timeframe=Timeframe.M1,
        candles=candles,
        range=TimeRange(
            start=Instant.from_ms(0),
            end=Instant.from_ms(60_000),
        ),
        quality=quality,
    )

class _FakeStrategy:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls = 0

    def analyze(self, series: OHLCVSeries) -> AnalysisResult:
        self.calls += 1
        return AnalysisResult(
            strategy=self.name,
            findings={"ran": True},
            confidence=Confidence.HIGH,
        )

class TestMarketAnalyzer:
    def test_dispatch_to_single_registered_strategy(self) -> None:
        strat = _FakeStrategy("volatility")
        analyzer = MarketAnalyzer(strategies={"volatility": strat})
        report = analyzer.analyze(
            series=_series(), strategy_names=("volatility",),
        )
        assert isinstance(report, AnalysisReport)
        assert strat.calls == 1
        assert len(report.results) == 1
        assert report.results[0].strategy == "volatility"
        assert report.symbol.native_symbol == "BTC-USDT"

    def test_dispatch_multiple_strategies_preserves_order(self) -> None:
        s1, s2 = _FakeStrategy("a"), _FakeStrategy("b")
        analyzer = MarketAnalyzer(strategies={"a": s1, "b": s2})
        report = analyzer.analyze(
            series=_series(), strategy_names=("b", "a"),
        )
        assert [r.strategy for r in report.results] == ["b", "a"]

    def test_unknown_strategy_raises(self) -> None:
        analyzer = MarketAnalyzer(strategies={"a": _FakeStrategy("a")})
        with pytest.raises(KeyError):
            analyzer.analyze(series=_series(), strategy_names=("missing",))
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write `src/cryptozavr/application/services/market_analyzer.py`:
```python
"""MarketAnalyzer — Strategy context over AnalysisStrategy registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from cryptozavr.application.strategies.base import (
    AnalysisResult,
    AnalysisStrategy,
)
from cryptozavr.domain.market_data import OHLCVSeries
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Timeframe

@dataclass(frozen=True, slots=True)
class AnalysisReport:
    """Aggregated output of MarketAnalyzer.analyze()."""

    symbol: Symbol
    timeframe: Timeframe
    results: tuple[AnalysisResult, ...]

class MarketAnalyzer:
    """Dispatches to registered AnalysisStrategy by name.

    The strategy registry is injected at construction. Consumers request
    strategies by name in `strategy_names`; the analyzer runs them in
    order and wraps results in an AnalysisReport.
    """

    def __init__(self, strategies: Mapping[str, AnalysisStrategy]) -> None:
        self._strategies: Mapping[str, AnalysisStrategy] = dict(strategies)

    def analyze(
        self,
        *,
        series: OHLCVSeries,
        strategy_names: tuple[str, ...],
    ) -> AnalysisReport:
        results: list[AnalysisResult] = []
        for name in strategy_names:
            strategy = self._strategies[name]  # raises KeyError if missing
            results.append(strategy.analyze(series))
        return AnalysisReport(
            symbol=series.symbol,
            timeframe=series.timeframe,
            results=tuple(results),
        )
```

- [ ] **Step 4: PASS (3 tests).**

```bash
uv run pytest tests/unit/application/services/test_market_analyzer.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```
Expect: 288 + 3 + 5 + 4 + 4 + 3 ≈ 307 tests.

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(app): add MarketAnalyzer Strategy context

Dispatches to registered AnalysisStrategy instances by name. Registry
injected at construction (Mapping[str, AnalysisStrategy]). analyze()
runs strategies in the caller-requested order, wraps them in an
AnalysisReport (symbol + timeframe + tuple[AnalysisResult]). Unknown
strategy → KeyError (hard fail; the registry is the contract).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/application/services/market_analyzer.py \
    tests/unit/application/services/test_market_analyzer.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 6: CHANGELOG + tag v0.1.1 + push

- [ ] **Step 1: Verify**

```bash
cd /Users/laptop/dev/cryptozavr
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```
Expect: clean; ~304 unit + 5 contract tests (288 + 16 new).

- [ ] **Step 2: Update CHANGELOG**

Edit `/Users/laptop/dev/cryptozavr/CHANGELOG.md`. Find:
```markdown
## [Unreleased]

## [0.1.0] - 2026-04-22
```

Replace with:
```markdown
## [Unreleased]

## [0.1.1] - 2026-04-22

### Added — M3.1 MarketAnalyzer (Strategy pattern)
- `AnalysisStrategy` Protocol (runtime_checkable) + `AnalysisResult` dataclass (strategy name, typed-dict findings, Confidence). Per MVP spec §5.
- `VwapStrategy` — Volume-Weighted Average Price via typical (h+l+c)/3 × volume. Zero-volume bars counted in bars_used but skipped in weighted sum. 5 unit tests.
- `SupportResistanceStrategy` — swing-pivot SR detector with level clustering (default window=2, cluster_pct=0.5). 4 unit tests.
- `VolatilityRegimeStrategy` — ATR-based regime classifier (calm/normal/high/extreme bands on ATR-as-%-of-close). Default window=14. 4 unit tests.
- `MarketAnalyzer` Strategy context — dispatches to strategy registry by name, preserves caller-requested order, wraps results in `AnalysisReport` (symbol + timeframe + tuple[AnalysisResult]). 3 unit tests.
- ~16 new unit tests. Total ≥304 unit + 5 contract + 14 integration (skip-safe).

### Next
- M3.2: Discovery tools (resolve_symbol, list_symbols, list_categories, scan_trending) — 4 new MCP tools + SymbolResolver service.
- M3.3: Analytics MCP tools on top of MarketAnalyzer (analyze_snapshot, compute_vwap, identify_support_resistance, volatility_regime).
- M3.4: fetch_ohlcv_history streaming + SessionExplainer envelope + /cryptozavr:scan/analyze commands → tag v0.2.0 (MVP closure).

## [0.1.0] - 2026-04-22
```

- [ ] **Step 3: Commit CHANGELOG + plan**

```bash
cd /Users/laptop/dev/cryptozavr
git add CHANGELOG.md
git add docs/superpowers/plans/2026-04-22-cryptozavr-m3.1-market-analyzer.md 2>/dev/null || true
```

Write to /tmp/commit-msg.txt:
```bash
docs: finalize CHANGELOG for v0.1.1 (M3.1 MarketAnalyzer)

Strategy pattern analytical layer: VWAP, Support/Resistance,
VolatilityRegime + MarketAnalyzer context. Pure-function layer,
foundation for M3.3 analytics MCP tools.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

- [ ] **Step 4: Tag + push**

Write tag message to /tmp/tag-msg.txt:
```bash
M3.1 MarketAnalyzer (Strategy pattern) complete

3 pure-function analytical strategies (VWAP, Support/Resistance,
VolatilityRegime) + MarketAnalyzer context dispatching by strategy
name. Foundation for M3.3 analytics MCP tools. 16 new unit tests.
```

```bash
cd /Users/laptop/dev/cryptozavr
git tag -a v0.1.1 -F /tmp/tag-msg.txt
rm /tmp/tag-msg.txt
git push origin main
git push origin v0.1.1
```

- [ ] **Step 5: Summary**

```bash
cd /Users/laptop/dev/cryptozavr
echo "=== M3.1 complete ==="
git log --oneline v0.1.0..HEAD
git tag -l | tail -5
```

---

## Acceptance Criteria

1. ✅ All 6 tasks done.
2. ✅ 16 new unit tests. Total ≥304 unit + 5 contract + 14 integration (skip-safe).
3. ✅ 3 strategies satisfy `isinstance(strat, AnalysisStrategy)` via `runtime_checkable` Protocol.
4. ✅ `MarketAnalyzer.analyze()` correctly dispatches to multiple strategies in requested order.
5. ✅ Empty / too-few-bar series handled gracefully (LOW confidence, no exceptions).
6. ✅ Mypy strict + ruff + pytest green.
7. ✅ Tag `v0.1.1` pushed to github.com/evgenygurin/cryptozavr.

---

## Notes

- **No new MCP tools** in this milestone — strategies are pure-domain additions. M3.3 wires them into tools.
- **Decimal everywhere** for prices — `float` would corrupt cross-exchange arithmetic. Volume is also Decimal for consistency.
- **No numpy**: keeps runtime tiny + the math simple enough that pure Python is adequate. If M3.3 backtesting needs speed, we can revisit.
- **Confidence policy**: LOW when bars < strategy minimum, MEDIUM in the middle band, HIGH when ≥ 2× minimum. Consistent across the three strategies so `SessionExplainer` can downsample on low-confidence findings later.
- **Runtime Protocol**: `AnalysisStrategy` is `@runtime_checkable` so external registrars (future Ichimoku plugin) can be verified with `isinstance` at wire time without inheritance.
- **`AnalysisReport.results`** is a tuple — preserves caller's strategy order and stays immutable. `AnalysisResult.findings` is a dict (mutable) — pragmatic for envelope serialization.
