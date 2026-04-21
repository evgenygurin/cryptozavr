"""Volume-Weighted Average Price strategy."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.strategies.base import AnalysisResult
from cryptozavr.domain.market_data import OHLCVSeries
from cryptozavr.domain.quality import Confidence

_THREE = Decimal(3)
_HIGH_CONFIDENCE_THRESHOLD = 10


class VwapStrategy:
    """Computes VWAP = sum(typical_price * volume) / sum(volume).

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
        confidence = (
            Confidence.HIGH if bars_used >= _HIGH_CONFIDENCE_THRESHOLD else Confidence.MEDIUM
        )
        return AnalysisResult(
            strategy=self.name,
            findings={
                "vwap": vwap,
                "total_volume": total_volume,
                "bars_used": bars_used,
            },
            confidence=confidence,
        )
