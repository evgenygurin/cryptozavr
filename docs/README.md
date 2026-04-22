# cryptozavr documentation

## Specs
- [MVP design (2026-04-21)](superpowers/specs/2026-04-21-cryptozavr-mvp-design.md) — full architectural design for MVP (Phase 0 + Phase 1).

## Plans
- Historical milestone plans live under [superpowers/plans/](superpowers/plans/) (M1..M3.4 — all landed in v0.2.0 / v0.3.0).
- Phase 1.5 (Realtime + Observability) tracked via Ralph loop; see [ralph-prompts/phase-1.5.md](ralph-prompts/phase-1.5.md).

## References
- [plugin-cli-reference.md](plugin-cli-reference.md) — exhaustive `claude plugin` cheat-sheet.
- [llm-study-guide.md](llm-study-guide.md) — onboarding for new LLM agents: FastMCP v3 topics, GoF patterns, tooling cheat-sheet.

## Per-platform install guides
- [Claude Code](README.claude-code.md)
- [OpenAI Codex](README.codex.md)
- [OpenCode](README.opencode.md)

## Verification / audit logs
- [checks/](checks/) — dated runs of the full semantic sweep (tools / resources / prompts / hooks / invariants).

## Roadmap

- **v0.1.0 (M1..M2.8)** — repo bootstrap, domain + infrastructure, Supabase schema, first MCP tool, multi-platform plugin manifest.
- **v0.2.0 (M3.0..M3.4)** — FastMCP v3 idiomatic refactor, discovery + symbol resolver, analytics (VWAP / S/R / volatility / snapshot), OHLCV history streaming, SessionExplainer envelope. **MVP closure.**
- **v0.3.0 — Phase 1.5** — MetricsDecorator + HealthMonitor + TickerSyncWorker + CacheInvalidator + `venue_health` resource + 5 catalog tools with `structuredContent` + `venue-debug` / `post-session-reflection` skills.
- **v0.4.0+ — Phase 2** — signals / triggers / alerts with Elicit-based approval flows; backtest analytics (Visitor pattern); StrategySpec builder.

## For contributors

See [../README.md](../README.md) for the quick start. Design decisions and trade-offs live in the MVP spec. Per-file Claude Code context: [../CLAUDE.md](../CLAUDE.md).
