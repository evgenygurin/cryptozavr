# cryptozavr — Milestone 3.3: Analytics MCP tools (compact plan)

**Goal:** Wrap M3.1's MarketAnalyzer strategies (VWAP, Support/Resistance, VolatilityRegime) as 3 single-strategy MCP tools + 1 composite `analyze_snapshot` tool. Each tool fetches OHLCV via `OhlcvService` (cache-aside, reason_codes propagated) then runs the selected strategy.

**Idiomatic per M3.0:** `Depends(get_ohlcv_service)` + `Depends(get_market_analyzer)` + `ctx.info` logging.

**Starting tag:** `v0.1.3`. Target: `v0.1.4`.

## Tasks

1. **Analysis DTOs** — `AnalysisResultDTO` (strategy/confidence/findings) + `AnalysisReportDTO` (symbol/timeframe/results). `findings` kept as `dict[str, Any]` with Decimal preservation via `model_dump(mode="json")`.
2. **AnalyticsService L4** — composes `OhlcvService.fetch_ohlcv()` → `MarketAnalyzer.analyze()`. Method: `analyze(*, venue, symbol, timeframe, limit, force_refresh, strategy_names)` → `(AnalysisReport, reason_codes)`.
3. **3 single-strategy tools** — `compute_vwap`, `identify_support_resistance`, `volatility_regime`. Each calls AnalyticsService with single strategy, returns `AnalysisResultDTO` + reason_codes.
4. **`analyze_snapshot` composite** — runs all 3 strategies in one call, returns `AnalysisReportDTO`.
5. **Wire** — bootstrap builds `MarketAnalyzer(strategies={"vwap": VwapStrategy(), ...})` + `AnalyticsService(ohlcv_service, analyzer)`; add `analytics_service` to `LIFESPAN_KEYS`; register 4 tools in server.py; add `/cryptozavr:analyze` slash command + banner update.
6. **CHANGELOG + tag v0.1.4 + push**.

Target: ~20 new unit tests, plugin surface → **10 tools** (+4 analytics).
