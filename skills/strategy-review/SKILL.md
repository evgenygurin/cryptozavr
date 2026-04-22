---
name: strategy-review
description: Use when the user brings a declarative trading strategy (StrategySpec payload, a saved strategy id, or a plain-language "review my strategy" request). This skill runs the validate → explain → backtest → compare/stress → save loop against the Phase-2 MCP tools and packages the findings in a Claude-friendly order.
---

# Strategy Review Workflow

## When to invoke

- User pastes or builds a `StrategySpec` payload and asks for a review, critique, or sanity-check.
- User asks "will this strategy work?", "is this a reasonable setup?", or similar **qualitative** questions about a strategy — before it has been backtested in this session.
- User references a strategy they previously saved (by name or UUID) and wants to revisit it.
- User wants to compare two or more candidate strategies against each other (invokes `compare_strategies` rather than `backtest_strategy` alone).

Do NOT invoke for:
- Pure market-data lookups (use `/cryptozavr:research`).
- Live-trading or order-placement questions — those don't exist in Phase 2.
- Re-runs of a backtest with different OHLCV without spec changes — just call `backtest_strategy` directly.

## The review loop

1. **Parse intent.** Is the user comparing, tuning, stress-testing, or just asking "is this well-formed?"
2. **Validate first (cheap).** Call `validate_strategy` with the raw payload. If `valid=False`, stop — report issues with `location` path + message + type, suggest fixes, wait for a new payload.
3. **Explain (human-readable).** Call `explain_strategy` so the user sees their spec in plain text (entry/exit/risk sections). Use this to confirm you both understand the same strategy before spending compute on a backtest.
4. **Backtest (flagship).** Call `backtest_strategy` with the validated payload. Set `initial_equity` to a round number like `10000` unless the user specifies. Default `limit=500`; bump to `limit=1500` for longer lookbacks if the user cares about multi-month behaviour.
5. **Inspect metrics.** Pull `metrics.total_return`, `win_rate`, `max_drawdown`, `profit_factor`, `sharpe_ratio` out of the response. Flag any unusual combinations (e.g. high win_rate + negative total_return → fees/slippage eating the edge).
6. **Stress-test (optional).** If the backtest looks good, call `stress_test` with the default `bull/bear/chop` scenarios to see whether the edge survives different regimes. If one regime catastrophically loses, call that out — it's a robustness signal.
7. **Compare (optional).** If the user supplied multiple candidates, call `compare_strategies([...specs])` and highlight the per-metric winner using the pivoted `comparison` dict.
8. **Save (opt-in).** Ask before saving. If the user wants to keep a spec around, call `save_strategy` and record the returned UUID so the user can reference it later.
9. **Advise — carefully.** Translate numbers into observations, not orders. "This draws down 28% — that's deep enough that most humans would abandon the system mid-drawdown." Not "you should raise your stop-loss."

## Tool selection matrix

| Question | Tool |
|----------|------|
| "Is my spec valid?" | `validate_strategy` |
| "Explain what this strategy does" | `explain_strategy` |
| "How well did it perform?" | `backtest_strategy` |
| "Does it hold up in a downturn?" | `stress_test(scenarios=["bear"])` or default 3 scenarios |
| "Which of these three is best?" | `compare_strategies` |
| "Save this one for later" | `save_strategy` (returns UUID) |
| "Show me what I've saved" | `list_strategies(limit=50)` |
| "What's different between v1 and v2?" | `diff_strategies(a, b)` |

All eight tools are `strategy`-tagged and `phase-2`. They are read-only (no balances moved, no orders placed) and idempotent with respect to each other — except `save_strategy` which persists a row (upsert-by-hash).

## Rails

- **No live-trading advice.** Phase 2 has no execution surface. Never tell the user to enter a position.
- **Don't hide poor metrics.** If `total_return < 0` or `max_drawdown > 50%`, say so first, not last.
- **Don't over-interpret a single backtest.** Backtests reflect the OHLCV window they ran on. Always note the window (inferred from `report.period_start_ms` / `period_end_ms`).
- **Placeholder embedding is semantically meaningless.** If the user asks for similarity search ("find strategies like this one"), clarify that the current embedding is a BLAKE2b placeholder — real similarity lands when the embedding provider is wired.
- **Fees and slippage are opinionated defaults.** `BacktestEngine` uses 5 bps fees + 10 bps slippage if unset. Tell the user when metrics are sensitive to these — they usually are at high turnover.

## Subagent delegation

For non-trivial reviews that bounce through ≥3 tools + interpretation (e.g. "tune my EMA crossover for BTC 1h, try three period pairs, compare, explain"), dispatch the `crypto-researcher` subagent in a fresh context. Pass it the validated payload, the metric targets, and the rail reminders above. It keeps the main thread clean for the user's follow-up questions.

## Output shape

Present findings in this order:

1. **Validation** — one line: `✅ Spec valid` or `❌ Spec invalid: <N> issues`.
2. **Explanation** — lift the `markdown` field from `explain_strategy` verbatim (already formatted).
3. **Backtest window** — venue, symbol, timeframe, range (ISO timestamps from `period_start_ms`).
4. **Headline metrics** — total_return, win_rate, max_drawdown, profit_factor, sharpe_ratio as a table.
5. **Regime robustness** — one bullet per scenario if `stress_test` was run.
6. **Comparison** — if `compare_strategies` was run, one row per strategy × metric.
7. **Observations** — two or three bullets, qualitative, no action items.
8. **Next steps** — what the user could try (tune X, add Y filter), not what they should do.
