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
    """Computes ATR over a window + classifies regime by ATR as % of close.

    Regime thresholds (atr / last_close * 100):
      < 1%  -> calm
      < 3%  -> normal
      < 6%  -> high
      >= 6% -> extreme

    Needs at least `window + 1` candles (ATR needs prev close for the
    first bar). Fewer bars -> regime="unknown", atr=None, LOW conf.
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
        atr_pct = atr / last_close * Decimal(100) if last_close > 0 else Decimal(0)
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
            confidence=(Confidence.HIGH if n >= 2 * self._window else Confidence.MEDIUM),
        )

    @staticmethod
    def _classify(atr_pct: Decimal) -> str:
        for threshold, label in _THRESHOLDS:
            if atr_pct < threshold:
                return label
        return "extreme"
