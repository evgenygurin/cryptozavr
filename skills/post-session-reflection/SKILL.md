---
name: post-session-reflection
description: Use at the end of a cryptozavr research session (or when the user asks "wrap up" / "what did we do"). Produces a disciplined 3-bullet summary — artifacts produced, decisions made, what's next — so the next session starts warm.
---

# Post-Session Reflection

Use this skill when the user signals the session is winding down (phrases
like "wrap up", "what did we do", "summarize", "done for today"), or
immediately after a multi-tool research collage that warrants a recap.

## Output format — exactly three bullets

```text
- **Produced**: <artifacts — tool outputs, files, commits, plan docs>
- **Decided**: <non-obvious choices made this session, with the reason>
- **Next**: <explicit next step, owner, and trigger condition>
```

## Rules

1. **Three bullets, no more, no less.** If you cannot compress to three,
   drop the least important item; do not add a fourth.
2. Each bullet is **one sentence**. Long bullets hide decisions.
3. **"Produced" stays concrete** — link file paths and commit SHAs when
   they exist, not abstractions.
4. **"Decided" favours the non-obvious.** Trivial defaults ("we used the
   default timeout") do not belong here. A fork in the road does.
5. **"Next" is actionable.** A task the next session can pick up without
   re-reading the transcript. Include the trigger (e.g. "when BTC >= $X"
   or "before PR #Y merges").

## Example

```bash
- **Produced**: `MetricsDecorator` + `HealthMonitor` (commits b7c6991, bb1b8aa) and 24 new unit tests in `tests/unit/observability/`.
- **Decided**: Prometheus-compatible dict snapshot over text format for now — keeps the surface JSON-serialisable until we add the HTTP endpoint in Phase 2.
- **Next**: Wire `HealthMonitor.start()` into `build_production_service` and expose `venue_health_check_total` via `/cryptozavr:health` when Supabase is reachable again.
```

## When NOT to use

- Mid-session debugging (use `venue-debug` instead).
- Quick Q&A where no artifacts were produced.
- Planning sessions — use the `feature-dev` skill's plan format there.
