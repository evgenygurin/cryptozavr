"""Test AnalyticsService: orchestrates OhlcvService → MarketAnalyzer."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.application.services.analytics_service import AnalyticsService
from cryptozavr.application.services.market_analyzer import (
    AnalysisReport,
    MarketAnalyzer,
)
from cryptozavr.application.services.ohlcv_service import (
    OhlcvFetchResult,
    OhlcvService,
)
from cryptozavr.application.strategies.base import AnalysisResult
from cryptozavr.domain.exceptions import SymbolNotFoundError
from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe, TimeRange
from cryptozavr.domain.venues import MarketType, VenueId


def _series() -> OHLCVSeries:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
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
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal("105"),
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


def _fake_report(series: OHLCVSeries) -> AnalysisReport:
    return AnalysisReport(
        symbol=series.symbol,
        timeframe=series.timeframe,
        results=(
            AnalysisResult(
                strategy="test_strategy",
                findings={"ran": True},
                confidence=Confidence.HIGH,
            ),
        ),
    )


class TestAnalyticsService:
    """Tests for AnalyticsService L4 orchestrator."""

    @pytest.mark.asyncio
    async def test_analyze_calls_ohlcv_service_then_market_analyzer(self) -> None:
        """Verify fetch_ohlcv is awaited with correct kwargs then analyzer.analyze called."""
        series = _series()
        fake_reason_codes = ["cache:miss", "provider:kucoin_spot"]
        ohlcv_result = OhlcvFetchResult(series=series, reason_codes=fake_reason_codes)
        report = _fake_report(series)

        mock_ohlcv_service = AsyncMock(spec=OhlcvService)
        mock_ohlcv_service.fetch_ohlcv.return_value = ohlcv_result

        mock_analyzer = MagicMock(spec=MarketAnalyzer)
        mock_analyzer.analyze.return_value = report

        service = AnalyticsService(
            ohlcv_service=mock_ohlcv_service,
            analyzer=mock_analyzer,
        )

        result = await service.analyze(
            venue="kucoin_spot",
            symbol="BTC/USDT",
            timeframe=Timeframe.M1,
            limit=200,
            force_refresh=False,
            strategy_names=("test_strategy",),
        )

        mock_ohlcv_service.fetch_ohlcv.assert_awaited_once_with(
            venue="kucoin_spot",
            symbol="BTC/USDT",
            timeframe=Timeframe.M1,
            limit=200,
            force_refresh=False,
        )
        mock_analyzer.analyze.assert_called_once_with(
            series=series,
            strategy_names=("test_strategy",),
        )
        assert result == (report, fake_reason_codes)

    @pytest.mark.asyncio
    async def test_analyze_propagates_reason_codes_from_ohlcv(self) -> None:
        """Reason codes from OhlcvFetchResult are returned as-is."""
        series = _series()
        reason_codes = ["cache:miss", "provider:kucoin_spot"]
        ohlcv_result = OhlcvFetchResult(series=series, reason_codes=reason_codes)
        report = _fake_report(series)

        mock_ohlcv_service = AsyncMock(spec=OhlcvService)
        mock_ohlcv_service.fetch_ohlcv.return_value = ohlcv_result

        mock_analyzer = MagicMock(spec=MarketAnalyzer)
        mock_analyzer.analyze.return_value = report

        service = AnalyticsService(
            ohlcv_service=mock_ohlcv_service,
            analyzer=mock_analyzer,
        )

        _, returned_codes = await service.analyze(
            venue="kucoin_spot",
            symbol="BTC/USDT",
            timeframe=Timeframe.M1,
            limit=100,
            force_refresh=True,
            strategy_names=("test_strategy",),
        )

        assert returned_codes is reason_codes
        assert returned_codes == ["cache:miss", "provider:kucoin_spot"]

    @pytest.mark.asyncio
    async def test_analyze_reraises_ohlcv_errors(self) -> None:
        """SymbolNotFoundError from OhlcvService propagates without catching."""

        mock_ohlcv_service = AsyncMock(spec=OhlcvService)
        mock_ohlcv_service.fetch_ohlcv.side_effect = SymbolNotFoundError(
            user_input="UNKNOWN/USDT",
            venue="kucoin_spot",
        )

        mock_analyzer = MagicMock(spec=MarketAnalyzer)

        service = AnalyticsService(
            ohlcv_service=mock_ohlcv_service,
            analyzer=mock_analyzer,
        )

        with pytest.raises(SymbolNotFoundError):
            await service.analyze(
                venue="kucoin_spot",
                symbol="UNKNOWN/USDT",
                timeframe=Timeframe.M1,
                limit=200,
                force_refresh=False,
                strategy_names=("test_strategy",),
            )

        mock_analyzer.analyze.assert_not_called()
