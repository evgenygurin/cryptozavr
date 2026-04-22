"""AnalyticsService — L4 orchestrator: OHLCV fetch → market analysis."""

from __future__ import annotations

from cryptozavr.application.services.market_analyzer import AnalysisReport, MarketAnalyzer
from cryptozavr.application.services.ohlcv_service import OhlcvService
from cryptozavr.domain.value_objects import Timeframe


class AnalyticsService:
    """L4 orchestrator: fetches OHLCV and runs market analysis strategies."""

    def __init__(
        self,
        *,
        ohlcv_service: OhlcvService,
        analyzer: MarketAnalyzer,
    ) -> None:
        self._ohlcv_service = ohlcv_service
        self._analyzer = analyzer

    async def analyze(
        self,
        *,
        venue: str,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 200,
        force_refresh: bool = False,
        strategy_names: tuple[str, ...],
    ) -> tuple[AnalysisReport, list[str]]:
        """Fetch OHLCV then run analyzer. Returns (report, reason_codes)."""
        ohlcv_result = await self._ohlcv_service.fetch_ohlcv(
            venue=venue,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            force_refresh=force_refresh,
        )
        report = self._analyzer.analyze(
            series=ohlcv_result.series,
            strategy_names=strategy_names,
        )
        return report, ohlcv_result.reason_codes
