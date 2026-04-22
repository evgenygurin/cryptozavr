"""Unit 2D-3 compute-layer strategy tools.

Four MCP tools:
  * backtest_strategy — flagship; load OHLCV via OhlcvService, run through
    BacktestEngine, attach 5 visitor metrics.
  * compare_strategies — backtest several specs sequentially, build a
    side-by-side comparison dict keyed by metric name.
  * stress_test — run a spec against synthetic bull / bear / chop regimes
    (no OhlcvService call; scenarios are deterministic pd.DataFrames).
  * save_strategy — stub until Unit 2E-1 lands real persistence.

All four tools receive their payload as a single `dict[str, Any]` so
malformed JSON surfaces as a structured `error` field instead of a
pydantic ValidationError at dispatch time (same pattern as
validate_strategy / explain_strategy in 2D-1/2D-2).
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Annotated, Any

import pandas as pd
from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field, ValidationError

from cryptozavr.application.analytics.analytics_service import (
    BacktestAnalyticsService,
)
from cryptozavr.application.analytics.visitors.max_drawdown import MaxDrawdownVisitor
from cryptozavr.application.analytics.visitors.profit_factor import (
    ProfitFactorVisitor,
)
from cryptozavr.application.analytics.visitors.sharpe import SharpeRatioVisitor
from cryptozavr.application.analytics.visitors.total_return import TotalReturnVisitor
from cryptozavr.application.analytics.visitors.win_rate import WinRateVisitor
from cryptozavr.application.backtest.engine import BacktestEngine
from cryptozavr.application.services.ohlcv_service import OhlcvService
from cryptozavr.application.strategy.strategy_spec import StrategySpec
from cryptozavr.domain.exceptions import ValidationError as DomainValidationError
from cryptozavr.domain.market_data import OHLCVSeries
from cryptozavr.domain.value_objects import Instant
from cryptozavr.mcp.lifespan_state import get_ohlcv_service
from cryptozavr.mcp.tools.strategy_backtest_dtos import (
    BacktestReportDTO,
    BacktestStrategyResponse,
    CompareStrategiesResponse,
    NamedBacktestDTO,
    SaveStrategyResponse,
    StressTestResponse,
)
from cryptozavr.mcp.tools.strategy_dtos import StrategySpecPayload

_DEFAULT_LIMIT = 500
_DEFAULT_INITIAL_EQUITY = "10000"
_DEFAULT_SCENARIOS = ("bull", "bear", "chop")
_SCENARIO_BARS = 200

# Module-level singleton — avoids B008 (function call in default argument).
_OHLCV_SERVICE: OhlcvService = Depends(get_ohlcv_service)


# --------------------------- helpers -----------------------------------------


def _default_visitors() -> list[Any]:
    """The five MVP visitors, rebuilt fresh each call (all stateless, cheap).

    Return type is `list[Any]` rather than `list[BacktestVisitor[Any]]` because
    the concrete visitor classes declare `name` as a regular class attribute,
    not a `ClassVar[str]`, and mypy's Protocol structural check is strict
    about that distinction — see the `BacktestVisitor` docstring. At runtime
    `BacktestAnalyticsService.__init__` reads `.name` / `.visit` directly,
    so the loosened type is type-safe in practice.
    """
    return [
        TotalReturnVisitor(),
        WinRateVisitor(),
        MaxDrawdownVisitor(),
        ProfitFactorVisitor(),
        SharpeRatioVisitor(),
    ]


def _to_decimal_or_none(v: Any) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _ohlcv_series_to_dataframe(series: OHLCVSeries) -> pd.DataFrame:
    """Convert an OHLCVSeries to the float-typed DataFrame BacktestEngine expects.

    Columns: open / high / low / close / volume. Index: epoch-ms per candle.
    We lose Decimal precision at the pandas boundary (floats are cheaper for
    vectorised indicator computation). `trade_simulator.to_decimal` converts
    back via str() at the simulator boundary so we don't eat float artifacts.
    """
    return pd.DataFrame(
        {
            "open": [float(c.open) for c in series.candles],
            "high": [float(c.high) for c in series.candles],
            "low": [float(c.low) for c in series.candles],
            "close": [float(c.close) for c in series.candles],
            "volume": [float(c.volume) for c in series.candles],
        },
        index=[c.opened_at.to_ms() for c in series.candles],
    )


def _synthetic_scenario(name: str) -> pd.DataFrame:
    """Deterministic 200-bar DataFrames for stress_test.

    bull: linear uptrend 100 → ~200, small deterministic oscillation.
    bear: linear downtrend 200 → ~100, same oscillation.
    chop: sine wave, amplitude 10 around 150.
    """
    n = _SCENARIO_BARS
    if name == "bull":
        close_raw = [100.0 + (i * 0.5) + ((i % 7) * 0.3 - 0.9) for i in range(n)]
    elif name == "bear":
        close_raw = [200.0 - (i * 0.5) + ((i % 7) * 0.3 - 0.9) for i in range(n)]
    elif name == "chop":
        close_raw = [150.0 + 10 * math.sin(i / 5) for i in range(n)]
    else:
        raise ValueError(f"unknown scenario: {name!r}")
    # Quantize to 2 decimal places — keeps the float → Decimal conversion
    # inside TradeSimulator deterministic. Without rounding, chop's sine
    # output can produce entry/exit prices whose float artefacts flip the
    # pnl sign relative to (entry - exit), tripping BacktestTrade's
    # pnl-sign invariant.
    close = [round(c, 2) for c in close_raw]
    return pd.DataFrame(
        {
            "open": close,
            "high": [round(c + 1.0, 2) for c in close],
            "low": [round(c - 1.0, 2) for c in close],
            "close": close,
            "volume": [1000.0] * n,
        },
    )


def _parse_spec_or_error(spec_raw: Any) -> tuple[StrategySpec | None, str | None]:
    """Parse a raw dict into a domain StrategySpec, return (spec, error_msg).

    Two-phase error handling mirrors validate_strategy: pydantic shape errors
    first, then Symbol / domain invariants via to_domain().
    """
    if not isinstance(spec_raw, dict) or not spec_raw:
        return None, "spec invalid: expected non-empty object"
    try:
        payload = StrategySpecPayload.model_validate(spec_raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = "/".join(str(p) for p in first["loc"]) or "<root>"
        return None, f"spec invalid at {loc}: {first['msg']}"
    try:
        domain_spec = payload.to_domain()
    except (DomainValidationError, ValueError) as exc:
        return None, f"spec domain invalid: {exc}"
    return domain_spec, None


def _run_backtest_on_dataframe(
    domain_spec: StrategySpec,
    candles_df: pd.DataFrame,
    initial_equity: Decimal,
) -> tuple[BacktestReportDTO | None, dict[str, Decimal | None], str | None]:
    """Run engine + visitors on an already-prepared DataFrame.

    Returns (report_dto, metrics, error_msg). Engine errors surface as error
    strings so compare_strategies / stress_test can collect them per-scenario
    instead of aborting the whole run.
    """
    try:
        report = BacktestEngine().run(
            domain_spec,
            candles_df,
            initial_equity=initial_equity,
        )
    except DomainValidationError as exc:
        return None, {}, f"backtest failed: {exc}"
    except Exception as exc:
        # we translate to a wire-format error for the client.
        return None, {}, f"backtest failed: {type(exc).__name__}: {exc}"
    raw_metrics = BacktestAnalyticsService(_default_visitors()).run_all(report)
    metrics = {name: _to_decimal_or_none(v) for name, v in raw_metrics.items()}
    return BacktestReportDTO.from_domain(report), metrics, None


async def _run_backtest_with_fetch(
    ohlcv_service: OhlcvService,
    domain_spec: StrategySpec,
    *,
    limit: int,
    since: Instant | None,
    force_refresh: bool,
    initial_equity: Decimal,
) -> tuple[BacktestReportDTO | None, dict[str, Decimal | None], list[str], str | None]:
    """Fetch OHLCV then run backtest. Shared between backtest_strategy and
    compare_strategies so the side-by-side variant doesn't duplicate logic."""
    try:
        fetch_result = await ohlcv_service.fetch_ohlcv(
            venue=domain_spec.venue.value,
            symbol=domain_spec.symbol.native_symbol,
            timeframe=domain_spec.timeframe,
            limit=limit,
            since=since,
            force_refresh=force_refresh,
        )
    except Exception as exc:
        # errors; surface them verbatim to the client as a single error line.
        return None, {}, [], f"ohlcv fetch failed: {type(exc).__name__}: {exc}"
    candles_df = _ohlcv_series_to_dataframe(fetch_result.series)
    report_dto, metrics, engine_err = _run_backtest_on_dataframe(
        domain_spec, candles_df, initial_equity
    )
    return report_dto, metrics, list(fetch_result.reason_codes), engine_err


def _extract_common_inputs(
    payload: dict[str, Any],
) -> tuple[int, Instant | None, Decimal, bool]:
    """Pull limit / since_ms / initial_equity / force_refresh from a tool payload
    with tolerant defaults. Raises ValueError on malformed numeric input."""
    limit = int(payload.get("limit") or _DEFAULT_LIMIT)
    since_ms = payload.get("since_ms")
    since = Instant.from_ms(int(since_ms)) if since_ms is not None else None
    initial_equity = Decimal(str(payload.get("initial_equity") or _DEFAULT_INITIAL_EQUITY))
    force_refresh = bool(payload.get("force_refresh") or False)
    return limit, since, initial_equity, force_refresh


# --------------------------- tool impl (module-level) ------------------------
# Each tool's body lives at module level so `register_strategy_compute_tools`
# stays a thin decorator pass (keeps PLR0915 happy). FastMCP's `.tool()`
# decorator is applied inside `register_strategy_compute_tools` via a small
# wrapper that bridges the `Depends(...)` default back to the impl.


async def _backtest_strategy_impl(
    payload: dict[str, Any],
    ctx: Context,
    ohlcv_service: OhlcvService,
) -> BacktestStrategyResponse:
    await ctx.info("backtest_strategy")
    domain_spec, err = _parse_spec_or_error(payload.get("spec"))
    if err is not None or domain_spec is None:
        return BacktestStrategyResponse(error=err or "spec invalid")
    try:
        limit, since, initial_equity, force_refresh = _extract_common_inputs(payload)
    except (ValueError, TypeError) as exc:
        return BacktestStrategyResponse(error=f"payload invalid: {exc}")

    report_dto, metrics, reason_codes, engine_err = await _run_backtest_with_fetch(
        ohlcv_service,
        domain_spec,
        limit=limit,
        since=since,
        force_refresh=force_refresh,
        initial_equity=initial_equity,
    )
    if engine_err is not None:
        return BacktestStrategyResponse(error=engine_err, reason_codes=reason_codes)
    if report_dto is None:
        # Defensive: should never happen when engine_err is None.
        return BacktestStrategyResponse(
            error="backtest failed: unknown",
            reason_codes=reason_codes,
        )
    return BacktestStrategyResponse(
        report=report_dto,
        metrics=metrics,
        reason_codes=reason_codes,
    )


async def _compare_strategies_impl(
    payload: dict[str, Any],
    ctx: Context,
    ohlcv_service: OhlcvService,
) -> CompareStrategiesResponse:
    await ctx.info("compare_strategies")
    specs_raw = payload.get("specs") or []
    if not isinstance(specs_raw, list):
        return CompareStrategiesResponse(errors=["specs must be a list"])
    try:
        limit, since, initial_equity, force_refresh = _extract_common_inputs(payload)
    except (ValueError, TypeError) as exc:
        return CompareStrategiesResponse(errors=[f"payload invalid: {exc}"])

    results, errors = await _run_compare_loop(
        ohlcv_service,
        specs_raw,
        limit=limit,
        since=since,
        force_refresh=force_refresh,
        initial_equity=initial_equity,
    )
    return CompareStrategiesResponse(
        results=results,
        comparison=_pivot_comparison(results),
        errors=errors,
    )


async def _run_compare_loop(
    ohlcv_service: OhlcvService,
    specs_raw: list[Any],
    *,
    limit: int,
    since: Instant | None,
    force_refresh: bool,
    initial_equity: Decimal,
) -> tuple[list[NamedBacktestDTO], list[str]]:
    results: list[NamedBacktestDTO] = []
    errors: list[str] = []
    for i, spec_raw in enumerate(specs_raw):
        domain_spec, err = _parse_spec_or_error(spec_raw)
        if err is not None or domain_spec is None:
            hint = (
                spec_raw.get("name")
                if isinstance(spec_raw, dict) and isinstance(spec_raw.get("name"), str)
                else f"spec[{i}]"
            )
            errors.append(f"{hint}: {err}")
            continue
        report_dto, metrics, _reason_codes, engine_err = await _run_backtest_with_fetch(
            ohlcv_service,
            domain_spec,
            limit=limit,
            since=since,
            force_refresh=force_refresh,
            initial_equity=initial_equity,
        )
        if engine_err is not None:
            errors.append(f"{domain_spec.name}: {engine_err}")
            results.append(
                NamedBacktestDTO(strategy_name=domain_spec.name, error=engine_err),
            )
            continue
        results.append(
            NamedBacktestDTO(
                strategy_name=domain_spec.name,
                report=report_dto,
                metrics=metrics,
            ),
        )
    return results, errors


def _pivot_comparison(
    results: list[NamedBacktestDTO],
) -> dict[str, dict[str, Decimal | None]]:
    """Metric → {strategy_name → value}. Last-wins on name collision."""
    comparison: dict[str, dict[str, Decimal | None]] = {}
    for entry in results:
        if entry.error is not None:
            continue
        for metric_name, value in entry.metrics.items():
            comparison.setdefault(metric_name, {})[entry.strategy_name] = value
    return comparison


async def _stress_test_impl(
    payload: dict[str, Any],
    ctx: Context,
) -> StressTestResponse:
    await ctx.info("stress_test")
    domain_spec, err = _parse_spec_or_error(payload.get("spec"))
    if err is not None or domain_spec is None:
        return StressTestResponse(errors=[err or "spec invalid"])
    scenarios_raw = payload.get("scenarios") or list(_DEFAULT_SCENARIOS)
    if not isinstance(scenarios_raw, list):
        return StressTestResponse(errors=["scenarios must be a list"])
    try:
        initial_equity = Decimal(
            str(payload.get("initial_equity") or _DEFAULT_INITIAL_EQUITY),
        )
    except (ValueError, TypeError) as exc:
        return StressTestResponse(errors=[f"initial_equity invalid: {exc}"])

    results, errors = _run_stress_scenarios(
        domain_spec,
        scenarios_raw,
        initial_equity=initial_equity,
    )
    return StressTestResponse(results=results, errors=errors)


def _run_stress_scenarios(
    domain_spec: StrategySpec,
    scenarios_raw: list[Any],
    *,
    initial_equity: Decimal,
) -> tuple[dict[str, NamedBacktestDTO], list[str]]:
    results: dict[str, NamedBacktestDTO] = {}
    errors: list[str] = []
    for scenario_name in scenarios_raw:
        if not isinstance(scenario_name, str):
            errors.append(f"{scenario_name!r}: scenario name must be a string")
            continue
        try:
            df = _synthetic_scenario(scenario_name)
        except ValueError as exc:
            errors.append(f"{scenario_name}: {exc}")
            continue
        report_dto, metrics, engine_err = _run_backtest_on_dataframe(
            domain_spec,
            df,
            initial_equity,
        )
        if engine_err is not None:
            errors.append(f"{scenario_name}: {engine_err}")
            results[scenario_name] = NamedBacktestDTO(
                strategy_name=scenario_name,
                error=engine_err,
            )
            continue
        results[scenario_name] = NamedBacktestDTO(
            strategy_name=scenario_name,
            report=report_dto,
            metrics=metrics,
        )
    return results, errors


async def _save_strategy_impl(
    spec: dict[str, Any],
    ctx: Context,
) -> SaveStrategyResponse:
    await ctx.info("save_strategy")
    _domain_spec, err = _parse_spec_or_error(spec)
    if err is not None:
        return SaveStrategyResponse(id=None, note="", error=err)
    return SaveStrategyResponse(
        id=None,
        note="Persistence lands in Unit 2E-1; spec validated but not stored.",
    )


# --------------------------- registration ------------------------------------


def register_strategy_compute_tools(mcp: FastMCP) -> None:
    """Attach backtest_strategy / compare_strategies / stress_test / save_strategy."""

    @mcp.tool(
        name="backtest_strategy",
        description=(
            "Load OHLCV via OhlcvService, run a StrategySpec through the "
            "BacktestEngine, and return the report plus five canonical "
            "visitor metrics (total_return, win_rate, max_drawdown, "
            "profit_factor, sharpe_ratio). Venue / symbol / timeframe come "
            "from the spec itself."
        ),
        tags={"strategy", "compute", "phase-2"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": False,
            "destructiveHint": False,
        },
    )
    async def backtest_strategy(
        payload: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Backtest request: {spec, limit?, since_ms?, initial_equity?, force_refresh?}"
                ),
            ),
        ],
        ctx: Context,
        ohlcv_service: OhlcvService = _OHLCV_SERVICE,
    ) -> BacktestStrategyResponse:
        return await _backtest_strategy_impl(payload, ctx, ohlcv_service)

    @mcp.tool(
        name="compare_strategies",
        description=(
            "Backtest several StrategySpecs sequentially and return a "
            "side-by-side comparison dict keyed by metric name. Continues "
            "on per-spec failure (errors collected in `errors` list). "
            "When two specs share a name the last one wins in the "
            "comparison dict; the full ordered results list preserves all."
        ),
        tags={"strategy", "compute", "phase-2"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": False,
            "destructiveHint": False,
        },
    )
    async def compare_strategies(
        payload: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Comparison request: {specs: [spec, ...], limit?, "
                    "since_ms?, initial_equity?, force_refresh?}"
                ),
            ),
        ],
        ctx: Context,
        ohlcv_service: OhlcvService = _OHLCV_SERVICE,
    ) -> CompareStrategiesResponse:
        return await _compare_strategies_impl(payload, ctx, ohlcv_service)

    @mcp.tool(
        name="stress_test",
        description=(
            "Run a StrategySpec against synthetic market regimes. Default "
            "scenarios: bull (uptrend), bear (downtrend), chop (sine wave). "
            "Each scenario is a deterministic 200-bar DataFrame built "
            "in-process — no OhlcvService call, so this tool is safe to "
            "exercise offline."
        ),
        tags={"strategy", "compute", "phase-2"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": False,
            "destructiveHint": False,
        },
    )
    async def stress_test(
        payload: Annotated[
            dict[str, Any],
            Field(description="Stress-test request: {spec, scenarios?, initial_equity?}"),
        ],
        ctx: Context,
    ) -> StressTestResponse:
        return await _stress_test_impl(payload, ctx)

    @mcp.tool(
        name="save_strategy",
        description=(
            "Persist a StrategySpec. STUB until Unit 2E-1 lands a real "
            "repository — parses the payload and returns a placeholder "
            "response explaining the stub; does not mutate any store."
        ),
        tags={"strategy", "compute", "phase-2"},
        annotations={
            "readOnlyHint": True,  # Stub — actually stateless for MVP.
            "idempotentHint": False,
            "destructiveHint": False,
        },
    )
    async def save_strategy(
        spec: Annotated[
            dict[str, Any],
            Field(description="StrategySpec payload (raw JSON object)."),
        ],
        ctx: Context,
    ) -> SaveStrategyResponse:
        return await _save_strategy_impl(spec, ctx)
