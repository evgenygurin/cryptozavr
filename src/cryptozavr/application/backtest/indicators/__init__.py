"""Streaming technical indicators for Phase 2B backtest execution.

Each indicator consumes `OHLCVCandle`s one-at-a-time via `update()` and
returns `Decimal | None` — `None` during warm-up, concrete Decimal once
the indicator has seen enough bars.
"""
