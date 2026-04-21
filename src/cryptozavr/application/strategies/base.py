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
