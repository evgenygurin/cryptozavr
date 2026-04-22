"""Swing-based Support/Resistance detector."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.strategies.base import AnalysisResult
from cryptozavr.domain.market_data import OHLCVSeries
from cryptozavr.domain.quality import Confidence

_HIGH_CONFIDENCE_BARS = 20


class SupportResistanceStrategy:
    """Finds pivot highs/lows (swing bars) and clusters them.

    Pivot high at index i: high[i] > high[j] for all j in
    [i-window, i+window] \\ {i}. Pivot low: mirror on low.

    Levels within `cluster_pct` percent of each other are merged —
    their mean becomes the final level.
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
                    "pivots_found": 0,
                    "bars_used": len(series.candles),
                    "window": self._window,
                },
                confidence=Confidence.LOW,
            )

        raw_supports: list[Decimal] = []
        raw_resistances: list[Decimal] = []
        for i in range(self._window, len(series.candles) - self._window):
            center = series.candles[i]
            neighbours = (
                series.candles[i - self._window : i] + series.candles[i + 1 : i + self._window + 1]
            )
            if all(center.high > other.high for other in neighbours):
                raw_resistances.append(center.high)
            if all(center.low < other.low for other in neighbours):
                raw_supports.append(center.low)

        supports = tuple(self._cluster(sorted(raw_supports)))
        resistances = tuple(self._cluster(sorted(raw_resistances, reverse=True)))

        confidence = (
            Confidence.HIGH
            if supports and resistances and len(series.candles) >= _HIGH_CONFIDENCE_BARS
            else Confidence.MEDIUM
            if supports or resistances
            else Confidence.LOW
        )
        return AnalysisResult(
            strategy=self.name,
            findings={
                "supports": supports,
                "resistances": resistances,
                "pivots_found": len(raw_supports) + len(raw_resistances),
                "bars_used": len(series.candles),
                "window": self._window,
            },
            confidence=confidence,
        )

    def _cluster(self, levels: list[Decimal]) -> list[Decimal]:
        """Merge levels within `cluster_pct` percent; return group means."""
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
        return [sum(group, Decimal(0)) / Decimal(len(group)) for group in clusters]
