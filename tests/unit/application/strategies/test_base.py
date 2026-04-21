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
            strategy="test",
            findings={},
            confidence=Confidence.LOW,
        )
        with pytest.raises((AttributeError, Exception)):
            result.strategy = "other"  # type: ignore[misc]


class TestAnalysisStrategyProtocol:
    def test_protocol_has_name_attribute_and_analyze_method(self) -> None:
        class _Impl:
            name = "dummy"

            def analyze(self, series: OHLCVSeries) -> AnalysisResult:
                return AnalysisResult(
                    strategy=self.name,
                    findings={},
                    confidence=Confidence.LOW,
                )

        impl: AnalysisStrategy = _Impl()
        assert impl.name == "dummy"
