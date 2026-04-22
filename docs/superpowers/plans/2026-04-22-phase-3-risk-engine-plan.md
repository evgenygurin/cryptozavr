# Implementation plan — Phase 3 RiskEngine

**Spec:** `docs/superpowers/specs/2026-04-22-phase-3-risk-engine-design.md`
**Base branch:** `main @ e61202e` (post Phase 2 closure merge)
**Feature branch:** `feat/phase-3-risk-engine`

Three units + closure. Each unit = one subagent dispatch + one light review (IRON RULE #8).

## Unit 3-1 — Domain + Policy DSL

**Dependencies:** none (adds new files).

**Files to create:**
- `src/cryptozavr/domain/risk.py` — `RiskStatus`, `Severity` StrEnums; `TradeIntent`, `Violation`, `RiskDecision` frozen dataclasses with `__post_init__` invariants
- `src/cryptozavr/application/risk/__init__.py` — empty package marker
- `src/cryptozavr/application/risk/risk_policy.py` — `LimitDecimal`, `LimitInt`, `RiskPolicy` Pydantic models (frozen, `@model_validator(mode="after")` for pct bounds + leverage floor)
- `tests/unit/domain/test_risk.py` — ~15 tests (TradeIntent/Violation/RiskDecision invariants, status coherence)
- `tests/unit/application/__init__.py` / `tests/unit/application/risk/__init__.py` — package markers
- `tests/unit/application/risk/test_risk_policy.py` — ~8 tests (pct bounds, leverage floor, Decimal Field constraints, severity default)

**Acceptance:** 23 new tests pass. `uv run mypy src/cryptozavr/domain/risk.py src/cryptozavr/application/risk/` clean. ruff clean.

**Budget:** 1 subagent + 1 light review.

- [x] Unit 3-1 done (9a9cda4, light review APPROVED)

## Unit 3-2 — RiskEngine + 5 handlers + KillSwitch

**Dependencies:** Unit 3-1 landed (imports `TradeIntent`, `RiskPolicy`, `RiskDecision`, `Violation`, `Severity`, `RiskStatus`).

**Files to create:**
- `src/cryptozavr/application/risk/kill_switch.py` — `KillSwitchStatus` dataclass + `KillSwitch` class (thread-safe via `threading.Lock`, `engage` / `disengage` / `status` / `is_engaged`)
- `src/cryptozavr/application/risk/handlers.py` — 5 classes + shared `RiskHandler` Protocol:
  - `RiskHandler` Protocol (`name: ClassVar[str]`, `evaluate(intent, policy, kill_switch) → Violation | None`)
  - `RiskPolicyHandler` — max_leverage
  - `ExposureHandler` — max_position_pct (skips when `current_balance is None`)
  - `LiquidityHandler` — min_balance_buffer (skips when `current_balance is None`)
  - `CooldownHandler` — `recent_losses >= cooldown_after_n_losses` (stateless)
  - `KillSwitchHandler` — always DENY if `kill_switch.is_engaged()` (ignores severity config — kill is non-negotiable)
- `src/cryptozavr/application/risk/engine.py` — `RiskEngine` class with `_aggregate_status` helper
- `tests/unit/application/risk/test_kill_switch.py` — ~6 tests (engage/disengage idempotence, status fields, thread-safety smoke)
- `tests/unit/application/risk/test_handlers.py` — ~20 tests (each handler: happy path, violation path, skip path for context-dependent handlers)
- `tests/unit/application/risk/test_engine.py` — ~10 tests (full chain scenarios)

**Acceptance:** ~36 new tests pass. mypy clean. RiskEngine holds 5 handlers in the canonical order from spec § 11.3 (`RiskPolicy → Exposure → Liquidity → Cooldown → KillSwitch`).

**Budget:** 1 subagent + 1 light review.

- [x] Unit 3-2 done (16d5b2a, light review APPROVED)

## Unit 3-3 — Persistence + MCP surface

**Dependencies:** Units 3-1 + 3-2 landed.

**Files to create:**
- `supabase/migrations/00000000000080_risk_policies.sql` — table, partial unique index, RLS, policy
- `src/cryptozavr/infrastructure/persistence/risk_policy_repo.py` — `RiskPolicyRow` frozen dataclass + `RiskPolicyRepository` class (asyncpg-based, mirrors `StrategySpecRepository` pattern; content_hash idempotency)
- `src/cryptozavr/mcp/tools/risk_dtos.py` — payload + response DTOs (Pydantic, frozen, coherence validators where applicable)
- `src/cryptozavr/mcp/tools/risk_tools.py` — `register_risk_tools(mcp)` wiring all 6 tools (`set_risk_policy`, `get_risk_policy`, `evaluate_trade_intent`, `simulate_risk_check`, `engage_kill_switch`, `disengage_kill_switch`)
- `tests/unit/infrastructure/persistence/test_risk_policy_repo.py` — ~10 tests (AsyncMock pool; save, activate transaction, get_active, list_history, idempotent content_hash)
- `tests/unit/mcp/tools/test_risk_tools.py` — ~20 tests (6 tools × DTO round-trips, coherence validators, chain integration with mocked engine, structured_content assertions)
- `tests/integration/supabase/test_risk_policies_roundtrip.py` — 3 tests (save+activate+get, idempotent save, history ordering), `pytestmark = pytest.mark.integration`

**Files to edit:**
- `src/cryptozavr/mcp/lifespan_state.py` — add `LIFESPAN_KEYS.risk_policy_repo`, `risk_engine`, `kill_switch` + accessors
- `src/cryptozavr/mcp/bootstrap.py` — instantiate KillSwitch → 5 handlers → RiskEngine → RiskPolicyRepository; add to state dict
- `src/cryptozavr/mcp/server.py` — import + call `register_risk_tools(mcp)` after existing `register_strategy_compute_tools(mcp)` line

**Tool timeouts:** `set_risk_policy` / `engage_kill_switch` / `disengage_kill_switch` → 30s; `get_risk_policy` / `evaluate_trade_intent` / `simulate_risk_check` → 10s.

**Tool tags:** `{"risk", "phase-3"}` on all 6. `set_risk_policy` / `engage_kill_switch` / `disengage_kill_switch` are `readOnlyHint=False`; the other three `readOnlyHint=True`.

**Acceptance:** ~33 new tests pass (unit); 3 integration tests skip cleanly when Supabase not running. mypy clean. ruff clean. Full suite ≥ 820 (≈ 758 pre-Phase-3 + 60-ish new).

**Budget:** 1 subagent + 1 light review.

- [ ] Unit 3-3 done

## Phase 3 closure — heavy review + PR + merge

- [ ] Heavy review via `pr-review-toolkit:code-reviewer` against `main..feat/phase-3-risk-engine` diff
- [ ] Fix Important / Critical issues
- [ ] Optional: pr-review-toolkit full 5-agent pass as in Phase 2 (comments / tests / silent-failures / types / code)
- [ ] Push branch + open PR + await user merge
- [ ] **Phase 3 ✓ merged**
- [ ] Update master plan checkboxes (3-1 / 3-2 / 3-3 / Phase 3 ✓)

**Budget (subagent dispatches):** 3 impl + 3 light reviews + 1 heavy review = **7**. Matches master-plan estimate.

## Risks / open items

- **pgvector smoke still deferred.** Phase 2 integration tests for `::extensions.vector` cast remain SKIPPED locally. Phase 3 migration does not touch pgvector, so no new exposure — but the underlying gap stays. Recommend running `supabase start` + the Phase 2 integration suite before Phase 4 (paper) start, since Phase 4 will land portfolio state persisted via same pool.
- **BacktestVisitor ClassVar cleanup.** Spawned task still pending from Phase 2D-3 review. Not blocking Phase 3.
- **Audit log table.** Phase 3 explicitly defers it. When Phase 5 needs it, migration 00000000000090_risk_evaluations.sql will land with the live-execution scope.
- **Mode capability gate.** `EVALUATE_RISK` capability exists in MVP spec §11 but ModeGuard currently exposes the Phase-3 tools via default `RESEARCH_ONLY` mode. Acceptable for MVP; Phase 5 will tighten as live execution requires explicit mode opt-in.
