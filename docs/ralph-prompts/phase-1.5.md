# Ralph prompt — cryptozavr Phase 1.5

You are continuing the cryptozavr plugin in `/Users/laptop/dev/cryptozavr/`.
MVP v0.2.0 is shipped. Your job is to ship Phase 1.5: **Realtime + Observability**.
Target tag: **v0.3.0**.

**Working branch:** `feat/phase-1.5-ralph` (already created, already checked out). Do NOT merge to `main`. Push commits to `origin feat/phase-1.5-ralph`. The tag `v0.3.0` MUST be annotated on the feature branch head AFTER all work is complete; a human reviews the branch and merges it — your job ends at "tag pushed, PR-ready".

## Completion criteria (output `<promise>PHASE_1_5_COMPLETE</promise>` only when ALL are true)

1. `uv run pytest tests/unit tests/contract -m "not integration" -q` passes — **ALL existing + new tests green**.
2. `uv run ruff check . && uv run ruff format --check . && uv run mypy src` all pass.
3. The following deliverables are in the repo:
   - **MetricsDecorator** — 5th decorator (wraps provider calls) exporting Prometheus-compatible counters/histograms (see below).
   - **HealthMonitor** — periodic ping service that refreshes `VenueState` health flags.
   - **TickerSyncWorker** — background task (asyncio, started in lifespan) that re-fetches subscribed tickers every N seconds and updates the L0 cache (the existing `RealtimeSubscriber.subscribe` surface is the hook; if there are no subscriptions, the worker is a no-op).
   - **Supabase Realtime → cache invalidation** — when Supabase Realtime emits a row change on `tickers_live` (or equivalent), the existing `RealtimeSubscriber` already receives it. Extend it to invalidate the relevant cache key through the gateway. If `tickers_live` does not yet exist in migrations, add a new migration that creates it with RLS identical to `tickers` and a trigger that mirrors `INSERT/UPDATE` from `tickers`.
   - **SessionStart plugin hook** — new `hooks/session-start.sh` + entry in `hooks/hooks.json`. On session start, it queries the MCP server for venue health (via a new `venue_health` resource `cryptozavr://venue_health` that returns `{venue: healthy|degraded|down, last_checked_ms}`) and prints a 1-line banner.
   - **2 new skills** under `skills/`:
     - `venue-debug/SKILL.md` — guides Claude through diagnosing a venue failure (walk the chain, inspect `provider_events`, check rate limits, check HTTP pool).
     - `post-session-reflection/SKILL.md` — 3-bullet post-session summary skill: what was produced, what decisions were made, what's next.
4. CHANGELOG.md has a `## [0.3.0]` section describing Phase 1.5.
5. Git tag `v0.3.0` exists locally AND is pushed to `origin`.
6. Branch `feat/phase-1.5-ralph` is pushed to `origin`. **Do NOT push to `main`.**

## Constraints (hard)

- **Do NOT** break any existing test. If a change would break one, update the test with a comment explaining why.
- **Do NOT** modify any file under `src/cryptozavr/domain/` or `src/cryptozavr/application/strategies/` unless strictly required.
- **No live Supabase mocking in unit tests.** Realtime subscriber changes are tested with `MagicMock(spec=RealtimeSubscriber)` at the service layer.
- Follow the import-placement rule in `CLAUDE.md` (imports added together with usage, never ahead).
- Conventional commits, atomic, one logical unit per commit, commit messages via `/tmp/commit-msg.txt` + `git commit -F` (never HEREDOC).
- Pre-commit hooks are authoritative; fix failures, never `--no-verify`.
- When in doubt about FastMCP v3 idioms, re-read `/Users/laptop/.claude/projects/-Users-laptop-dev-cryptozavr/memory/feedback_fastmcp_idiomatic.md`.

## Recommended task order (each a commit)

1. `feat(infrastructure): add MetricsDecorator (Prometheus counters/histograms)` — TDD.
2. `feat(application): add HealthMonitor service + tests` — TDD.
3. `feat(application): add TickerSyncWorker background task` — TDD.
4. `feat(mcp): add cryptozavr://venue_health resource` — TDD.
5. `feat(infrastructure): invalidate cache on realtime tickers_live update` — TDD.
6. `feat(plugin): add SessionStart hook that prints venue-health banner`.
7. `feat(plugin): add venue-debug + post-session-reflection skills`.
8. Wire everything into `bootstrap.py` + `server.py`. Update `commands/health.md` banner.
9. `docs: finalize CHANGELOG for v0.3.0 (Phase 1.5)` + `git tag -a v0.3.0 -m "..."` + `git push origin feat/phase-1.5-ralph && git push origin v0.3.0`. **Never push to `main`.**
10. Output `<promise>PHASE_1_5_COMPLETE</promise>` ONLY after step 9 is verified with `git ls-remote --tags origin | grep v0.3.0` AND `git ls-remote --heads origin | grep feat/phase-1.5-ralph`.

## MetricsDecorator contract (detail)

Wraps any provider method call. Exposes a Prometheus-ready text endpoint later, but for Phase 1.5 just maintains the in-memory registry:

```python
class MetricsRegistry:
    def inc_counter(self, name: str, *, labels: dict[str, str]) -> None
    def observe_histogram(self, name: str, *, labels: dict[str, str], value: float) -> None
    def snapshot(self) -> dict[str, Any]  # Prometheus text format
```

Decorator emits:
- `provider_calls_total{venue, endpoint, outcome}` — counter, outcome ∈ {ok, error, rate_limited, timeout}.
- `provider_call_duration_ms{venue, endpoint}` — histogram, buckets [50, 100, 250, 500, 1000, 2500, 5000, inf].

## HealthMonitor contract

Periodic task (interval configurable, default 60s):
- For each `VenueId`, calls the lightest provider endpoint (e.g. `fetch_time` for CCXT adapters, `/ping` for CoinGecko).
- On success → `VenueState.mark_healthy()`; on failure → `VenueState.mark_degraded(reason)`.
- Metrics: emits `venue_health_check_total{venue, outcome}` through `MetricsDecorator`.
- Exposed as an asyncio task started from `build_production_service()`; cleanup cancels it.

## TickerSyncWorker contract

Async task that periodically:
1. Reads currently-subscribed symbols from `RealtimeSubscriber.subscriptions()` (add this read-only accessor if missing).
2. For each subscription, calls `TickerService.fetch_ticker(force_refresh=True)`.
3. On error — log via `ctx.warning`, do not crash.
4. Interval configurable (default 30s). No-op when no subscriptions.

## After every iteration (yourself)

- If tests are failing: read the failure, fix the narrowest root cause, re-run tests.
- If pre-commit fails: read the hook output, fix the root cause, re-run `git commit`.
- If stuck on a sub-task for 3 iterations: document the blocker in `docs/ralph-prompts/phase-1.5-blockers.md` and move to the next deliverable.
