# Changelog

All notable changes to cryptozavr will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.2] - 2026-04-21

### Added — M2.1 Domain layer
- Value objects: `Timeframe`, `Instant`, `TimeRange`, `Money`, `Percentage`, `PriceSize`.
- Quality types: `Staleness` (ordered FRESH<RECENT<STALE<EXPIRED), `Confidence`, `Provenance`, `DataQuality` envelope.
- Entities: `Asset` + `AssetCategory`, `Venue` + 5 enums, `Symbol` + `SymbolRegistry` (Flyweight).
- Market data: `Ticker`, `OHLCVCandle`, `OHLCVSeries` (with slice/window), `OrderBookSnapshot` (with spread/spread_bps), `TradeTick`, `TradeSide`, `MarketSnapshot` composite.
- Protocol interfaces: `MarketDataProvider`, `Repository[T]`, `Clock`.
- Exception hierarchy: `DomainError` root + 4 families (ValidationError, NotFoundError, ProviderError, QualityError) with domain-specific subtypes.
- Dev deps: `hypothesis`, `polyfactory` for property-based and factory-driven tests.
- 114 unit tests, domain coverage ≥ 94%.

### Fixed
- `Instant.to_ms()` uses `round()` instead of `int()` to preserve roundtrip precision (hypothesis property-based regression).

## [0.0.1] - 2026-04-21

### Added — M1 Bootstrap
- Repository initialization with git, uv, ruff, mypy, pytest, pre-commit.
- Claude Code plugin manifest (`plugin.json`, `.mcp.json`).
- FastMCP v3+ server skeleton with `echo` smoke tool.
- Supabase CLI init with `cryptozavr` schema reserved.
- CI pipelines: lint + typecheck + unit tests, plugin artefact validation.
- Documentation: README, CHANGELOG, design spec, M1 implementation plan.
